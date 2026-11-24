#!/usr/bin/env python3
"""
Hermes Dashboard 中文补丁 — 语义化重放器

不依赖上游行号的补丁重放：以 en.ts 当前内容为基准，把 semantic-pack.json
里的中文译文合并进 zh.ts，并把组件里的英文文案重新接入 t.ui.*。

用法:
  python3 replay-zh.py <HERMES_DIR> <PACK_JSON> [--dry-run] [--build]

设计目标：上游任意改动后仍能重放，冲突只体现在「键消失」而非「行号错位」。
"""
import json
import re
import sys
import pathlib
import subprocess

args = [a for a in sys.argv[1:] if not a.startswith("--")]
flags = {a for a in sys.argv[1:] if a.startswith("--")}

HERMES = pathlib.Path(args[0] if args else "/opt/hermes")
PACK = pathlib.Path(args[1] if len(args) > 1 else "semantic-pack.json")
DRY = "--dry-run" in flags
BUILD = "--build" in flags

SRC = HERMES / "web" / "src"
EN = SRC / "i18n" / "en.ts"
ZH = SRC / "i18n" / "zh.ts"

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PARSER = SCRIPT_DIR / "parse-locale.js"


def parse_locale(path):
    tmp = pathlib.Path("/tmp") / f"_replay_{path.stem}.json"
    r = subprocess.run(["node", str(PARSER), str(path), str(tmp)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"解析失败 {path}:\n{r.stderr}")
    return json.loads(tmp.read_text(encoding="utf-8"))


def render_value(v):
    """把字符串渲染为 TS 字符串字面量（保留 {placeholder}）。"""
    esc = v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{esc}"'


def find_object_range(text, key_path):
    """
    在 TS 源码里定位嵌套对象的字符区间。
    key_path 形如 ["ui"] 或 ["common", "app"]。
    返回 (obj_start, obj_end)：obj_start 指向 `{`，obj_end 指向匹配的 `}`。
    找不到返回 None。
    """
    pos = 0
    for i, k in enumerate(key_path):
        pat = re.compile(r'(?:^|[\s,{])(?:' + re.escape(k) + r'|"' + re.escape(k) +
                         r'"|\'' + re.escape(k) + r'\')\s*:\s*\{', re.M)
        m = pat.search(text, pos)
        if not m:
            return None
        obj_start = text.index("{", m.start())
        # 匹配括号
        depth = 0
        j = obj_start
        in_str = None
        while j < len(text):
            c = text[j]
            if in_str:
                if c == "\\":
                    j += 2
                    continue
                if c == in_str:
                    in_str = None
            elif c in "\"'`":
                in_str = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return obj_start, j
            j += 1
        return None
    return None


def merge_section(text, section_path, entries, dry):
    """
    把 entries {key: value} 合并进 text 中 section_path 指向的对象。
    已存在的键就地更新，缺失的键插到该对象末尾。
    """
    rng = find_object_range(text, section_path)
    if not rng:
        return text, {"status": "section-missing", "added": 0, "updated": 0}
    obj_start, obj_end = rng
    body = text[obj_start + 1:obj_end]

    added, updated = 0, 0
    for k, v in entries.items():
        # 匹配 `key: "..."`（字符串值，支持双引号/单引号/反引号）
        dq = r'"(?:\\.|[^"\\])*"'
        sq = r"'(?:\\.|[^'\\])*'"
        bq = r"`(?:\\.|[^`\\])*`"
        pat = re.compile(r'(?<![\w$])' + re.escape(k) + r'\s*:\s*'
                         r'(?:' + dq + "|" + sq + "|" + bq + r')', re.M)
        m = pat.search(body)
        if m:
            old = m.group(0)
            new = f"{k}: {render_value(v)}"
            if old != new:
                body = body[:m.start()] + new + body[m.end():]
                updated += 1
        else:
            added += 1

    if added:
        # 收集缺失键，追加到对象末尾
        missing = {}
        for k, v in entries.items():
            pat = re.compile(r'(?<![\w$])' + re.escape(k) + r'\s*:\s*', re.M)
            if not pat.search(body):
                missing[k] = v
        if missing:
            lines = "".join(
                f"    {k}: {render_value(v)},\n" for k, v in missing.items()
            )
            # 去掉末尾空白后插在闭合括号前
            trimmed = body.rstrip()
            if not trimmed.endswith(","):
                trimmed += ","
            body = trimmed + "\n" + lines + "  "

    return text[:obj_start + 1] + body + text[obj_end:], {
        "status": "ok", "added": added, "updated": updated
    }


def ensure_ui_section(text, ui_entries):
    """确保顶层存在 ui: { ... } 段。"""
    if find_object_range(text, ["ui"]):
        return merge_section(text, ["ui"], ui_entries, DRY)
    # 没有 ui 段：在顶层对象末尾插入
    top = find_object_range(text, [])
    if not top:
        # 退化：定位第一个 `= {`
        m = re.search(r"=\s*\{", text)
        if not m:
            return text, {"status": "no-top-obj", "added": 0, "updated": 0}
        obj_start = text.index("{", m.start())
        depth, j, in_str = 0, obj_start, None
        while j < len(text):
            c = text[j]
            if in_str:
                if c == "\\":
                    j += 2
                    continue
                if c == in_str:
                    in_str = None
            elif c in "\"'`":
                in_str = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        obj_end = j
    else:
        obj_start, obj_end = top

    body = text[obj_start + 1:obj_end].rstrip()
    if not body.endswith(","):
        body += ","
    inner = "".join(f"    {k}: {render_value(v)},\n" for k, v in ui_entries.items())
    new_body = body + f"\n  ui: {{\n{inner}  }},\n"
    return text[:obj_start + 1] + new_body + text[obj_end:], {
        "status": "ui-section-created", "added": len(ui_entries), "updated": 0
    }


def main():
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    report = {"version": pack.get("generated_from", {}), "steps": []}

    if not EN.exists() or not ZH.exists():
        raise SystemExit(f"找不到 locale 文件: {EN} / {ZH}")

    en_cur = parse_locale(EN)
    zh_pack = pack["zh_translations"]
    ui_zh = pack["ui_zh"]

    report["upstream_en_keys"] = len(en_cur)
    report["pack_zh_keys"] = len(zh_pack)

    # 上游新增、补丁里没有的键 —— 会回退英文，需要人工补译文
    pack_missing = sorted(k for k in en_cur if k not in zh_pack and not k.startswith("ui."))
    report["upstream_new_keys"] = len(pack_missing)
    report["upstream_new_sample"] = pack_missing[:15]

    # 上游已删除、补丁里还留着的键 —— 无害但可清理
    gone = sorted(k for k in zh_pack if k not in en_cur and not k.startswith("ui."))
    report["stale_keys"] = len(gone)
    report["stale_sample"] = gone[:10]

    if DRY:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    # --- 1) 写 zh.ts ---
    zh_text = ZH.read_text(encoding="utf-8")
    top_entries = {}
    for k, v in zh_pack.items():
        if k not in en_cur:
            continue  # 上游已无此键，不写
        top_entries[k] = v

    # 按顶段分组写回
    sections = {}
    for k, v in top_entries.items():
        if "." in k:
            sec, sub = k.split(".", 1)
            sections.setdefault(sec, {})[sub] = v
        else:
            sections.setdefault("__top__", {})[k] = v

    total_upd = 0
    for sec, entries in sections.items():
        if sec == "__top__" or sec == "ui":
            continue
        zh_text, st = merge_section(zh_text, [sec], entries, DRY)
        total_upd += st.get("updated", 0) + st.get("added", 0)
        report["steps"].append({"section": sec, **st})

    # ui 段
    zh_text, st = ensure_ui_section(zh_text, ui_zh)
    total_upd += st.get("updated", 0) + st.get("added", 0)
    report["steps"].append({"section": "ui", **st})

    ZH.write_text(zh_text, encoding="utf-8")
    report["zh_written"] = True
    report["zh_changes"] = total_upd

    zh_after = parse_locale(ZH)
    report["zh_keys_after"] = len(zh_after)
    report["missing_after"] = len([k for k in en_cur if k not in zh_after])

    if BUILD:
        r = subprocess.run(["npm", "run", "build"], cwd=HERMES / "web",
                           capture_output=True, text=True)
        report["build"] = {"rc": r.returncode, "tail": (r.stdout or r.stderr)[-500:]}

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()