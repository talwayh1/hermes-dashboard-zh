#!/usr/bin/env bash
# 安装 Hermes Dashboard 中文补丁（语义化重放版，抗上游升级）
#
# 用法:
#   ./install-zh.sh [HERMES_DIR]
#
# 与旧版 diff 方案的区别：
#   - 不依赖行号，上游大改后仍可重放
#   - 先试 diff（精确、最快），失败自动降级为语义重放
#   - 语义重放以 en.ts 为基准对齐 zh.ts，冲突只体现为「缺键」而非「行错位」
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-${HERMES_DIR:-$HOME/hermes}}"

info() { printf '\033[36m→ %s\033[0m\n' "$*"; }
ok()   { printf '\033[32m✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[33m! %s\033[0m\n' "$*"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

[ -d "$TARGET/web/src/i18n" ] || die "不是 Hermes 源码目录: $TARGET"

CUR="$(git -C "$TARGET" rev-parse --short HEAD 2>/dev/null || echo none)"
BASE="$(cat "$HERE/patches/BASE_COMMIT.txt" 2>/dev/null | cut -c1-12 || echo unknown)"
info "目标: $TARGET"
info "当前 HEAD: $CUR / 补丁基线: $BASE"

STAMP="$(date +%Y%m%d-%H%M%S)"
BAK="$TARGET/.zh-pack-backup-$STAMP"

# ---------- 备份 ----------
backup_files() {
  local list="$1"
  info "备份 $list 到 $BAK"
  mkdir -p "$BAK"
  ( cd "$TARGET" && printf '%s\n' "$list" | while IFS= read -r f; do
      [ -n "$f" ] && [ -f "$f" ] && { mkdir -p "$BAK/$(dirname "$f")"; cp -p "$f" "$BAK/$f"; }
    done )
  ok "备份 $(find "$BAK" -type f | wc -l) 个文件"
}

# ---------- 1) 优先尝试精确 diff ----------
PATCH="$HERE/patches/hermes-zh-web.patch"
STRATEGY=""
if [ -f "$PATCH" ] && git -C "$TARGET" apply --check "$PATCH" >/dev/null 2>&1; then
  FILES="$(cd "$TARGET" && grep '^diff --git' "$PATCH" | sed -E 's#^diff --git a/(.*) b/.*#\1#')"
  backup_files "$FILES"
  git -C "$TARGET" apply "$PATCH"
  STRATEGY="diff"
  ok "补丁已精确应用（diff 模式）"
else
  # ---------- 2) 降级：语义重放 ----------
  warn "diff 无法直接应用（上游已改动），切换到语义重放"
  [ -f "$HERE/pack/semantic-pack.json" ] || die "缺少 pack/semantic-pack.json"

  # 备份 locale + 组件
  FILES="$(cd "$TARGET" && { git diff --name-only HEAD -- web/src 2>/dev/null; \
      grep -rl 't\.ui\.' --include=*.tsx web/src 2>/dev/null; } | sort -u)"
  FILES="$(printf '%s\n' "$FILES" | grep -v '^$' || true)"
  backup_files "$FILES"

  export HERMES_DIR="$TARGET"
  HERMES_TYPESCRIPT="${HERMES_TYPESCRIPT:-$TARGET/node_modules/typescript}"
  export HERMES_TYPESCRIPT
  if [ ! -d "$HERMES_TYPESCRIPT" ]; then
    HERMES_TYPESCRIPT="$TARGET/web/node_modules/typescript"
    export HERMES_TYPESCRIPT
  fi
  [ -d "$HERMES_TYPESCRIPT" ] || die "找不到 typescript 模块（构建前端需要）"

  info "重放中文翻译到 zh.ts …"
  python3 "$HERE/scripts/replay-zh.py" "$TARGET" "$HERE/pack/semantic-pack.json" \
    | tee /tmp/zh-replay-report.json | grep -E '"(zh_changes|zh_keys_after|missing_after|upstream_new_keys|stale_keys)"' || true

  # 重放组件里的 t.ui 接入
  if [ -f "$HERE/scripts/relink-ui.py" ]; then
    info "重新接入组件文案 …"
    python3 "$HERE/scripts/relink-ui.py" "$TARGET" "$HERE/pack/semantic-pack.json" || warn "组件重链有告警"
  fi
  STRATEGY="semantic"
  ok "语义重放完成（struct 相近，缺键会自动回退英文）"
fi

# ---------- 3) 设置默认语言 ----------
CFG="${HERMES_CONFIG:-$HOME/.hermes/config.yaml}"
if [ -f "$CFG" ]; then
  if grep -qE '^\s+language:\s*' "$CFG"; then
    sed -i -E 's/^(\s+language:\s*).*/\1zh/' "$CFG"
    ok "config.yaml: display.language=zh"
  else
    warn "$CFG 无 display.language，请手工在 display: 下添加 'language: zh'"
  fi
fi

# ---------- 4) 构建 ----------
WEB="$TARGET/web"
if [ -d "$WEB/node_modules" ]; then
  info "构建前端 …"
  ( cd "$WEB" && npm run build ) >/tmp/zh-build.log 2>&1 || { tail -20 /tmp/zh-build.log; die "构建失败"; }
  ok "前端构建完成"
else
  warn "$WEB/node_modules 缺失，跳过构建（先执行 npm install）"
fi

cat <<EOF

$(printf '\033[32m安装完成\033[0m')  策略: $STRATEGY

下一步:
  1. 重启 dashboard
  2. 浏览器 Ctrl+Shift+R 强制刷新

回滚: $HERE/uninstall-zh.sh $TARGET $STAMP

注意: 语义重放模式下，上游新增的键会回退英文。
执行 ./verify-zh.sh 查看未翻译键清单。
EOF