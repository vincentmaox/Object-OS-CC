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

### Fixed
- `feishu_sync.py send_blocker_alert` 身份 bug：`--text` 模式触发 `im:message.send_as_user` scope 缺失 → 改用 `send_rich_message`（post 类型，bot 身份）

### Pending
- 飞书 App 新增权限：`im:resource`、`im:message.reactions:write`、事件 `card.action.trigger`
- 安装 Bun runtime（`winget install Oven-sh.Bun`）
- 用户确认后 push 到 https://github.com/vincentmaox/Object-OS-CC

## [Prior] - 2026-06-01 ~ 2026-06-06

- 建立 `project_agent.py` 项目扫描器 + Obsidian 看板生成
- 建立 `feishu_sync.py` 飞书同步引擎（晨报/卡点/多维表格）
- 建立 `cc_bot_server.py` 飞书 Bot 双向通信（WebSocket）
- NSSM 服务化 CC 小助手 Bot
- 注册每日 9:07 定时任务（CronCreate）
- 首批入库 7 个项目（NuclearPowerAI/docreview-ai/ai-router-48h 等）
- 完成 PhysicsAI-Research 项目 Kill 归档
