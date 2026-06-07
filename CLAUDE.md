# ProjectOS — Claude Code 导航文档

ProjectOS 是用户「茅弘毅 / 虚空建筑师」的多项目跟踪与远程控制系统，位于 `D:\ClaudeCodeProjects\_ProjectOS\`。本文件是 Claude Code 进入本仓库时的第一阅读节点。

## 项目定位

把散落在 `D:\ClaudeCodeProjects\` 下的所有子项目（NuclearPowerAI、docreview-ai、ai-router-48h 等）统一扫描、状态化、推到飞书，实现「频域决策 + 72h MVA + 零持仓」工作流的自动化基础设施。

## 架构总览

```
项目扫描层    project_agent.py  ──┐
                                  ├──> data/registry.json (真值)
飞书同步层    feishu_sync.py    ──┤
                                  ├──> 飞书 Bot 消息（晨报/卡点）
远程驱动层    cc_bot_server.py  ──┘     飞书多维表格
                                        Obsidian 看板
            （计划替换为 Ceeon/claude-channel-feishu）
```

## 核心组件

| 文件 | 职责 |
|---|---|
| `agent/project_agent.py` | 扫描所有 D:\ClaudeCodeProjects 下子项目 → 写 registry.json + 生成 Obsidian 看板 |
| `agent/feishu_sync.py` | 飞书同步引擎（晨报/卡点/多维表格/文档导入）。`send-report` / `alert` / `sync-base` / `sync-docs` 四个命令 |
| `agent/cc_bot_server.py` | 飞书 Bot WebSocket 服务（飞书消息→本机claude→回复推回）。**计划下线** |
| `agent/daily_projectos_report.py` | 每日定时任务入口（9:07 触发 scan+report） |
| `data/registry.json` | 项目状态真值表（不入 git，含本地路径） |
| `data/feishu-base-config.json` | 飞书多维表格绑定（不入 git） |
| `templates/` | 项目笔记模板 |
| `archive/` | 已 Kill 项目归档（不入 git） |
| `_inbox/` | 散落 md 自动归类区（不入 git） |

## 关键约束（不要踩坑）

### 飞书 lark-cli
- **没有 `--format json`** — lark-cli 默认输出 JSON
- 命令名：`+base-create`（不是 +app-create）、`+record-batch-create`（不是 +records-create）
- `--base-token`（不是 `--app-token`）
- 字段 type 是字符串 `"text"/"number"/"select"/"datetime"/"link"/"checkbox"`
- record-batch-create 用 `--json` 传 `{"fields":[...], "rows":[[...]]}`
- link 字段值是 `[{"id": rec_id}]` 不是 `[rec_id]`

### 飞书 Bot 身份
- 自动化消息**一律走 bot 身份**（`--as bot`）。`im:message.send_as_user` 是受限 scope，普通授权拿不到
- `send_message` 走 `--text` 模式时 lark-cli 可能强制 user 身份导致 scope 报错 → 改用 `send_rich_message`（post 类型，bot 身份稳定）
- 任何飞书后台改动（权限/事件订阅）**必须发新版本**否则不生效

### Windows subprocess
- `subprocess shell=True` + 含 JSON 的 arg 会被 cmd.exe 重解析剥引号 → 必须手动转义 `"`→`\"`
- 异步协程里 stdout 默认 buffered → 必须 `sys.stdout = io.TextIOWrapper(..., write_through=True)`
- 路径用正斜杠或转义反斜杠

### CC 小助手 Bot 已知踩坑（cc_bot_server.py）
1. 飞书后台**三步必须全做**：权限管理 + 事件订阅 + **「版本管理与发布」创建新版本**（最后这步最常忘）
2. `EventDispatcherHandler.builder("", "")` 空 token，WebSocket 走 `_do_without_validation`
3. 回调签名 `(data)` 单参，从 `data.event.message` 取消息
4. 飞书单条消息上限 ~30k 字符 → 长输出按 4000 分片，加 `[i/n]` 前缀

## 当前演进方向

**正在做：** 用 [Ceeon/claude-channel-feishu](https://github.com/Ceeon/claude-channel-feishu) 替换自写 `cc_bot_server.py`，获得交互卡片 + 移动端权限授权能力。详见 `docs/journal/`。

**为什么换：** 现有 Bot 纯文本，缺按钮卡片、缺工具权限弹窗中继；Ceeon 用 Claude Code 官方 Channel 协议（MCP experimental capability），原生支持。

**风险：** `--dangerously-load-development-channels` 是 dev-only flag，Anthropic 未承诺长期稳定 → 保留 cc_bot_server.py 做降级路径。

## 关键凭据（在 User env，不入 git）

- `FEISHU_APP_ID` = `cli_aa97967fa3b81cc7`
- `FEISHU_APP_SECRET` = （User env）
- `FEISHU_ALLOWED_OPEN_IDS` = `ou_59a5d4b0cc115a66295961a1aec66a9e`（茅弘毅）
- `OBSIDIAN_API_KEY` / `OBSIDIAN_PORT=27123`

## 飞书资源

- App ID: `cli_aa97967fa3b81cc7`
- 用户 open_id: `ou_59a5d4b0cc115a66295961a1aec66a9e`
- 多维表格 base_token: `XZrSbVFATaiwcRsmAgocRin4n3M`
- 主表 table_id: `tblUseYoGnHeGvRL`（项目总览，11 字段）
- 表格 URL: https://voidarchitect.feishu.cn/base/XZrSbVFATaiwcRsmAgocRin4n3M

## 每日例行

CronCreate 注册了每日 9:07 触发：scan + send-report + alert。7 天自动过期，需重激活。

## 相关导航

- `README.md` — 面向人类的快速上手
- `SETUP_GUIDE.md` — 初始安装步骤
- `docs/journal/` — 项目工作日志（决策/动作/踩坑）
