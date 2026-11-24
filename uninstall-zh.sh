#!/usr/bin/env bash
# 回滚 Hermes Dashboard 中文补丁
# 用法: ./uninstall-zh.sh [HERMES_DIR] [BACKUP_STAMP]
#   BACKUP_STAMP 形如 20261124-144800，对应 install-zh.sh 生成的备份目录
#   省略 stamp 时自动选择最新备份
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCH="$HERE/patches/hermes-zh-web.patch"
TARGET="${1:-${HERMES_DIR:-$HOME/hermes}}"
STAMP="${2:-}"

info() { printf '\033[36m→ %s\033[0m\n' "$*"; }
ok()   { printf '\033[32m✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[33m! %s\033[0m\n' "$*"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

[ -d "$TARGET/web/src/i18n" ] || die "不是 Hermes 源码目录: $TARGET"

if [ -z "$STAMP" ]; then
  STAMP="$(ls -1d "$TARGET"/.zh-pack-backup-* 2>/dev/null | sort | tail -1 | sed 's#.*\.zh-pack-backup-##')"
fi
BAK="$TARGET/.zh-pack-backup-${STAMP:-none}"

if [ -d "$BAK" ]; then
  info "从备份恢复: $BAK"
  n=0
  while IFS= read -r -d '' f; do
    rel="${f#$BAK/}"
    mkdir -p "$TARGET/$(dirname "$rel")"
    cp -p "$f" "$TARGET/$rel"
    n=$((n+1))
  done < <(find "$BAK" -type f -print0)
  ok "已恢复 $n 个文件"
else
  warn "未找到备份目录，改为反向应用补丁"
  [ -f "$PATCH" ] || die "找不到补丁: $PATCH"
  git -C "$TARGET" apply -R -3 "$PATCH" || die "反向应用失败，请手工处理"
  ok "反向应用完成"
fi

WEB="$TARGET/web"
if [ -d "$WEB/node_modules" ]; then
  info "重新构建前端（npm run build）…"
  ( cd "$WEB" && npm run build ) || warn "构建失败，请手工检查"
  ok "前端已重建"
else
  warn "$WEB/node_modules 不存在，跳过构建"
fi

cat <<EOF

$(printf '\033[32m回滚完成\033[0m')

请重启 dashboard 并强制刷新浏览器。
EOF