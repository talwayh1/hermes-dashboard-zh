#!/usr/bin/env bash
# 安装 Hermes Dashboard 中文补丁
# 用法: ./install-zh.sh [HERMES_DIR]
#   默认 HERMES_DIR=$HOME/hermes，可用环境变量或第一个参数覆盖
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCH="$HERE/patches/hermes-zh-web.patch"
BASE_FILE="$HERE/patches/BASE_COMMIT.txt"
TARGET="${1:-${HERMES_DIR:-$HOME/hermes}}"

info() { printf '\033[36m→ %s\033[0m\n' "$*"; }
ok()   { printf '\033[32m✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[33m! %s\033[0m\n' "$*"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

[ -f "$PATCH" ] || die "找不到补丁: $PATCH"
[ -d "$TARGET/web/src/i18n" ] || die "不是 Hermes 源码目录: $TARGET (缺少 web/src/i18n)"

BASE="$(cat "$BASE_FILE" 2>/dev/null || echo unknown)"
CUR="$(git -C "$TARGET" rev-parse HEAD 2>/dev/null || echo none)"

info "目标: $TARGET"
info "补丁基线: ${BASE:0:12}"
info "当前 HEAD: ${CUR:0:12}"

# --- 1) 允许带冲突继续（-3 三方合并），失败则中止 ---
STAMP="$(date +%Y%m%d-%H%M%S)"
BAK="$TARGET/.zh-pack-backup-$STAMP"

info "备份受影响文件到 $BAK"
mkdir -p "$BAK"
( cd "$TARGET" && grep '^diff --git' "$PATCH" \
    | sed -E 's#^diff --git a/(.*) b/.*#\1#' \
    | while IFS= read -r f; do
        [ -f "$f" ] && { mkdir -p "$BAK/$(dirname "$f")"; cp -p "$f" "$BAK/$f"; }
      done )
ok "备份完成: $(find "$BAK" -type f | wc -l) 个文件"

# --- 2) 先 dry-run ---
if ! git -C "$TARGET" apply --check -3 "$PATCH" 2>/tmp/zh-apply-check.err; then
  warn "标准应用失败，错误如下："
  head -20 /tmp/zh-apply-check.err
  warn "尝试三方合并（--3way）…"
fi

# --- 3) 应用 ---
if ! git -C "$TARGET" apply -3 "$PATCH"; then
  die "应用失败。回滚可执行: ./uninstall-zh.sh $TARGET $STAMP"
fi
ok "补丁已应用"

if [ -n "$(git -C "$TARGET" status --porcelain | grep -E '^(UU|AA)' || true)" ]; then
  warn "存在合并冲突，需要手工解决："
  git -C "$TARGET" status --porcelain | grep -E '^(UU|AA)' || true
  die "解决冲突后重新构建。回滚: ./uninstall-zh.sh $TARGET $STAMP"
fi

# --- 4) 设置 display.language=zh ---
CFG="${HERMES_CONFIG:-$HOME/.hermes/config.yaml}"
if [ -f "$CFG" ]; then
  if grep -qE '^\s+language:\s*' "$CFG"; then
    sed -i -E 's/^(\s+language:\s*).*/\1zh/' "$CFG"
    ok "config.yaml: display.language 已设为 zh"
  else
    warn "$CFG 中未找到 display.language，请手工在 display: 下添加 'language: zh'"
  fi
else
  warn "未找到 $CFG，跳过语言默认值设置"
fi

# --- 5) 构建前端 ---
WEB="$TARGET/web"
if [ -d "$WEB/node_modules" ]; then
  info "构建前端（npm run build）…"
  ( cd "$WEB" && npm run build ) || die "前端构建失败"
  ok "前端构建完成"
else
  warn "$WEB/node_modules 不存在，跳过构建。请先执行: cd $WEB && npm install && npm run build"
fi

cat <<EOF

$(printf '\033[32m安装完成\033[0m')

下一步:
  1. 重启 dashboard 使其加载新构建产物
  2. 浏览器强制刷新（Ctrl+Shift+R），否则旧 bundle 会被缓存

回滚:
  $HERE/uninstall-zh.sh $TARGET $STAMP
EOF