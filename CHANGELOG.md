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

### Discovered (重要发现)
- ❌ **Channel协议在第三方API代理后端不可用**：`--dangerously-load-development-channels` 被代理后端忽略，需Anthropic官方API的 `tengu_harbor_ledger` 服务端白名单
- ✅ **claude-agent-sdk (Python v0.2.93) 在火山方舟代理下完整可用**：can_use_tool异步callback验证通过，工具实际执行落地
- ✅ 关键配置：`setting_sources=[]` 隔离user级allowlist，否则CLI直接放行tool_use不问SDK

### Fixed
- `feishu_sync.py send_blocker_alert` 身份 bug：`--text` 模式触发 `im:message.send_as_user` scope 缺失 → 改用 `send_rich_message`（post 类型，bot 身份）

### Pending
- Day3: 改造 `cc_bot_server.py` → 新版 `sdk_bot_server.py`（SDK大脑+飞书外壳）
- Day3: 写飞书卡片模板 + `can_use_tool` 飞书round-trip
- Day3-4: 流式卡片更新 + 联调

### Decision Log
- **放弃 Ceeon Channel方案** — 不可用于火山方舟代理环境，但保留clone作卡片JSON参考
- **采用方案D（SDK+现Bot）** — 端到端smoke test验证通过，预计10h完成

## [Prior] - 2026-06-01 ~ 2026-06-06

- 建立 `project_agent.py` 项目扫描器 + Obsidian 看板生成
- 建立 `feishu_sync.py` 飞书同步引擎（晨报/卡点/多维表格）
- 建立 `cc_bot_server.py` 飞书 Bot 双向通信（WebSocket）
- NSSM 服务化 CC 小助手 Bot
- 注册每日 9:07 定时任务（CronCreate）
- 首批入库 7 个项目（NuclearPowerAI/docreview-ai/ai-router-48h 等）
- 完成 PhysicsAI-Research 项目 Kill 归档
