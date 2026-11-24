# hermes-dashboard-zh

Hermes Agent Web Dashboard 简体中文补丁 — 让内页 UI 不再回落英文，并**跟得上上游版本迭代**。

官方 `web/src/i18n/zh.ts` 只覆盖 UI chrome，且长期缺键；页面组件里的按钮、提示、状态标签是硬编码英文，完全不经过 i18n。这个仓库把两者都补上，并提供一套升级后仍能重放的机制。

## 效果

| 范围 | 说明 |
|---|---|
| 语言包 | `zh.ts` 补齐至与 `en.ts` 同键数（919 / 919），`ui` 段新增 152 键 |
| 内页组件 | 33 个文件、186 处文案接入 `t.ui.*` |
| 默认语言 | 后端注入 `window.__HERMES_LOCALE__`，首屏即为中文（此前 `getInitialLocale()` 硬编码回落 `en`） |
| 导航/标题 | `App.tsx` 6 个无 `labelKey` 的导航项补齐；路由标题映射补 9 条 |
| 相对时间 | `timeAgo`/`isoTimeAgo` 输出「3 小时前」而非「3h ago」 |
| 网关横幅 | 后端英文拼接的 reason 由前端映射为中文 |

其他 15 种语言（`zh-hant`、`ja`、`ko` 等）缺同样的键，但依赖 `mergeTranslations` 逐键回退英文，不会显示 `undefined`，因此本补丁只改 `en`/`zh`。

## 安装

```bash
git clone https://github.com/talwayh1/hermes-dashboard-zh.git
cd hermes-dashboard-zh
chmod +x install-zh.sh uninstall-zh.sh verify-zh.sh

./install-zh.sh /opt/hermes
```

安装后**重启 dashboard 并强制刷新浏览器**（Ctrl+Shift+R），否则旧 bundle 仍被缓存。

### 两种策略，自动选择

| 策略 | 触发条件 | 说明 |
|---|---|---|
| `diff` | 上游与基线一致 | 精确应用 `patches/hermes-zh-web.patch`，最快 |
| `semantic` | 上游已改动 | 以 `en.ts` 为基准重放 `pack/semantic-pack.json` 里的译文 |

语义重放**不依赖行号**：上游改了文件结构、删了组件、重排了键，冲突只表现为「缺键」而不是「补丁失败」。缺的键自动回退英文，页面不会坏。

## 校验 / 回滚

```bash
./verify-zh.sh /opt/hermes     # 键数、ui 段、注入变量、tsc
./uninstall-zh.sh /opt/hermes  # 自动选最新备份
```

## 自动跟踪上游

`.github/workflows/track-upstream.yml` 每天 02:00 UTC 运行：

1. 查 `NousResearch/hermes-agent` 最新 release
2. 拉该版本真实的 `en.ts` / `zh.ts` / `types.ts`
3. 跑语义重放 **dry-run**，统计新增/过期键
4. 新增键 ≤ 30 → 实际重放、生成 `patches/replayed-<tag>.patch`、**自动提交并发 Release**
5. 新增键 > 30 → 开 Issue 要求人工补译文（不盲目发布）

已发布：[releases](https://github.com/talwayh1/hermes-dashboard-zh/releases)（tag 形如 `zh-v0.23.3`）。

也可手动指定版本：

```bash
gh workflow run "Track upstream and replay" -f upstream_ref=v0.23.3
```

### 实测记录

在 v0.23.3（比补丁基线新很多，含文件删除与结构变化）上：

| 指标 | 结果 |
|---|---|
| 精确 diff 应用 | ❌ 多处 conflict，2 个文件已不存在 |
| 语义重放 | ✅ 444 处合并，缺键 116 → 6 |
| 生成补丁 | 687 行 |

## 仓库结构

```
install-zh.sh              安装（diff 优先，失败降级语义重放）
uninstall-zh.sh            回滚（备份优先，缺失时反向应用补丁）
verify-zh.sh               校验 6 项 + tsc
patches/hermes-zh-web.patch  精确补丁（基线 e8639fd4312）
patches/BASE_COMMIT.txt    补丁基线 commit
patches/replayed-*.patch   CI 为各上游版本生成的补丁
pack/semantic-pack.json    语义包：zh 译文全量 + ui 段 + 引用映射
pack/upstream-tag.txt      已跟踪的上游版本
scripts/parse-locale.js    用 TS 编译器 API 解析 locale（不靠正则猜）
scripts/build-semantic-pack.py  从已打补丁的源码生成语义包
scripts/replay-zh.py       把语义包重放到任意上游版本
scripts/relink-ui.py       组件英文重新接入 t.ui.*
```

## 已知边界

- 不翻译品牌名、模型名、技能名、命令行、文件路径、平台名（`Hermes`、`MCP`、`Webhook`、`systemd`、`deepseek-*`）
- Cron 页的任务状态枚举（`passed` / `scheduled` / `no agent` / `repeat: forever`）与后端拼接的调度描述尚未映射，需前端枚举层改造
- 语义重放后上游新增键会回退英文，`verify-zh.sh` 会列出清单
- `relink-ui.py` 只替换「整段文本完全等于 ui 英文原文」的情形，漏网项需人工判断（宁可漏，不可误伤）

## 环境

- Hermes Agent v0.21.2 起（v0.23.3 实测可重放）
- Node.js ≥ 18
- 解析脚本需要 TypeScript **5.x**（7.x 包结构变化，`createSourceFile` 不再直接导出）
- `web/node_modules` 存在才能构建前端；缺失时脚本跳过构建并提示

## 许可

MIT。补丁内容源自对 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 的修改，遵循其 MIT 许可与归属。