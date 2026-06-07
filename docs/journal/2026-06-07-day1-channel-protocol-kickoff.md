# ProjectOS 工作日志 — Day1：Channel 协议方案评估与启动

**日期：** 2026-06-07
**负责人：** 茅弘毅（虚空建筑师）+ Claude Code
**MVA 节奏：** Day1 理论验证

## 决策背景

### 痛点
- 现有 `cc_bot_server.py`（自写 Python 飞书 WebSocket Bot）能用，但：
  1. 纯文本交互，无卡片/按钮
  2. Claude 工具调用权限无法推到移动端，远程驱动断在权限弹窗
  3. 富媒体（图/文件）支持弱

### 调研对比（详见 上一轮调研产出）
| 方案 | 结论 |
|---|---|
| Codex Cloud | ❌ 中国账号/支付门槛 + 与本地 ProjectOS 上下文割裂 |
| Hermes Agent | ❌ 是 Claude Code 替代品（非补充），换内核成本极高 |
| **Ceeon/claude-channel-feishu** | ✅ Claude Code 官方 Channel 协议 + 飞书 + 移动端权限中继，三痛点全解 |
| MocA-Love/claude-code-lark | 备选，无 permission relay，3 月未更新 |
| xfbaby/claude-feishu-agent | ❌ 本质是当前架构 TS 重写，不解决痛点 |

### 频域决策
- 理论：4 分（Channel 协议是 Claude Code 官方扩展点）
- 市场：5 分（三个开源实现已踩过坑）
- 组织：4 分（与现有飞书 App 复用，迁移成本可控）
- **总分 13 > 12，执行**

## Day1 动作

### ✅ 已完成

1. **救火：修复 alert 身份 bug**
   - `feishu_sync.py` `send_blocker_alert` 从 `send_message` 改为 `send_rich_message`
   - 根因：`--text` 模式 lark-cli 走 user 身份，触发 `im:message.send_as_user` scope 缺失
   - 验证：alert 推送成功，identity=bot

2. **Clone Ceeon 仓库**
   - `D:/ClaudeCodeProjects/claude-channel-feishu/`
   - 关键文件：`server.ts`（1133 行）、`README.md`、`skills/`、`scripts/trace-channel-startup.sh`

3. **核心代码确认（Channel 协议实证）**

   ```ts
   capabilities: { tools: {}, experimental: {
     'claude/channel': {},
     'claude/channel/permission': {}
   }}
   ```

   - 入站：`notifications/claude/channel` 把飞书消息推进 Claude session
   - 出站：4 个 MCP tools：`reply` / `react` / `download_attachment` / `edit_message`
   - 权限：`notifications/claude/channel/permission_request` → 飞书交互卡片 → `card.action.trigger` → 回 Claude

4. **本地文档落地**
   - `_ProjectOS/CLAUDE.md`：Claude Code 导航 + 关键约束 + 踩坑清单
   - `_ProjectOS/README.md`：30 秒上手 + 目录 + 安装
   - `_ProjectOS/docs/journal/`：本日志目录建立

### 🟡 等用户确认

5. **Bun 安装** — 当前 PATH 无 bun，需执行：
   ```
   winget install Oven-sh.Bun
   ```
   未自动跑（涉及包安装，先告知用户）

6. **飞书 App 新增权限**（需用户操作飞书后台）：
   - 权限管理：`im:resource`、`im:message.reactions:write`
   - 事件订阅：`card.action.trigger`
   - **创建新版本并发布**（关键，不发版本所有改动不生效）

## 接入清单（Day2 用）

### 启动命令模板（验证后再固化）
```bash
claude \
  --strict-mcp-config \
  --mcp-config %USERPROFILE%\.claude\channels\feishu\mcp.json \
  --dangerously-load-development-channels server:feishu \
  --plugin-dir D:\ClaudeCodeProjects\claude-channel-feishu
```

### 凭据落位
```
%USERPROFILE%\.claude\channels\feishu\
├── .env          (FEISHU_APP_ID, FEISHU_APP_SECRET)
├── mcp.json      (注册 feishu MCP server)
├── access.json   (路由配置，/feishu:access 管理)
└── inbox/        (下载附件落地)
```

### mcp.json 模板（Windows 适配）
```json
{
  "mcpServers": {
    "feishu": {
      "command": "bun",
      "args": ["run", "--cwd", "D:/ClaudeCodeProjects/claude-channel-feishu", "--shell=bun", "--silent", "start"],
      "type": "stdio"
    }
  }
}
```

## 风险与对冲

| 风险 | 对冲 |
|---|---|
| `--dangerously-load-development-channels` dev-only，Anthropic 可能改动 | 锁 Claude Code 版本（当前 2.1.143），保留 cc_bot_server.py 做降级 |
| Bun on Windows 兼容性未实测 | Day2 先验证 `bun --version` 能跑 + `bun install` 能装 |
| 飞书 App 加权限后忘发版本 | 写入 CLAUDE.md 踩坑清单（已写） |
| Channel 协议 Windows 路径坑（正斜杠 vs 反斜杠） | mcp.json 用正斜杠，PATH 用 `%USERPROFILE%` |

## 本地 Git 管理决策

- **本地仓库**：今日初始化 `git init`，首次 commit "Initial ProjectOS snapshot"
- **远程仓库**：https://github.com/vincentmaox/Object-OS-CC
- **push 时机**：用户确认 README/CLAUDE.md 内容无误后再 push（不擅自上传）
- **不入 git**：`data/*.json`（含 base_token）、`agent/*.env`、`agent/*.log`、`archive/`、`_inbox/`、`feishu-auth-qr.png`、`agent/cc_bot_context.json`

## 明日计划（Day2 市场验证）

1. 用户飞书后台加权限+发版本
2. `winget install Oven-sh.Bun`
3. `cd claude-channel-feishu && bun install`
4. 配 `~/.claude/channels/feishu/.env` 和 `mcp.json`
5. 启动测试 session，飞书发"你好"验证：
   - 能否收到带按钮的回复
   - 触发 Claude 工具调用时，权限弹窗是否推到飞书
6. 测试通过 → 整理为 NSSM 服务方案
7. 测试失败 → 跑 `scripts/trace-channel-startup.sh` 抓日志，写入本日志

## 关键事实留档

- Claude Code 版本：2.1.143
- 系统：Windows 11 Home China 10.0.26200
- VPN 状态：已通（外网 GitHub 可达）
- 现有 ProjectOS 服务：cc_bot（NSSM 服务），运行中，**不动它**
