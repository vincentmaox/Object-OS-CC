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
│   ├── cc_bot_server.py    # 飞书 Bot 服务（计划替换）
│   └── daily_projectos_report.py  # 每日定时任务
├── data/                   # 数据真值（不入 git）
│   └── registry.json
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

## License

私有项目。Ceeon/claude-channel-feishu 子模块（如引入）遵循 Apache-2.0。
