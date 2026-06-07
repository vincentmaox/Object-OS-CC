# ProjectOS Changelog

按倒序记录主要演进。完整决策细节在 `journal/` 下按日期归档。

## [Unreleased] - 2026-06-07

### Added
- 初始化 git 仓库 + 本地版本管理
- `CLAUDE.md` Claude Code 导航文档
- `README.md` 用户视角快速上手
- `docs/journal/` 工作日志机制
- Clone [Ceeon/claude-channel-feishu](https://github.com/Ceeon/claude-channel-feishu) 到 `D:/ClaudeCodeProjects/`（独立仓库）
- 启动 Channel 协议方案 Day1（理论验证）
- Day2: Bun 1.3.14 装好；Ceeon server.ts standalone 跑通
- Day2: `agent/sdk_smoke_test.py` — claude-agent-sdk方案验证脚本
- Day2: `docs/journal/2026-06-07-day2-channel-blocked-sdk-validated.md` — Day2完整记录
- Day3: `agent/feishu_cards.py` — 三种卡片模板（permission/morning/status）+ resolved 替换卡
- Day3: `agent/feishu_card_router.py` — `PermissionRouter` 类（register/await_decision/handle_card_action/resolve_by_text），含 6 个单元测试全绿
- Day3: `agent/sdk_bot_server.py` — 新版 Bot 主程，asyncio 主循环 + lark WS worker 双线程模型
- Day3: `agent/permission_rules.py` — 规则引擎（白名单只读工具/git 只读/dry-run + 黑名单 rm-rf root/force push main）
- Day3: `agent/card_render_test.py` + `agent/test_card_router.py` — 真机渲染 + 路由单元测试
- Day3: `agent/install_sdk_bot_service.bat` — NSSM 安装脚本（自动卸载旧 CCBotServer 避免 WS 冲突）
- Day3: `docs/journal/2026-06-07-day3-sdk-bot-end-to-end.md` — Day3 完整记录

### Discovered (重要发现)
- ❌ **Channel协议在第三方API代理后端不可用**：`--dangerously-load-development-channels` 被代理后端忽略，需Anthropic官方API的 `tengu_harbor_ledger` 服务端白名单
- ✅ **claude-agent-sdk (Python v0.2.93) 在火山方舟代理下完整可用**：can_use_tool异步callback验证通过，工具实际执行落地
- ✅ 关键配置：`setting_sources=[]` 隔离user级allowlist，否则CLI直接放行tool_use不问SDK
- ✅ Day3: lark-cli.cmd 在 Windows 上吃 interactive 卡片 JSON 的双引号 → 改 `node + run.js` 直调 shell=False 绕过 cmd.exe
- ✅ Day3: lark 回调在 worker 线程里，asyncio.Event 必须用 `loop.call_soon_threadsafe(event.set)` 派发

### Fixed
- `feishu_sync.py send_blocker_alert` 身份 bug：`--text` 模式触发 `im:message.send_as_user` scope 缺失 → 改用 `send_rich_message`（post 类型，bot 身份）
- `feishu_sync.py` 新增 `send_interactive_card` 方法（独立 subprocess 路径，绕过 cmd.exe）

### Day3 验证（2026-06-07 真机联调通过）
- 场景1: "各项目进展情况" → SDK 触发 PowerShell 跑 project_agent.py → 卡片点 Allow → 176s 完成 8 项目盘点回复
- 场景2: "你能干啥..." → 纯对话无工具 → 46.8s 直接回复
- 场景3: 多轮上下文窗口生效（第二轮基于第一轮的盘点回答）

### Pending (Day4+)
- 装 NSSM 服务自启：`install_sdk_bot_service.bat`（管理员运行）
- 改造每日 9:07 定时任务推晨报卡片（不再纯文本）
- 晨报卡片 All-in/Watch/Kill 按钮回写 registry.json
- 流式回复（assistant 文本块到达即更新状态卡片）
- 长任务可中断按钮

### Decision Log
- **放弃 Ceeon Channel方案** — 不可用于火山方舟代理环境，但保留clone作卡片JSON参考
- **采用方案D（SDK+现Bot）** — 端到端smoke test验证通过，预计10h完成 → 实际 Day3 一天完成
- **保留 cc_bot_server.py** — 作为降级路径，install_sdk_bot_service.bat 自动停旧服务避免 APP_ID WebSocket 冲突

## [Prior] - 2026-06-01 ~ 2026-06-06

- 建立 `project_agent.py` 项目扫描器 + Obsidian 看板生成
- 建立 `feishu_sync.py` 飞书同步引擎（晨报/卡点/多维表格）
- 建立 `cc_bot_server.py` 飞书 Bot 双向通信（WebSocket）
- NSSM 服务化 CC 小助手 Bot
- 注册每日 9:07 定时任务（CronCreate）
- 首批入库 7 个项目（NuclearPowerAI/docreview-ai/ai-router-48h 等）
- 完成 PhysicsAI-Research 项目 Kill 归档
