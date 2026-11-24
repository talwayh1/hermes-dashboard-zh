#!/usr/bin/env bash
# 校验中文补丁是否生效
# 用法: ./verify-zh.sh [HERMES_DIR]
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-${HERMES_DIR:-$HOME/hermes}}"
I18N="$TARGET/web/src/i18n"

pass=0; fail=0
chk() { # chk <描述> <条件命令...>
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf '\033[32m✓\033[0m %s\n' "$desc"; pass=$((pass+1))
  else
    printf '\033[31m✗\033[0m %s\n' "$desc"; fail=$((fail+1))
  fi
}

[ -d "$I18N" ] || { echo "不是 Hermes 源码目录: $TARGET"; exit 1; }

echo "=== 文件级检查 ==="
chk "zh.ts 存在" test -f "$I18N/zh.ts"
chk "context.tsx 支持 __HERMES_LOCALE__" grep -q "__HERMES_LOCALE__" "$I18N/context.tsx"
chk "types.ts 导出 UiStrings" grep -q "UiStrings" "$I18N/types.ts"
chk "后端注入 __HERMES_LOCALE__" grep -q "__HERMES_LOCALE__" "$TARGET/hermes_cli/web_server_dashboard.py"
chk "App.tsx 导航项已接入 labelKey" grep -q "labelKey" "$TARGET/web/src/App.tsx"
chk "utils.ts 相对时间本地化" grep -qE "分钟前|小时前|天前|__HERMES_LOCALE__" "$TARGET/web/src/lib/utils.ts"

echo
echo "=== 键数对比 ==="
en_keys=$(grep -cE '^[[:space:]]+[a-zA-Z_]+:' "$I18N/en.ts" 2>/dev/null || echo 0)
zh_keys=$(grep -cE '^[[:space:]]+[a-zA-Z_]+:' "$I18N/zh.ts" 2>/dev/null || echo 0)
echo "en.ts 键数: $en_keys"
echo "zh.ts 键数: $zh_keys"

echo
echo "=== ui 段键数 ==="
ui_en=$(sed -n '/^  ui: {/,/^  },/p' "$I18N/en.ts" 2>/dev/null | grep -cE '^[[:space:]]+[a-zA-Z_]+:')
echo "en.ts ui 段: $ui_en 个键"

echo
echo "=== 硬编码残留扫描（组件内 JSX 纯文本）==="
left=$(cd "$TARGET/web/src" && grep -rnoE '>[A-Z][a-z]+( [a-z]+)*<' --include=*.tsx . 2>/dev/null | wc -l)
echo "疑似残留: $left 处（不区分是否已接入 i18n）"

echo
echo "=== TypeScript 编译 ==="
if [ -d "$TARGET/web/node_modules" ]; then
  if ( cd "$TARGET/web" && npx tsc -p tsconfig.app.json --noEmit >/tmp/zh-verify-tsc.log 2>&1 ); then
    printf '\033[32m✓\033[0m tsc 通过（0 错误）\n'; pass=$((pass+1))
  else
    printf '\033[31m✗\033[0m tsc 报错，详见 /tmp/zh-verify-tsc.log\n'; fail=$((fail+1))
    head -10 /tmp/zh-verify-tsc.log
  fi
else
  printf '\033[33m!\033[0m node_modules 缺失，跳过 tsc\n'
fi

echo
echo "=== 结果: 通过 $pass / 失败 $fail ==="
[ "$fail" -eq 0 ] && exit 0 || exit 1