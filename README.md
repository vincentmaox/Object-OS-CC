# ProjectOS

> 把 `D:\ClaudeCodeProjects\` 下所有项目自动扫描、状态化、推到飞书的多项目跟踪与远程控制系统。

## 它解决什么

- **看不清进度** → 每天自动扫所有项目 → Obsidian 看板 + 飞书晨报
- **卡点遗忘** → 高严重度卡点自动推飞书 alert
- **远程驱动** → 飞书 Bot 私聊触发本机 Claude Code（CC 小助手）
- **决策没纪律** → 72h MVA 自动检测，提醒 All-in / Watch / Kill

## 30 秒上手

```bash
cd D:/ClaudeCodeProjects/_ProjectOS/agent

# 扫描所有项目 + 生成看板
python project_agent.py

# 推晨报到飞书（user_id 或 chat_id）
python feishu_sync.py send-report ou_59a5d4b0cc115a66295961a1aec66a9e

# 推高严重卡点提醒
python feishu_sync.py alert ou_59a5d4b0cc115a66295961a1aec66a9e

# 同步项目注册表到飞书多维表格
python feishu_sync.py sync-base

# 同步看板文档到飞书
python feishu_sync.py sync-docs
```

## 目录

```
_ProjectOS/
├── agent/                  # 核心脚本
│   ├── project_agent.py    # 项目扫描器 + 看板生成
│   ├── feishu_sync.py      # 飞书同步引擎
│   ├── sdk_bot_server.py   # 飞书 Bot 主服务（claude-agent-sdk + 卡片权限中继）
│   ├── feishu_cards.py     # 卡片模板
│   ├── feishu_card_router.py  # 卡片回调路由
│   ├── permission_rules.py # 工具权限白/黑名单引擎
│   ├── thought_inspector.py   # 思考池周巡检（每周一 09:07）
│   ├── cc_bot_server.py    # 旧版 Bot（保留作降级路径，不再开服务）
│   └── daily_projectos_report.py  # 每日定时任务
├── data/                   # 数据真值（不入 git）
│   └── registry.json
├── thoughts/               # 思考池
│   ├── inbox.md            # 接收原始思考（Bot 自动追加）
│   ├── active.md           # 已决断 Go
│   ├── watching.md         # 暂观望
│   └── killed.md           # 已 Kill 留痕
├── templates/              # 项目笔记模板
├── docs/                   # 文档
│   └── journal/            # 工作日志
├── archive/                # 已 Kill 项目归档（不入 git）
├── _inbox/                 # 散落文件归类区（不入 git）
├── CLAUDE.md               # Claude Code 导航
└── README.md               # 本文件
```

## 安装

### 前置依赖

- Python 3.11+（含 `requests`）
- [lark-cli](https://github.com/larksuite/lark-cli)（飞书 CLI 工具）
- Obsidian + Local REST API 插件（27123 端口）
- 一个飞书 Custom App（Bot capability）

### 配置环境变量

`agent/cc_bot.env` 和 `agent/project_os.env` 是模板，实际 secret 走 Windows User env：

```powershell
# 一次性安装到 User env
powershell -ExecutionPolicy Bypass -File agent/install_user_env.ps1
```

需要的变量：
- `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_ALLOWED_OPEN_IDS`
- `OBSIDIAN_API_KEY`、`OBSIDIAN_PORT`

### 注册定时任务（每日 9:07 晨报）

```bash
agent/install_daily_report_task.bat
```

### NSSM 服务化 CC 小助手 Bot

```bash
agent/install_service.bat
```

### NSSM 服务化新版 SDK Bot（推荐）

```bash
agent/install_sdk_bot_service.bat
```

服务名 `SDKBotServer`，跑当前 User 账户（继承 ~/.claude 配置）。
管理命令：`net start/stop SDKBotServer`、`sc query SDKBotServer`。

### 注册思考池每周巡检（每周一 09:07）

```bash
agent/install_thought_inspector_schedule.bat
```

不需要管理员。任务用 schtasks，跑当前 User 权限（Interactive only — 需登录 Windows 才触发）。

## 飞书 Bot 远程驱动（CC 小助手）

私聊飞书 Bot 任何指令 → 本机 Claude Code 执行 → 结果推回。需要：
1. 飞书 App 开启 Bot capability
2. 权限：`im:message`
3. 事件订阅：`im.message.receive_v1`（WebSocket 模式）
4. 创建版本并发布

详细踩坑见 `CLAUDE.md`。

## 工作流哲学（用户偏好）

- **频域决策**：不预测走势，只看键位（项目状态频谱）
- **72h MVA**：任何新项目 72 小时内 All-in / Watch / Kill
- **零持仓**：禁止"我必须做完 X 才能 Y"的固定仓位
- **认错套利**：错误 72h 内闭环为训练数据，不为面子持仓

ProjectOS 把上述纪律物化为代码，让纪律不依赖意志力。

## 思考池工作流（Day3 新增）

把日常零散思考变成结构化决断流：

1. **随手丢** — 飞书发"我有个想法，docreview 应该加 X" → Bot 反问确认项目 → 写入 `thoughts/inbox.md`
2. **每周一 09:07** — `thought_inspector.py` 自动巡检，按"沉睡 14 天 / 反复出现 ≥3 / git 自然落地"三档分析，推飞书报告
3. **你决断** — 回 Bot "1 Go, 2 Kill, 3 Watch" → 对应思考从 inbox 移到 active / killed / watching

详见 `thoughts/inbox.md` 头部说明。

## License

私有项目。Ceeon/claude-channel-feishu 子模块（如引入）遵循 Apache-2.0。
