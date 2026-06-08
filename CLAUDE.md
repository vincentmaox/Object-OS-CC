# ProjectOS — Claude Code 导航文档

ProjectOS 是用户「茅弘毅 / 虚空建筑师」的多项目跟踪与远程控制系统，位于 `D:\ClaudeCodeProjects\_ProjectOS\`。本文件是 Claude Code 进入本仓库时的第一阅读节点。

## 项目定位

把散落在 `D:\ClaudeCodeProjects\` 下的所有子项目（NuclearPowerAI、docreview-ai、ai-router-48h 等）统一扫描、状态化、推到飞书，实现「频域决策 + 72h MVA + 零持仓」工作流的自动化基础设施。

## 架构总览

```
项目扫描层    project_agent.py    ──┐
                                    ├──> data/registry.json (真值)
飞书同步层    feishu_sync.py      ──┤
                                    ├──> 飞书 Bot 消息（晨报/卡点）
远程驱动层    sdk_bot_server.py   ──┤    飞书多维表格
            （SDK + 卡片权限中继）   │    Obsidian 看板
                                    │
思考池层      thoughts/inbox.md   ──┘
            thought_inspector.py
            （每周一 09:07 巡检）
```

## 核心组件

| 文件 | 职责 |
|---|---|
| `agent/project_agent.py` | 扫描所有 D:\ClaudeCodeProjects 下子项目 → 写 registry.json + 生成 Obsidian 看板 |
| `agent/feishu_sync.py` | 飞书同步引擎（晨报/卡点/多维表格/文档导入）。`send-report` / `alert` / `sync-base` / `sync-docs` 四个命令 |
| `agent/sdk_bot_server.py` | **当前主 Bot**。claude-agent-sdk + lark WS + 卡片权限中继。NSSM 服务名 `SDKBotServer` |
| `agent/feishu_cards.py` | 飞书交互卡片模板（permission / morning / status / resolved） |
| `agent/feishu_card_router.py` | 卡片回调路由（register / await_decision / handle_card_action / resolve_by_text） |
| `agent/permission_rules.py` | 工具权限白/黑名单引擎（含 `allow_thoughts_write` 思考池放行规则） |
| `agent/thought_inspector.py` | 思考池周巡检脚本（沉睡 14d / 反复 ≥3 / git 自然落地三档分析） |
| `agent/cc_bot_server.py` | 旧版 Bot（保留作降级路径，**不再开服务**） |
| `agent/daily_projectos_report.py` | 每日定时任务入口（9:07 触发 scan+report） |
| `data/registry.json` | 项目状态真值表（不入 git，含本地路径） |
| `data/feishu-base-config.json` | 飞书多维表格绑定（不入 git） |
| `thoughts/inbox.md` | 思考池入口（Bot 自动追加，含 `BOT_APPEND_BELOW_THIS_LINE` 锚点） |
| `thoughts/active.md / watching.md / killed.md` | 决断后归类 |
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

**Day3 完成（2026-06-07）：** SDK Bot 端到端跑通 + NSSM 服务化 + 思考池建成。详见 `docs/journal/2026-06-07-day3-sdk-bot-end-to-end.md` 和 `docs/journal/2026-06-07-day3-evening-postmortem.md`。

**已废弃方案：** Ceeon/claude-channel-feishu Channel 协议方案在火山方舟代理后端不可用（`--dangerously-load-development-channels` 被代理忽略），保留 clone 仅作卡片 JSON 参考。

**Day4+ 候选：** 晨报推交互卡片（All-in/Watch/Kill 按钮回写 registry）、流式回复、长任务可中断按钮、思考池巡检改卡片决断。

## 🔒 安全约束（继承全局）

全局 `~/.claude/CLAUDE.md` 已写入「密钥安全」硬约束章节。在本仓库工作时**额外注意**：
- `agent/cc_bot.env` 含 ANTHROPIC_AUTH_TOKEN / FEISHU_APP_SECRET — **禁止 Read 整文件、cat、head、tail**
- 验证字段存在：`grep -c FIELD_NAME agent/cc_bot.env`
- 验证字段非空：`python -c "import os; print(bool(os.environ.get('FIELD')))"`（先 source 或在已 load 的 shell 跑）
- Edit cc_bot.env 必须用非密钥行做 old_string 锚点

## 思考池工作流

用户发 "我有个想法 / 我有个思考 / 我在想 / 突然想到" 触发：
1. Bot 反问确认项目名（registry 真实项目模糊匹配）+ 是否记录
2. 确认后在 `thoughts/inbox.md` 的 `<!-- BOT_APPEND_BELOW_THIS_LINE -->` 下追加一行
   格式：`[ISO 时间戳] [项目名] 用户原话浓缩`
3. 每周一 09:07 `thought_inspector.py` 自动巡检（schtasks 任务 `ProjectOS_ThoughtInspector_Weekly`，跑当前 User 权限，需登录态）
4. 用户决断 → 手工或 Bot 协助移到 active / watching / killed

`permission_rules.allow_thoughts_write` 规则自动放行思考池写入（不弹卡片）。

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

- **每日 9:07** — schtasks 任务 `ProjectOS_DailyReport`（取代会过期的 CronCreate）触发 scan + send-report + alert
- **每周一 9:07** — schtasks 任务 `ProjectOS_ThoughtInspector_Weekly` 触发思考池巡检

## 相关导航

- `README.md` — 面向人类的快速上手
- `SETUP_GUIDE.md` — 初始安装步骤
- `docs/journal/` — 项目工作日志（决策/动作/踩坑）
  - `2026-06-07-day3-sdk-bot-end-to-end.md` — Day3 主体（SDK Bot 端到端）
  - `2026-06-07-day3-evening-postmortem.md` — Day3 晚段（NSSM 服务化 / 密钥事故 / 思考池建成）
