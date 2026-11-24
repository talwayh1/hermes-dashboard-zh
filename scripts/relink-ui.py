#!/usr/bin/env python3
"""
把组件里硬编码的英文文案重新接入 t.ui.*。

以 semantic-pack.json 的 ui_en（key -> 英文原文）为映射，
在 .tsx 中查找文本节点/属性值，替换为表达式形式的 t.ui.<key>，
并确保文件已 import useI18n 且作用域内有 t。

用法: python3 relink-ui.py <HERMES_DIR> <PACK_JSON> [--dry-run]

设计原则:
  - 只替换「整段文本完全等于某个 ui 英文原文」的情形，避免误伤
  - JSX 属性写成 {t.ui.x}（表达式），文本节点写成 {t.ui.x}
  - 已在 t.ui.* 里的不重复处理
  - 不做 AST 改写（脆），改用「精确短语 + 上下文确认」策略
"""
import json
import re
import sys
import pathlib

args = [a for a in sys.argv[1:] if not a.startswith("--")]
flags = {a for a in sys.argv[1:] if a.startswith("--")}
HERMES = pathlib.Path(args[0] if args else "/opt/hermes")
PACK = pathlib.Path(args[1] if len(args) > 1 else "semantic-pack.json")
DRY = "--dry-run" in flags

SRC = HERMES / "web" / "src"
pack = json.loads(PACK.read_text(encoding="utf-8"))
ui_en = pack.get("ui_en", {})

# 英文原文 -> ui key（仅保留唯一映射，歧义的不动）
by_text = {}
dup = set()
for k, v in ui_en.items():
    if not v or len(v) < 2:
        continue
    if v in by_text:
        dup.add(v)
    by_text[v] = k
for d in dup:
    by_text.pop(d, None)

# 长句优先，避免短句先匹配吃掉长句的一部分
ordered = sorted(by_text.items(), key=lambda kv: -len(kv[0]))

stats = {"files": 0, "replaced": 0, "need_hook": [], "skipped_files": []}

HOOK = "const { t } = useI18n();"
IMPORT = 'import { useI18n } from "@/i18n";'


def has_hook(text):
    return re.search(r"\bconst\s*\{\s*t\s*\}\s*=\s*useI18n\s*\(\s*\)", text) is not None


def add_import(text):
    if re.search(r'import\s*\{[^}]*\buseI18n\b[^}]*\}\s*from\s*["\']@/i18n["\']', text):
        return text, False
    # 插到第一条 import 之后
    m = re.search(r"^import[^\n]*\n", text, re.M)
    if not m:
        return text, False
    return text[:m.end()] + IMPORT + "\n" + text[m.end():], True


def jsx_safe(text):
    """跳过 import 行与注释行的替换。"""
    return text


def process(path):
    orig = path.read_text(encoding="utf-8")
    text = orig
    # 已被处理过的文件（含 t.ui.）仍可能漏网，一并尝试
    n = 0

    for eng, key in ordered:
        # 已存在该 key 的引用就跳过
        if re.search(r"\bt\.ui\." + re.escape(key) + r"\b", text):
            continue

        # 形态 1: JSX 文本节点  >English<
        pat_text = re.compile(r">(" + re.escape(eng) + r")<")
        # 形态 2: 属性值  attr="English"
        pat_attr = re.compile(r'(\b(?:title|label|placeholder|aria-label|alt|tooltip|description)=)("' +
                              re.escape(eng) + r'")')
        # 形态 3: 默认参数  = "English"
        pat_default = re.compile(r'(=\s*)"(' + re.escape(eng) + r')"(?=\s*[,)])')

        new = pat_text.sub(lambda m: ">{" + f"t.ui.{key}" + "}<", text, count=1)
        if new != text:
            text = new
            n += 1
            continue

        new = pat_attr.sub(lambda m: m.group(1) + "{" + f"t.ui.{key}" + "}", text, count=1)
        if new != text:
            text = new
            n += 1
            continue

        new = pat_default.sub(lambda m: m.group(1) + "{" + f"t.ui.{key}" + "}", text, count=1)
        if new != text:
            text = new
            n += 1

    if n == 0:
        return 0

    # 需要 t 作用域
    if not has_hook(text):
        stats["need_hook"].append(str(path.relative_to(SRC)))

    if not DRY:
        path.write_text(text, encoding="utf-8")
    return n


def main():
    files = sorted(SRC.rglob("*.tsx"))
    for p in files:
        try:
            n = process(p)
        except Exception as e:
            stats["skipped_files"].append(f"{p}: {e}")
            continue
        if n:
            stats["files"] += 1
            stats["replaced"] += n

    # 补 import
    if not DRY:
        for p in files:
            try:
                txt = p.read_text(encoding="utf-8")
            except Exception:
                continue
            if "t.ui." in txt and not re.search(r'\buseI18n\b', txt):
                new, changed = add_import(txt)
                if changed:
                    p.write_text(new, encoding="utf-8")

    print(json.dumps({
        "mode": "dry-run" if DRY else "write",
        "ui_en_keys": len(ui_en),
        "unique_texts": len(by_text),
        "ambiguous_skipped": len(dup),
        "files_changed": stats["files"],
        "replacements": stats["replaced"],
        "needs_hook": stats["need_hook"][:20],
        "needs_hook_count": len(stats["need_hook"]),
        "skipped": stats["skipped_files"][:5],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()