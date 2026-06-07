# ProjectOS 工作日志 — Day2：Channel方案碰壁→SDK方案验证通过

**日期：** 2026-06-07
**MVA 节奏：** Day2 市场验证

## 核心结论

✅ **方案D（claude-agent-sdk + 现有飞书Bot）端到端验证通过**，可以在火山方舟代理下拿到100%的Channel体验。

❌ **Ceeon方案在第三方代理下不可用**（被服务端 `tengu_harbor_ledger` 屏蔽）。

## Day2 演进路径

### 上午：Ceeon方案接入（按Day1计划）
- ✅ Bun 1.3.14 装好（winget）
- ✅ 凭据落 `~/.claude/channels/feishu/.env`
- ✅ `mcp.json` 配好（bun绝对路径）
- ✅ `bun install` 装好123个包
- ✅ server.ts standalone 跑通：WebSocket连飞书，拿到 Bot open_id `ou_1c048ddf206ea511f07019b0c29de0e1`

### 中午：启动验证失败
- ❌ `claude --dangerously-load-development-channels server:feishu` 启动后报：
  ```
  --dangerously-load-development-channels ignored (server:feishu)
  Channels are not currently available
  ```
- **根因诊断：** 用户`~/.claude/settings.json`配置走火山方舟代理（`ANTHROPIC_BASE_URL=https://ark.cn-beijing.volces.com/api/coding`），Channel需要Anthropic官方API后端的`tengu_harbor_ledger`服务端白名单，第三方代理无法命中

### 下午：调研替代方案
- ✅ 确认 `claude-agent-sdk` (Python v0.2.93) 存在且可用
- ✅ inspect SDK源码确认关键能力：
  - `can_use_tool` callback：`(tool_name, input, ctx) -> Awaitable[Allow|Deny]`，**异步**
  - `env`/`hooks`/`mcp_servers`/`session_store` 全套
  - 重要：SDK调起本地claude CLI，自动继承`~/.claude/settings.json` env配置
- ✅ 找到 `~/.claude/settings.json` 已配火山方舟env，无需额外注入

### 傍晚：smoke test实证
- 写 `agent/sdk_smoke_test.py` 30行最小验证
- **关键踩坑**：第一次跑 `can_use_tool` 未触发
  - 原因：本地user级配置（settings.json含`skipDangerousModePermissionPrompt: true`）让CLI直接放行tool_use
  - **修复**：`ClaudeAgentOptions(setting_sources=[])` 显式不继承user/project配置
- **第二次跑全绿**：
  ```
  [Claude决定调用] PowerShell(['command', 'description'])
  [✅ can_use_tool TRIGGERED]
  [↩️ 返回 Allow] 等待1.0s
  [完成] turns=2 cost=$0.0205
  ```
- 文件 `D:/temp_sdk_test.txt` 实际被写入磁盘 → 端到端全链路成立

## 关键技术事实留档

### 火山方舟代理实测
- ✅ 透传 `tool_use` content block
- ✅ 接受 `--permission-mode default` flag
- ✅ 接受 SDK 主动发起的 `subtype="can_use_tool"` 控制请求
- ❌ 不支持 `--dangerously-load-development-channels`（被代理后端剥）
- ❌ 不支持 MCP `experimental.claude/channel` capability协商

### SDK 实测能力
- `ClaudeSDKClient` 异步 session
- `can_use_tool` 可await任意时长（实测1秒OK，理论可await飞书round-trip的30秒+）
- `setting_sources=[]` 是隔离user级配置的关键开关
- 当前模型路由（settings.json）：sonnet=glm-5.1, opus=deepseek-v4-pro, haiku=kimi-k2.6
- 测试调用成本：$0.0205/次（GLM-5.1）

### Bot Token 信息（已发现的额外资产）
- 飞书Bot open_id: `ou_1c048ddf206ea511f07019b0c29de0e1` — Ceeon验证时拿到
- 用户open_id: `ou_59a5d4b0cc115a66295961a1aec66a9e`
- App ID: `cli_aa97967fa3b81cc7`

## Day3 计划（方案D实施）

### 改造 cc_bot_server.py 路线
1. **保留**：WebSocket长连、上下文deque、白名单、lark SDK封装、分片
2. **替换**：`subprocess.run(['claude','-p',prompt])` → `ClaudeSDKClient`异步session
3. **新增**：
   - 飞书交互卡片渲染器（参考 Ceeon `server.ts:475-509`的JSON结构）
   - `can_use_tool` 飞书round-trip：发卡片→`asyncio.Event`→等`card.action.trigger`回调→resolve
   - 卡片更新API（点按钮后从"等待中"刷成"已批准"）

### 工作量估算
- 卡片渲染器：1.5h
- can_use_tool→飞书→Event解析回路：3h
- SDK替换subprocess：1.5h
- 流式输出（每500ms合并刷卡片）：2h
- 联调+踩坑：2h
- 总计：~10h，可在 Day3+Day4 完成

### 待办文件
- [ ] `agent/sdk_bot_server.py` — 新版Bot主程
- [ ] `agent/feishu_cards.py` — 卡片模板（permission/morning/status）
- [ ] `agent/feishu_card_router.py` — `card.action.trigger`事件路由
- [ ] 替换NSSM服务的启动脚本

## 风险已对冲

| 风险 | 状态 |
|---|---|
| 火山方舟剥tool_use | ✅ 实证不剥 |
| can_use_tool异步等待超时 | ✅ SDK层面无stdio阻塞，可等任意时长 |
| Channel卡片协议依赖 | ✅ 完全自渲染，不依赖任何官方协议 |
| 旧Bot降级路径 | ✅ cc_bot_server.py保留，新Bot独立文件 |

## 项目状态

- 本地git: 2 commits, 干净
- 远程: github.com/vincentmaox/Object-OS-CC 已push
- Ceeon仓库: clone保留，作为卡片JSON结构参考资源
- SDK: claude-agent-sdk 0.2.93 已装
- Bun: 1.3.14 已装（虽然这条路线没用上了）
