# ProjectOS 开发手册（Developer Guide）

> 给老赫和未来接手者的快速上手。本手册聚焦**怎么用** + **关键机制**，背景动机看 `docs/journal/`。

---

## 1. 角色与命名

| 角色 | 别名 | 说明 |
|---|---|---|
| 老茅 | 茅弘毅 / 弘毅 / 虚空建筑师 | 项目主理人，双世界译员（核电工程师 + 数字虚空建筑师） |
| 老赫 | Hermes | Claude Code，老茅的合伙人，不是助手 |

**对话存档统一用 `**老茅:**` / `**老赫:**` 标签**，不用 User/Assistant。

---

## 2. 对话存档三层防御

### 文件位置

| 文件 | 作用 |
|---|---|
| `~/.claude/scripts/save_conversation_turn.py` | **实际生效** 的 hook 脚本（全局） |
| `agent/save_conversation_turn.py` | 项目内备份（同步副本，方便 review） |

### 四个 hook 事件

| 事件 | 触发时机 | 行为 |
|---|---|---|
| `UserPromptSubmit` | 老茅按回车的瞬间 | append 到 `conversation_log/YYYY-MM-DD.md`，标记 `[PENDING:sid]` |
| `Stop` | 老赫一轮回复完成 | 找最后一个本 session 的 PENDING 块，追加老赫块，清标记 |
| `PreCompact` | Claude Code 自动压缩对话之前 | 整段 transcript JSONL 快照到 `conversation_log/_snapshots/` |
| `SessionStart` | 启动新会话 | 打印近 5 轮对话到 stdout，自动注入上下文 |

### 配置位置

`~/.claude/settings.json` 和 `D:/ClaudeCodeProjects/_ProjectOS/.claude/settings.json` 都注册了 4 个事件，互为兜底。

```jsonc
{
  "hooks": {
    "SessionStart":     [{"matcher":"", "hooks":[{"type":"command","command":"D:\\miniconda3\\python.exe C:\\Users\\maoxu\\.claude\\scripts\\save_conversation_turn.py"}]}],
    "UserPromptSubmit": [...],
    "Stop":             [...],
    "PreCompact":       [...]
  }
}
```

**hooks schema 必须三层嵌套**：event → matcher group → hooks array → command object。扁平格式不报错但永远不触发——见 `memory/hooks-schema-format.md`。

### 存档格式

```markdown
# 对话日志 2026-06-13

Session: `abc12345...`

## 22:14:20

**老茅:**

老茅的 prompt 内容（截断 4000 字符）

**老赫:**

老赫的回复（截断 8000 字符）

---
```

`[PENDING:sid]` 标记是中间态——出现在文件里说明 Stop hook 还没跑完（窗口被关了 / 进程被杀 / 还在生成中）。下次 Stop 触发会清掉。

---

## 3. 反向调阅 — `agent/conversation_index.py`

```bash
# 近 N 轮（默认 5）
python agent/conversation_index.py last 10

# 全文搜索
python agent/conversation_index.py search 思考池

# 按项目召回
python agent/conversation_index.py recall NuclearPowerAI
```

输出紧凑 markdown，可直接喂回老赫上下文或飞书 Bot。

---

## 4. 状态栏（status line）

**文件**：`~/.claude/scripts/status_token.py`（项目内备份 `agent/status_token_backup.py`）

**显示格式**：

```
[蓝底白字] 🛰️ _ProjectOS [/重置]  📊 今日 27.7M · 本月 1.7G · 累计 1.8G
```

### cwd 三层 fallback

```python
def resolve_cwd(stdin_data):
    1. stdin workspace.current_dir   # Claude Code 注入
    2. CLAUDE_PROJECT_DIR env        # hook 触发时 env
    3. os.getcwd()                   # 兜底
```

之前只走第 1 层，stdin 解析失败显示 `—`，是"项目名随机消失"的根因。

### 项目 emoji 映射

