# hermes-dashboard-zh

Hermes Agent Web Dashboard 简体中文补丁 — 让内页 UI 不再回落英文。

官方 `web/src/i18n/zh.ts` 只覆盖 UI chrome，且长期缺键（v0.21.x 时 `en.ts` 796 键 / `zh.ts` 681 键，缺 115）；页面组件里的按钮、提示、状态标签是硬编码英文，完全不经过 i18n。这个补丁把两者都补上。

## 效果

| 范围 | 说明 |
|---|---|
| 语言包 | `zh.ts` 补齐至与 `en.ts` 同键数，`ui` 段新增 152 键 |
| 内页组件 | 33 个文件、179 处硬编码英文接入 `t.ui.*` |
| 默认语言 | 后端注入 `window.__HERMES_LOCALE__`，首屏即为中文（此前 `getInitialLocale()` 硬编码回落 `en`） |
| 导航/标题 | `App.tsx` 6 个无 `labelKey` 的导航项补齐；路由标题映射补 9 条 |
| 相对时间 | `timeAgo`/`isoTimeAgo` 输出「3 小时前」而非「3h ago」 |
| 网关横幅 | 后端英文拼接的 reason 由前端映射为中文 |

其他 15 种语言（`zh-hant`、`ja`、`ko` 等）缺同样的键，但依赖 `mergeTranslations` 逐键回退英文，不会显示 `undefined`，因此本补丁只改 `en`/`zh`。

## 安装

```bash
git clone <this-repo> hermes-dashboard-zh
cd hermes-dashboard-zh
chmod +x install-zh.sh uninstall-zh.sh verify-zh.sh

# 默认查找 ~/hermes，也可显式指定
./install-zh.sh /opt/hermes
```

脚本会：备份受影响文件 → 三方合并应用补丁 → 设置 `display.language=zh` → 构建前端。

安装后**重启 dashboard 并强制刷新浏览器**（Ctrl+Shift+R），否则旧 bundle 仍被缓存。

## 校验

```bash
./verify-zh.sh /opt/hermes
```

检查注入变量、键数、`ui` 段、硬编码残留，并跑一次 `tsc --noEmit`。

## 回滚

```bash
./uninstall-zh.sh /opt/hermes            # 自动选最新备份
./uninstall-zh.sh /opt/hermes 20261124-144800   # 指定备份
```

优先从 `.zh-pack-backup-<stamp>/` 恢复；备份不在时反向应用补丁。

## 上游升级后

补丁基线是 `e8639fd4312`（v0.21.2）。上游改动命中同一区域时，`install-zh.sh` 会用 `git apply -3` 三方合并；冲突会被明确列出并中止，不会静默写坏文件。

升级流程建议：

```bash
git -C /opt/hermes pull
git -C /opt/hermes status --porcelain   # 确认是否被上游覆盖
./install-zh.sh /opt/hermes
./verify-zh.sh /opt/hermes
```

## 已知边界

- 不翻译品牌名、模型名、技能名、命令行、文件路径、平台名（`Hermes`、`MCP`、`Webhook`、`systemd`、`deepseek-*`）
- 任务卡片里的状态枚举（`passed` / `scheduled` / `no agent` / `repeat: forever`）与后端拼接的调度描述尚未映射，需前端枚举层改造
- 极少数动态内容由后端返回英文，前端仅做展示，未在此补丁范围内

## 环境

- Hermes Agent v0.21.2（`0.22.5+3271` 亦可，补丁区域未变）
- Node.js ≥ 18（构建前端）
- 依赖 `web/node_modules` 存在才能构建；缺失时脚本跳过构建并提示

## 许可

MIT。补丁内容源自对 NousResearch/hermes-agent 的修改，遵循其 MIT 许可与归属。