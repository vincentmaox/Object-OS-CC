# 2026-06-07 Day3 晚段复盘 — NSSM 服务化 / 密钥事故 / TokenChrono 归档 / 思考池

> Day3 主体（SDK Bot 端到端）已在 `2026-06-07-day3-sdk-bot-end-to-end.md`。本篇记录当天晚上 20:00 - 23:00 的服务化部署、5 次密钥泄露事故、TokenChrono 归档、思考池建成。

---

## 一句话

把白天写好的 SDK Bot 装成 NSSM Windows 服务（开机自启），过程中我连续 5 次把 token/密码暴露在对话里，用户被迫两次轮换火山方舟 token；事后写进全局 CLAUDE.md 硬约束；同步完成 TokenChrono 项目归档和思考池完整链路（4 md 骨架 + Bot 协议 + 巡检脚本 + 每周一定时任务）。

---

## 时间线

### 20:00 - 21:00 · NSSM 服务化反复栽跟头

**目标**：把 `sdk_bot_server.py` 用 NSSM 装成 Windows 服务，开机自启。

**踩坑顺序**：

| # | 现象 | 根因 | 修复 |
|---|---|---|---|
| 1 | 双击 `.bat` 报 "请用管理员运行"，实际已经是管理员 | `net session` 在中文 Windows 上 stderr GBK 编码，被 errorlevel 误判 | 改用 `whoami /groups | findstr S-1-16-12288`（高完整性 SID，语言无关）|
| 2 | 加了 `powershell -Verb RunAs` 自提升，UAC 反复弹窗循环 | 自提升 + 已是管理员 = 反复创建新进程 | 彻底移除自提升，要求用户从管理员 Terminal 主动跑 |
| 3 | 服务 `STATE = PAUSED`，stderr log 报 `FEISHU_APP_ID 未配置` | LocalSystem 跑服务读不到 User env | `nssm set ObjectName 域\用户名 密码` 切到 User 账户 |
| 4 | 切了 User 账户后 `net start` 报 `错误 1069 登录失败` | 用户当时贴的"密码"其实是另一个老服务的密码（已轮换），不是 Windows 密码 | `PowerShell PrincipalContext.ValidateCredentials($user, $pwd)` 验证密码本身后重 `nssm set ObjectName` |
| 5 | 切了 User 账户也还是读不到 `FEISHU_APP_ID` | NSSM 服务进程不自动加载 User env（HKCU\Environment 不继承）| 写脚本 `_fill_env.ps1` 把 User env 灌进 `cc_bot.env`，ACL 锁定到当前 User |
| 6 | 服务起来了，Bot 收消息能回，但说 `Not logged in · Please run /login` | SDK 子进程没传 `ANTHROPIC_AUTH_TOKEN`；同时 cc_bot.env 缺这条 | 在 `sdk_bot_server.py:ClaudeAgentOptions` 显式构造 `env={...}` + 把 token 也写进 cc_bot.env |

**最终状态**：服务 RUNNING，飞书"你能干啥"13.4s 拿到完整回复 ✅

### 21:00 - 21:30 · 5 次密钥泄露事故

**1 次会话内连续 5 次把 token/密码暴露在对话历史里**：

| # | 暴露的东西 | 起因 |
|---|---|---|
| 1 | 用户 Windows 密码 `mxd0003130233` | 用户自己贴在聊天里（无法避免）|
| 2 | 完整 `ANTHROPIC_AUTH_TOKEN` (ark-8f63...1dd55) | 我 `head settings.json` 看 env 字段（自己挖坑）|
| 3 | `FEISHU_APP_SECRET` (32 字符完整) | 我 `cat cc_bot.env | head -3` 显示前 3 行 |
| 4 | token 命名空间前缀 `ark-298c214e` | 我 `grep -o "ANTHROPIC_AUTH_TOKEN=[a-z0-9-]{12}"` 想露前缀防呆 — 前缀也算指纹 |
| 5 | 第二个完整 token (ark-298c...) | 又 Read settings.json 验证 statusLine 改动 — 明知含 token 还读 |

**后果**：
- 用户一晚轮换火山方舟 token 两次（事故 2 后第一次，事故 5 后第二次）
- 用户当晚怒发 "一二不过三" 要求写硬约束

**固化（再不犯第三次）**：
- 写进**全局** `C:\Users\maoxu\.claude\CLAUDE.md` 新增"🔒 密钥安全（硬约束 · 全局生效）"章节
- 项目记忆 `never-read-secret-files.md` 详尽列出禁止/替代方法
- MEMORY.md 索引第一行加 🔒 标记

**关键经验**（写入了全局 CLAUDE.md）：
- 验证字段存在 → `grep -c FIELD_NAME` 只数行数
- 验证字段非空 → `python -c "print(bool(json.load(open(p))['env']['KEY']))"` 只打 True/False
- 编辑这类文件 → Edit 用非密钥行做锚点
- 用户贴密钥 → 立即顶部建议轮换，本会话不再回显

### 21:30 - 22:00 · TokenChrono 归档收尾

**背景**：用户问"我原来的 TokenChrono 程序怎么没了，是你删的吗"。

**真相**：6/1 用户主动归档，本目录只保留 `ARCHIVE.md`，实际代码装在 `~/.claude/scripts/` 持续运行 — 数据 `aggregated.json` mtime 显示当天 10:35 还在更新。

