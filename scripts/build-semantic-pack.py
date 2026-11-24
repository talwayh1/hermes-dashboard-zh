#!/usr/bin/env python3
"""
生成 Hermes Dashboard 中文补丁的「语义化补丁包」。

不依赖上游行号：抽出 zh/en 的完整键值对 + 每个文件的 t.ui 引用 + 改动文件清单。
升级后用 build 逻辑重放：以 en.ts 为基准，把 zh 译文补进去。

用法:
  python3 build-semantic-pack.py <HERMES_DIR> <OUT_JSON>
依赖: node + <HERMES_DIR>/node_modules/typescript
"""
import json
import re
import sys
import pathlib
import subprocess

HERMES = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/hermes")
OUT = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "semantic-pack.json")

SRC = HERMES / "web" / "src"
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PARSER = SCRIPT_DIR / "parse-locale.js"


def parse_locale(locale_file):
    tmp = pathlib.Path("/tmp") / f"_pack_{locale_file.stem}.json"
    r = subprocess.run(
        ["node", str(PARSER), str(locale_file), str(tmp)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise SystemExit(f"parse failed for {locale_file}:\n{r.stderr}")
    return json.loads(tmp.read_text(encoding="utf-8"))


def changed_files():
    r = subprocess.run(
        ["git", "-C", str(HERMES), "diff", "--name-only", "HEAD", "--",
         "web/src", "hermes_cli/web_server_dashboard.py"],
        capture_output=True, text=True,
    )
    return [f for f in r.stdout.splitlines() if f.strip()]


def changed_added_files():
    """新增文件（未跟踪）也要记，重放时需要一并带过去。"""
    r = subprocess.run(
        ["git", "-C", str(HERMES), "ls-files", "--others", "--exclude-standard",
         "--", "web/src"],
        capture_output=True, text=True,
    )
    return [f for f in r.stdout.splitlines() if f.strip()]


def collect_ui_refs():
    refs = {}
    for p in SRC.rglob("*.tsx"):
        try:
            txt = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in re.finditer(r"\bt\.ui\.([A-Za-z_][\w]*)", txt):
            k = m.group(1)
            refs.setdefault(k, set()).add(str(p.relative_to(SRC)))
    return {k: sorted(v) for k, v in sorted(refs.items())}


def main():
    en = parse_locale(SRC / "i18n" / "en.ts")
    zh = parse_locale(SRC / "i18n" / "zh.ts")

    pack = {
        "schema": 2,
        "generated_from": {
            "hermes_head": subprocess.run(
                ["git", "-C", str(HERMES), "rev-parse", "HEAD"],
                capture_output=True, text=True).stdout.strip(),
            "hermes_version": subprocess.run(
                ["git", "-C", str(HERMES), "describe", "--tags", "--always"],
                capture_output=True, text=True).stdout.strip(),
            "en_keys": len(en),
            "zh_keys": len(zh),
        },
        # 译文全量（重放时的唯一事实来源）
        "zh_translations": zh,
        # en 独有（补丁新增的键在 en 侧也要能重建）
        "en_only": {k: v for k, v in en.items() if k not in zh},
        # ui 段（补丁新增，上游没有）
        "ui_en": {k: v for k, v in en.items() if k.startswith("ui.")},
        "ui_zh": {k: v for k, v in zh.items() if k.startswith("ui.")},
        # 组件里哪些文件引用了哪些 ui key
        "ui_refs": collect_ui_refs(),
        # 补丁触及的文件
        "changed_files": changed_files(),
        "added_files": changed_added_files(),
    }

    OUT.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"written: {OUT}")
    print(f"  version={pack['generated_from']['hermes_version']} "
          f"head={pack['generated_from']['hermes_head'][:12]}")
    print(f"  en={len(en)} zh={len(zh)} en_only={len(pack['en_only'])}")
    print(f"  ui_en={len(pack['ui_en'])} ui_zh={len(pack['ui_zh'])}")
    print(f"  ui_refs keys={len(pack['ui_refs'])}")
    print(f"  changed={len(pack['changed_files'])} added={len(pack['added_files'])}")


if __name__ == "__main__":
    main()