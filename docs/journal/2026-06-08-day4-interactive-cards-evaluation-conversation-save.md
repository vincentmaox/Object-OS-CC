# 2026-06-08 Day4 — 晨报交互卡片 + 项目评估 + 对话自动保存

> Day3 晚段完成 SDK Bot 服务化 + 思考池。Day4 在此基础上推进三个方向：晨报从纯文本升级为交互卡片（MVA 按钮）、复盘加入项目评估与夸夸、对话自动存档防窗口意外丢失。

---

## 一句话

晨报推飞书交互卡片（8 张全部送达，每项目附 All-in/Watch/Kill 按钮），按钮回调写回 registry.json 链路真通；daily_recap 加项目评估三段式（诊断/建议/夸夸）覆盖所有活跃项目；Stop hook 自动保存对话轮次到本地文件，下次新会话生效。

---

## 时间线

### 18:00 - 19:30 · 三线并行推进

**起点**：上个 Claude Code 会话因另一个项目意外关闭窗口，用户问"今天落地了吗"。

**发现**：
- `ProjectOSDailyReport` schtasks 任务存在且今早 9:07 正常跑了（不是 `ProjectOS_DailyReport`）
- `ProjectOS_DailyRecap_Evening` 已注册，今晚 22:57 首次触发
- `SDKBotServer` 服务 Running + Automatic
- 6 个修改文件 + 5 个新文件全部未 commit（裸奔）

**动作 1 — 保护成果**：先 commit Day3 晚段全部 16 文件（`92314ce`）

**动作 2 — 项目评估增强 daily_recap.py**：
- 新增 `build_eval_prompt()` — 单项目 LLM 评估 prompt（诊断/建议/夸夸三段式）
- 新增 `eval_one()` / `_fallback_eval()` — LLM 或模板双模式
- 新增 `collect_all_active()` — 遍历所有活跃项目（不限于今日有动静）
- `build_report()` 重构 — 日报 + 静默项目评估 + 今日项目评估三段
- no-llm dry-run 测试通过（8 个项目均出评估）

**动作 3 — 对话自动保存**：
- 研究确认 Claude Code `Stop` hook 完全可行：stdin 有 `last_assistant_message`，`UserPromptSubmit` hook 有用户消息
- 写 `agent/save_conversation_turn.py` — Stop hook 脚本，保存到 `conversation_log/YYYY-MM-DD.md`
- 创建 `.claude/settings.json` — 注册 UserPromptSubmit + Stop 双 hooks
- `.gitignore` 加 `conversation_log/`
- 注意：hooks 在下次新会话才生效

### 19:30 - 20:00 · 晨报交互卡片全链路

**已有基础设施**：
- `feishu_cards.py:build_morning_report_card()` — 卡片模板已有 All-in/Watch/Kill 三按钮
- `feishu_card_router.py:_handle_non_permission_action()` — 桩代码已有，只回 toast
- `feishu_sync.py:send_interactive_card()` — node 直调绕过 cmd.exe 引号问题

**新增**：
1. `feishu_sync.py:send_daily_report_cards()` — 遍历活跃项目，每项目一张卡片推飞书
2. `feishu_sync.py:update_project_status()` — MVA 决策写回 registry.json（all_in→活跃/watch→观望/kill→已归档 + archived_at）
3. `feishu_card_router.py:_handle_non_permission_action()` — 接通 `update_project_status()`，点按钮即写回 + 返回替换卡片
4. `feishu_sync.py` CLI 新增 `send-cards` / `update-status` 命令
5. `daily_projectos_report.py` 晨报改用 `send-cards`（取代 `send-report`）

**验证**：
- `feishu_sync.py send-cards ou_59a5d4b0...` → 8 张卡片发送成功，0 失败
- `feishu_sync.py update-status TexasPhilosopher watch` → registry 写入 `mva_decision=Watch, status=观望`，确认后恢复 All-in

### 20:00 · 文档同步

- CLAUDE.md 架构图加复盘层 + 对话存档层
- 核心组件表更新（feishu_sync 命令列表、daily_recap、save_conversation_turn）
- 每日例行加 22:57 复盘
- Day4 完成标记
- CHANGELOG 新增 Day4 条目

---

## 关键决策

- **晨报从纯文本改交互卡片** — send-cards 取代 send-report，每个项目独立卡片 + MVA 按钮。旧 send-report 保留作为降级路径。
- **MVA 按钮直接写回 registry** — 不是只 toast，是 `update_project_status()` 真改文件。点 Kill 会设 `archived_at`。
- **项目评估覆盖所有活跃项目** — 不只今日有动静的。静默项目更需要评估（可能需要激活或归档）。
- **对话保存用 Stop hook** — 不是解析 JSONL 文件，而是 Claude Code 内置 hook 机制。stdin JSON 有 `last_assistant_message`，比解析 transcript 更可靠。
- **daily_recap LLM 模式卡住** — 8 个项目并行调 SDK 超时。no-llm 模式秒完。后续需加 per-project timeout 或改串行。

---

## 已知问题 / 后续

1. **daily_recap LLM 模式超时** — 需加 per-project asyncio timeout（比如 30s），失败 fallback 模板
2. **对话 hook 未在本会话测试** — 下次新会话才生效，需验证
3. **卡片按钮的安全校验** — 当前任何人点按钮都能改 registry，需校验 `operator_open_id` 是否在 `FEISHU_ALLOWED_OPEN_IDS` 白名单内
4. **流式回复** — 仍是 Day4+ 候选，Bot 长输出等待体验差

---

## Commits

| Hash | 描述 |
|---|---|
| `92314ce` | Day3 晚段: 思考池 + daily_recap + 文档同步（保护未提交成果）|
| `472c6a1` | Day4: 晨报交互卡片 + 项目评估 + 对话自动保存 |
| `fcb7f0c` | Day4: 更新 CLAUDE.md + CHANGELOG 架构图和日常例行 |