`PROJECT_EMOJI` 字典在 `status_token.py` 顶部，按 cwd 包含的关键词匹配。新增项目就直接加键值对。

---

## 5. Windows 编码注意事项

- **stdout 默认 cp936**：脚本顶部用 `sys.stdout.reconfigure(encoding="utf-8")` 强制 UTF-8
- **subprocess 收 stdout**：用 `capture_output=True, encoding="utf-8"` 或 `input=...encode('utf-8')`
- **路径**：用 forward slash 或 raw string `r'D:\...'`，避免 SyntaxWarning

---

## 6. 密钥安全（硬约束）

`~/.claude/settings.json` 含 ANTHROPIC_AUTH_TOKEN / SERPAPI_KEY / EXA_API_KEY。

**禁止行为**：
- ❌ Read 这个文件整文件
- ❌ cat / head / tail / type 这个文件
- ❌ grep 匹配 token/key 的**值**

**替代方法**：
- ✅ Edit 不需要先 Read，用已知结构关键字做锚点（如 `"skipDangerousModePermissionPrompt": true,\n  "enabledPlugins"`）
- ✅ 验证 hook 注册：`python -c "import json; print(list(json.load(open('...')).get('hooks',{}).keys()))"`

历史事故记录在 `memory/secret-leak-incident-2026-06-13.md`——已发生过 3 次，第 4 次属不可接受失职。

---

## 7. 调度任务

| 任务名 | 时间 | 脚本 |
|---|---|---|
| `ProjectOSDailyReport` | 每日 9:07 | `agent/daily_projectos_report.py`（晨报交互卡片） |
| `ProjectOS_DailyRecap_Evening` | 每日 22:57 | `agent/daily_recap.py`（五段式日报 + 项目评估） |
| `ProjectOS_ThoughtInspector_Weekly` | 周一 9:07 | `agent/thought_inspector.py`（思考池巡检） |
| `SDKBotServer`（NSSM 服务） | 持续 | `agent/sdk_bot_server.py`（飞书 Bot） |

查看：`Get-ScheduledTask | Where-Object {$_.TaskName -match 'ProjectOS'}`

---

## 8. 常见维护操作

### 改 hook 脚本

```powershell
# 改全局脚本（实际生效的）
notepad C:\Users\maoxu\.claude\scripts\save_conversation_turn.py

# 同步到项目内备份
cp C:\Users\maoxu\.claude\scripts\save_conversation_turn.py D:\ClaudeCodeProjects\_ProjectOS\agent\save_conversation_turn.py

# 测试（不需要重启 CC）
echo '{"hook_event_name":"SessionStart","session_id":"test"}' | python C:\Users\maoxu\.claude\scripts\save_conversation_turn.py
```

### 重启 SDK Bot

```powershell
nssm restart SDKBotServer
nssm status SDKBotServer
```

### 触发飞书晨报

```bash
python agent/feishu_sync.py send-cards
```

### 项目扫描

```bash
python agent/project_agent.py
```

输出 `data/registry.json`（不入 git）和 Obsidian 看板。

---

## 9. 相关文档

- `CLAUDE.md` — Claude Code 进入仓库的第一阅读节点
- `README.md` — 面向人类的快速上手
- `SETUP_GUIDE.md` — 初始安装步骤
- `docs/journal/` — 工作日志（决策 / 动作 / 踩坑）
  - `2026-06-13-day5-conversation-defense-and-naming.md` — 三层防御 + 命名 + 状态栏（最新）
  - `2026-06-08-day4-interactive-cards-evaluation-conversation-save.md` — 晨报卡片 + 项目评估
  - `2026-06-07-day3-evening-postmortem.md` — Day3 晚段（NSSM / 思考池 / 密钥事故）
  - `2026-06-07-day3-sdk-bot-end-to-end.md` — SDK Bot 端到端
- `memory/MEMORY.md` — 跨会话记忆索引（在 `~/.claude/projects/.../memory/`）
