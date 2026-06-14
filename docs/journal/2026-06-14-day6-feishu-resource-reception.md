# Day6 — 飞书资源接收 + Bot 多模态扩容

**日期**：2026-06-14
**主线**：让 SDK Bot 能接收图片/文件/富文本（之前只支持文本），并把过去几天漏接的文件用 backfill 脚本捞回来。

## 起因（老茅原话）

> 赫赫，我今天给你发我有个想法的时候，你又说API Error: Request rejected (429)... 但实际上我已经通过CC Switch切换过Coding Plan了，其次我单独发消息给你发文件希望你下载保存，你说只支持文本消息，有没有哪个权限开通后你可以从飞书消息接收文件或阅读文件，包括群里的文件？

两个问题揉在一起：
1. **CC Switch 切换 Coding Plan 但 Bot 还报 429** — Bot 进程内存里 freeze 了启动时的 token，不会自动 reload。
2. **Bot 不接文件** — `sdk_bot_server.py:418` 一刀切：`msg_type != "text"` 就拒绝。

## 方案

### 1. 飞书资源下载客户端
`FeishuSender.download_resource(message_id, file_key, resource_type)` 用 lark-oapi `GetMessageResourceRequest` 实现。返回 `(bytes, file_name)`。

### 2. msg_type 多路分发
`on_message` 改造：
- `image` → 提取 `image_key` → 下载 → `agent/inbox/images/`
- `file` → 提取 `file_key` + `file_name` → 下载 → `agent/inbox/files/`
- `post` → 落 JSON 到 `agent/inbox/texts/`，并递归扫 `tag=img`/`file`/`media` 元素回调下载
- `audio`/`media`/`sticker` → 当 file 走兜底
- 落盘后回 "📥 已收到 X，落盘 N 个文件"

文件命名：`{YYYYMMDD-HHMMSS}_{open_id_short8}_{safe_filename}`。

### 3. 内置指令
- `/reload` 或 `/重载` — 调 `env_loader.load_all()` 重读 `~/.claude/settings.json` 的 ANTHROPIC_* 字段，回报 token 是否在位、BASE_URL 当前值。**注意**：当前正在跑的 SDK session 不受影响，下一条消息生效。
- `/list-inbox` 或 `/inbox` — 列 inbox 最近 20 条（含 img/file/text 三类，按 mtime 倒序）。

### 4. Backfill 脚本
`agent/feishu_backfill.py`：
- `--days N` / `--hours N` / `--chat-id X`
- 用 `ListMessageRequest`（`container_id_type="chat"`, `sort_type="ByCreateTimeAsc"`）拉历史消息
- 同样的下载 + 落盘逻辑（独立于 Bot 进程，不需要服务重启）
- 文本消息只打摘要，不入 inbox（避免和 conversation_log 重复）

## 实测

```
$ python agent/feishu_backfill.py --days 3 --chat-id oc_3a157c322267f8149a927ee151a6580e
回溯窗口: 2026-06-11 → 2026-06-14
扫描 57 条消息，落盘 5 个文件
```

落盘明细（`agent/inbox/files/`）：
- `20260614-171550_aec66a9e_20260608-重新野化心力训练体系.md` (32KB)
- `20260614-172416_aec66a9e_20260608-_虚空建筑师野化宣言_心力训练与AI变现完整作战体系.md` (76KB)

文件内容完整可读，证明 lark-oapi `message_resource.get` 链路通。

`agent/inbox/texts/` 里几个 om_x100... json 是飞书每天 09:07 发来的晨报交互卡片落档（`interactive` 类型暂未单独处理，落到 post 走的兜底）。

## 已知坑

- **`chat.list` 不返 p2p 私聊**（只返 group），所以 backfill 默认枚举到 0。要么走 `--chat-id` 显式传，要么后续做"从 cc_bot_context.json 读历史 chat_id"的索引。
- **服务重启需要 admin**：NSSM 服务跑在 SYSTEM 账户下，`taskkill /F` 普通用户拿不到句柄。要让代码生效，老茅必须管理员 PowerShell 跑：
  ```powershell
  D:\tools\nssm\nssm.exe restart SDKBotServer
  # 或
  Restart-Service SDKBotServer
  ```
- **`interactive` 消息**没有 file_key/image_key，是卡片 schema，无需也无法下载。当前 backfill 会打 `⚠️ 未提取到资源`，是噪音不是 bug。

## Day6 落地清单

- [x] 加 `GetMessageResourceRequest` 导入
- [x] `FeishuSender.download_resource()`
- [x] inbox 三目录自动创建（`INBOX_IMAGES/FILES/TEXTS`）
- [x] `save_to_inbox()` + `list_inbox()` 工具函数
- [x] `on_message` 移除 `msg_type != "text"` 单刀切，改多路分发
- [x] `/reload` 指令
- [x] `/list-inbox` 指令
- [x] `agent/feishu_backfill.py` 脚本
- [x] 实测：捞回 2 份漏接文件
- [ ] 服务重启（待 admin shell）→ 重启后 Bot 即可正常接 file/image
- [x] Day6 journal + git commit

## 下一步

- 服务重启后让老茅再发一次图片+文件做端到端确认
- `chat.list` 拿不到 p2p chat_id 的问题：从 `cc_bot_context.json` 反查历史 chat_id 列表，作为 backfill 默认目标
- `daily_recap` 加一句"今日 inbox 新增 N 项"提醒，避免文件落了没人看
- `interactive` 类型消息（晨报卡片回执）做轻量索引，区分"卡片本身"和"卡片回调"