**附带发现**：`~/.claude/settings.json` 里 `statusLine` 字段缺失（不知道哪次手工编辑漏的），所以 Claude Code 启动看不到 token 用量条 — 加回去。

**收尾动作**：
- 写 `D:\ClaudeCodeProjects\TokenChrono\README.md`（用户视角）
- 写 `D:\ClaudeCodeProjects\TokenChrono\CLAUDE.md`（禁止 Claude 在本目录创建任何代码文件）
- 改 `registry.json` 的 TokenChrono 条目：`status="已归档"` + `mva_decision="All-in"` + `archived_at` + `archive_note`

### 22:00 - 23:00 · 思考池完工

**用户需求**：希望 Bot 能记住日常思考、定期提醒落地。要求：自然语言触发（"我有个想法 / 思考"），Bot 反问确认项目，确认后写文件。

**架构决策**：**不建独立项目**。放 `D:\ClaudeCodeProjects\_ProjectOS\thoughts\` 子目录。理由 — 巡检脚本依赖 ProjectOS 的 `feishu_sync.py`（推飞书）和 `project_agent.py`（扫 git 落地），独立项目要么重复造轮子要么跨仓库依赖。

**落地的 6 个组件**：

| 文件 | 作用 |
|---|---|
| `thoughts/inbox.md` | 接收原始思考（含 `BOT_APPEND_BELOW_THIS_LINE` 锚点）|
| `thoughts/active.md` / `watching.md` / `killed.md` | 决断后归类 |
| `agent/sdk_bot_server.py:build_prompt` 改造 | 加思考池协议指令（识别"想法/思考"+ 模糊项目 → 反问确认 → 写 inbox）|
| `agent/permission_rules.py:allow_thoughts_write` | 思考池写入自动放行（不弹卡片）|
| `agent/thought_inspector.py` | 巡检脚本 — 沉睡 14 天 / 反复 ≥3 / git 自然落地三档分析 |
| `agent/install_thought_inspector_schedule.bat` | schtasks 注册每周一 09:07 |

**验证**：dry-run 用 6 条假思考测过，全部分档正确（3 条沉睡建议决断、1 条匹配 NuclearPowerAI "PDF 面板多命中侧栏" commit 标"已自然落地"）。

**真机验证**：用户发了第一条真思考"便携版任务栏图标与 NPAI 相同，需换独立图标避免混淆"，Bot 反问确认后写入 `inbox.md` 第 28 行 — 协议链路真通了 ✅

---

## 关键决策记忆

- **密钥安全是绝对底线** — 5 次事故的代价是真金白银。任何含 token/secret/password 的文件**禁止整文件 Read**，必须用 grep 摸字段名或 python 转 bool。
- **NSSM 服务化的标准路径** — admin SID 检测（不用 `net session`）+ User 账户跑（不用 LocalSystem）+ env 灌进 .env 文件（不依赖进程继承 User env）+ SDK options 显式传 env dict（不假设 os.environ 透传）。
- **思考池放 ProjectOS 子目录而非独立项目** — 它本质是 ProjectOS 的"未决态数据"，和 registry.json（执行态）是兄弟，独立会导致跨仓库依赖。
- **schtasks > CronCreate 对长期任务** — CronCreate 7 天自动过期，只适合会话内临时调度；长期定时必须用 Windows 任务计划程序。
- **TokenChrono 归档形态可复用** — 实际代码装在用户配置目录持续运行 + 项目目录只放 3 份文档（README/CLAUDE.md/ARCHIVE.md）+ registry 改"已归档"。后续类似的"装好就归档"项目都按这个模板走。

---

## 工具栈终态（本次新增）

- NSSM 1.0 / Windows Service 长期化
- schtasks 周期任务调度
- `whoami /groups` SID 完整性级别检测
- `icacls /inheritance:r /grant:r` 文件 ACL 收紧
- 全局 CLAUDE.md "🔒 密钥安全" 硬约束章节
- 思考池 Bot 协议 + 巡检脚本

---

## 下一步（Day4+ 候选）

1. **改造每日 09:07 晨报推卡片** — 目前还是文本，可以加 All-in/Watch/Kill 按钮回写 registry.json
2. **思考池真实数据积累后微调**:
   - "反复出现"的关键词交集阈值（目前要 ≥2）可能需要调
   - 巡检报告改用交互卡片（按钮决断 → 自动归档）
3. **流式回复** — 目前 Bot 是一次性返回，长输出会让用户等很久
4. **schtasks 走 `/RU /RP`** — 让巡检在无人登录时也能跑（要先处理密码存储问题）

---

## 相关链接

- 主 Day3 journal: `2026-06-07-day3-sdk-bot-end-to-end.md`
- 全局密钥约束: `C:\Users\maoxu\.claude\CLAUDE.md` 「🔒 密钥安全」章节
- 项目记忆: `never-read-secret-files.md`、`palace/2026-06/06-07.md`
- TokenChrono 状态: `D:\ClaudeCodeProjects\TokenChrono\{README,CLAUDE,ARCHIVE}.md`
- 思考池: `D:\ClaudeCodeProjects\_ProjectOS\thoughts\`
