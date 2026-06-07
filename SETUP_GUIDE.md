# ProjectOS 安装配置完成指南

## ✅ 已完成

### 1. 飞书 CLI & MCP Server
- ✅ 官方 `@larksuite/cli` 全局安装就绪
- ✅ App ID: `cli_aa97967fa3b81cc7` 已绑定
- ✅ Bot身份认证就绪（tenant_access_token可用）
- ✅ User身份OAuth完成 — `茅弘毅` (ou_59a5d4b0cc115a66295961a1aec66a9e)
- ✅ 已授权域: im, base, docs, drive, calendar, task, wiki
- ⚠️  受限scope `im:message.send_as_user` 未授（需企业管理员开启）— 不影响Bot通知

### 2. 飞书数据已打通
- ✅ Bot身份发消息：晨报推送已上线
- ✅ 多维表格已创建并完成首次同步
  - 表名：ProjectOS 项目注册表
  - URL: https://voidarchitect.feishu.cn/base/XZrSbVFATaiwcRsmAgocRin4n3M
  - 主表 `项目总览` 含11个字段，已同步4个项目记录

### 3. Obsidian 插件生态
- ✅ Dataview — 动态查询项目看板
- ✅ Tasks — 卡点任务管理与勾选
- ✅ Templater — 新项目快速模板
- ✅ Calendar — 72小时MVA决策时间线
- ✅ Local REST API — 与Agent双向通信

### 3. 飞书同步引擎 (`agent/feishu_sync.py`)
- ✅ 每日项目晨报推送（Bot消息）
- ✅ 注册表同步到多维表格
- ✅ Obsidian文档同步到飞书文档
- ✅ 高严重卡点紧急提醒
- ✅ 72小时MVA决策请求推送

### 4. Project Agent 升级
- ✅ 自动生成每个项目的 Dataview frontmatter 笔记
- ✅ 资源需求自动生成 Tasks 待办
- ✅ 卡点数量/严重程度统计字段
- ✅ 项目停滞天数自动计算

### 5. 每日定时任务
- ✅ Cron: 每天 9:07 执行 `project_agent.py`
- ✅ 重新扫描 → 更新看板 → 推送飞书晨报

---

## 🔐 下一步：完成飞书授权（必做）

### 步骤 1/2 — 完成 OAuth Device 授权（获取User身份）

扫码（或点击链接）完成OAuth，User身份才能：
- 以**你本人**名义发消息/创建文档
- 读取你的群聊/私聊
- 同步你的任务/日历

**授权链接**: https://accounts.feishu.cn/oauth/v1/device/verify?flow_id=OI2IRODjQhLKOOOOOOOOOO_zgeUrywmzo-zU6lSL7CYS&user_code=WZL4-5AAG

完成授权后验证：
```bash
lark-cli auth status
# User身份显示 ready
```

### 步骤 2/2 — 配置你的接收消息的 User ID

授权后执行：
```bash
python feishu_sync.py auth
# 找到你的 user_id (ou_xxxx)，然后测试发消息
python feishu_sync.py send-report ou_your_user_id
```

### 步骤 3/2（可选）— 把机器人加到群聊

机器人也可以发消息到群聊：
```bash
# 先把机器人拉入群聊
# 拿到 chat_id (oc_xxxx)
python feishu_sync.py send-report oc_your_chat_id
```

---

## 📂 文件布局

```
ClaudeCodeProjects/
├── _ProjectOS/                          # ProjectOS 系统目录
│   ├── agent/                           # 使魔引擎
│   │   ├── project_agent.py            # 项目扫描器+看板生成
│   │   └── feishu_sync.py              # 飞书同步引擎
│   ├── data/
│   │   ├── registry.json               # 项目注册中心（真值）
│   │   └── feishu-base-config.json      # 飞书多维表格绑定
│   ├── templates/
│   ├── _inbox/                         # 散落文件临时收纳
│   └── archive/                        # 已归档项目
├── ProjectOS-Projects/                  # 项目笔记（Dataview数据源）
│   ├── ai-router-48h.md
│   ├── PhysicsAI-Research.md
│   └── ...
├── ProjectOS-Dashboard.md               # 静态Agent生成看板
├── ProjectOS-DynamicDashboard.md        # 动态Dataview看板
├── ProjectOS-DailyReport.md             # 每日晨报
└── ProjectOS-ArchiveIndex.md            # 归档索引
```

---

## 🚀 常用命令

```bash
cd D:/ClaudeCodeProjects/_ProjectOS/agent

# 手动全量扫描+更新看板
python project_agent.py

# 发送晨报到飞书
python feishu_sync.py send-report <user_id_or_chat_id>

# 同步注册表到飞书多维表格
python feishu_sync.py sync-base

# 推送卡点紧急提醒
python feishu_sync.py alert <user_id_or_chat_id>

# 手动设置项目优先级
python project_agent.py priority <项目名> P0
python project_agent.py priority <项目名> P1
python project_agent.py priority <项目名> P2

# MVA决策
python project_agent.py mva <项目名> All-in
python project_agent.py mva <项目名> Watch
python project_agent.py mva <项目名> Kill

# 归档项目
python project_agent.py archive <项目名>
```

---

## ⚙️ 后续可能需要的配置

1. **飞书每日9:07自动推送晨报** — Cron任务当前只跑`project_agent.py`，飞书推送是额外步骤。完成授权拿到user_id后，我帮你把飞书推送也加入每日定时。

2. **Templater 项目模板** — 在Obsidian中设置 `_ProjectOS/templates/project-template.md` 为Templater的模板文件夹，新建项目时一键套用。

3. **Tasks插件联动** — 当前资源需求已经生成了`- [ ]`格式的待办，Tasks插件会自动识别，直接在Obsidian中勾选即可。

---

## 风险说明

- 每日定时任务（9:07）会在7天后过期（Cron的默认限制），到时候需要重新激活
- Bot身份和User身份的API权限范围不同，有些操作只能以User身份做
- 首次同步多维表格会自动创建，后续增量同步需要补充sync逻辑
