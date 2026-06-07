# ProjectOS 工作日志 — Day3：方案D 实施完工（SDK + 飞书 Bot 混合）

**日期：** 2026-06-07
**MVA 节奏：** Day3 组织验证 → All-in

## 核心结论

✅ **方案D 端到端真机联调通过**：飞书 → SDK session → can_use_tool 拦截 → 卡片/规则双通道 → 工具执行 → 结果回复 全链路工作。

## Day3 产出文件

| 文件 | 职责 |
|---|---|
| `agent/feishu_cards.py` | 三种卡片模板（permission/morning/status）+ resolved 替换卡 + truncate 辅助 |
| `agent/feishu_card_router.py` | `PermissionRouter` 类：register / await_decision / handle_card_action / resolve_by_text |
| `agent/sdk_bot_server.py` | 新版 Bot 主程，asyncio 主循环 + lark WS worker 线程双线程模型 |
| `agent/permission_rules.py` | 规则引擎：白名单（只读工具/git 只读/dry-run）+ 黑名单（rm -rf root/force push main） |
| `agent/card_render_test.py` | 卡片真机渲染测试 |
| `agent/test_card_router.py` | 路由单元测试（6 个全绿） |
| `agent/install_sdk_bot_service.bat` | NSSM 服务安装脚本（自动卸载旧 CCBotServer 避免 WS 冲突） |

## 关键技术决策

### 双通道权限决策
1. **规则层（无声）**：Read/Grep/Glob/git status/PowerShell Get-* → 自动 Allow，不打扰
2. **卡片层（默认）**：未命中规则 → 飞书橙色卡片 + Allow/Deny/See more 三按钮
3. **命令层（备用）**：飞书回复 `y` / `n` / `拒绝` / `y req_xxx` 也能解 pending

### 三个非显然踩坑

#### 坑1：lark-cli.cmd 在 Windows 上吃掉 interactive 卡片 JSON 的双引号
- 症状：发普通文本/post 都正常，发 interactive 卡片报 exit 1，stderr 是 GBK 编码的"文件名、目录名或卷标语法不正确"
- 根因：`.cmd` shim 走 cmd.exe，cmd.exe 对含 `"` 和 `\n` 的大段 JSON 参数重新解释
- 修：直接调 `D:/nodejs/node.exe + run.js`，shell=False，绕过 cmd.exe
- 落地：`feishu_sync.py` `send_interactive_card` 独立实现，不复用 `_run`

#### 坑2：lark 回调在 worker 线程里，不能直接 `asyncio.Event.set()`
- 症状：can_use_tool 永远收不到决策
- 根因：lark `ws.Client` 的事件分发跑在自己的线程池，asyncio Event 必须在 owning loop 里 set
- 修：`PermissionRouter.bind_loop()` 记下主循环，`loop.call_soon_threadsafe(p.event.set)` 派发
- 复用：`resolve_by_text` 命令通道也用同一机制

#### 坑3：`setting_sources=[]` 必须显式（继承自 Day2）
- 不加 → user-level `skipDangerousModePermissionPrompt: true` 让 CLI 直接放行所有工具，can_use_tool 不触发
- 加上 → SDK 完全隔离本地配置，按预期拦截

## 真机联调记录（2026-06-07 11:33-11:40）

用户测试场景：
1. "各项目进展情况" → SDK 触发 PowerShell 跑 `python project_agent.py` → 卡片送达 → 点 Allow → 176s 完成 → 8 个项目盘点回复
2. "你能干啥..." → SDK 纯对话无工具调用 → 46.8s → 直接回复"七层使用说明书"
3. 第二轮基于第一轮的项目盘点回答（上下文窗口生效）

## 架构图

```
飞书私聊                           本机 Python 进程
   │                              ┌──────────────────────────┐
   ├─ 消息 ──► lark WS ─────►  ws_thread                     │
   │                              ↓                          │
   │                       on_message ──┐                    │
   │                                    │ run_coroutine_threadsafe
   │                                    ↓                    │
   │                              asyncio 主循环            │
   │                                    │                    │
   │                              ClaudeSDKClient.query     │
   │                                    │                    │
   │                              can_use_tool ─► permission_rules │
   │                                    │           │ allow → 直返 │
   │                                    │           │ deny  → 直拒 │
   │                                    │           │ ask           │
   │                                    ↓           ↓               │
   │                              router.register + send_card       │
   │                                    │                    │
   │  ◄─ 权限卡片 ───── lark im.message.create               │
   │                                    │                    │
   │                              await event.wait()         │
   │                                    │                    │
   ├─ 点 Allow 按钮 ─► lark WS ──► card.action.trigger      │
   │                              router.handle_card_action  │
   │                              loop.call_soon_threadsafe  │
   │                                    │                    │
   │                              PermissionResultAllow      │
   │                                    │                    │
   │                              SDK 执行工具 → 收集回复    │
   │                                    │                    │
   │  ◄─ 文本回复 ───── lark im.message.create               │
   │                              └──────────────────────────┘
```

## 风险已对冲

| 风险 | 状态 |
|---|---|
| 火山方舟剥 tool_use | ✅ Day2 已实证不剥，Day3 端到端再次验证 |
| can_use_tool 异步等待超时 | ✅ 实测 176s 任务无 stdio 阻塞 |
| 卡片协议依赖 | ✅ 完全自渲染，不依赖 Channel |
| 旧 Bot 降级 | ✅ cc_bot_server.py 保留，install_sdk_bot_service.bat 自动停旧服务避免 WS 冲突 |
| 误操作 | ✅ permission_rules 黑名单防 rm -rf 盘符根、force push main、裸 reset --hard |

## 下一步（Day4+）

### 短期（24h 内）
- 装 NSSM 服务自启：`install_sdk_bot_service.bat`（管理员运行）
- 改造每日 9:07 定时任务从 `daily_projectos_report.py` 推晨报卡片（不再纯文本）
- 让晨报卡片 All-in/Watch/Kill 按钮真正回写 registry.json 状态

### 中期
- 流式回复（assistant 文本块到达即更新状态卡片，不等 ResultMessage）
- 长任务可中断按钮（卡片加 "❌ 取消" 触发 client.close）
- 多并发 session（不同 chat_id 走独立 ClaudeSDKClient）

### 长期
- 在 settings.json hooks 层加 PreToolUse 兜底审计（即使 SDK 路线挂了也不会无声执行）
- 飞书侧权限分级（白名单用户/只读用户/管理员）

## 项目状态

- 本地 git: 待 commit
- 远程: github.com/vincentmaox/Object-OS-CC 待 push
- bot: 已停（task buqv7puwq stopped），等装服务
- 工具栈: claude-agent-sdk 0.2.93 + lark-oapi + Node 直调 lark-cli + Python asyncio
