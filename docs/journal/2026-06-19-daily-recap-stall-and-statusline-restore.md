# 2026-06-19 — 晚报卡顿推送失败修复 + 状态栏 token 恢复

**日期：** 2026-06-19
**主体：** 老茅 + 老赫
**起因：** 老茅反馈两件事 — (1) 昨晚 22:57 的项目总结一直到 23:17 还没发出来；(2) 终端状态栏看不到项目名和 token 消耗了。

## TL;DR

两个独立故障，同一晚一起修：

1. **晚报没发** — 不是没跑，是跑了 22 分钟（22:57→23:19）最后 `[推送] 失败`。根因双重：LLM 串行评估把链路拖死 + 飞书 `send_rich_message` 走 `lark-cli.cmd` 被 cmd.exe 吃 JSON 引号。
2. **状态栏空白** — `settings.json` 的 `statusLine` 字段丢了（6-13 密钥事故重建时漏掉），脚本 `status_token.py` 还在但没被挂载。

## 故障 1：晚报卡顿 + 推送失败

### 现象

`agent/daily_recap.log` 关键片段：

```
[22:57:04] === 启动 daily_recap args=[] ===
... 11 个项目 LLM 成功（22:57-22:59）...
[23:02:05] [disk-manager] LLM 超时 attempt=1/2 (90s)
[23:04:16] [disk-manager] LLM 超时 attempt=2/2 (90s)
[23:04:39] [disk-manager] 全部重试用尽，用 fallback
[23:07:02] [docreview-ai] LLM 超时 ...
[23:11:10] [obsidian manager] LLM 超时 ...
[23:17:55] [_heart] LLM 成功 (83 chars)
[23:19:01] [推送] 失败 title=📅 2026-06-18 每日复盘
[23:19:01] === 完成 push_ok=False ===
```

- 总耗时 22 分钟（正常 1-2 分钟）。
- 三个项目（disk-manager / docreview-ai / obsidian manager）连续超时，每个吃掉 ~3 分钟（2 次 90s 重试 + fallback）。
- 最后飞书推送返回失败，但原代码只记 `[推送] 失败`，不记返回内容 — 黑箱。

### 根因

**根因 A — LLM 串行评估过载**：

`build_report()` 对所有活跃项目逐个跑评估。今日有动静的走 LLM（合理），**静默项目也走 LLM**（设计缺陷）：

```python
# 旧代码（agent/daily_recap.py:573-579）
for name in eval_names:
    if use_llm:
        sections.append(eval_one(name, all_active[name]))  # ← 16 个静默项目串行调 LLM
```

16 个静默项目串行，任何一个超时就把整条链路卡住。这违反了「LLM 是锦上添花，不能挡关键推送」的原则。

**根因 B — 飞书富文本走 cmd.exe 被 JSON 引号坑**：

`FeishuClient.send_rich_message` 原本走 `lark-cli.cmd`，大 JSON 里的双引号被 cmd.exe 重解析吃掉 — 这个坑交互卡片（`send_interactive_card`）早就踩过并改走 node 直连了，但富文本当时没同步修。

### 修复

| 文件 | 改动 | 目的 |
|---|---|---|
| `agent/daily_recap.py:259-260` | `LLM_TIMEOUT 90→45`、`LLM_RETRIES 2→1` | 单项目最坏 180s → 45s |
| `agent/daily_recap.py:573-576` | 静默项目评估改为只走 `_fallback_eval` 模板 | 16 个项目不再串行调 LLM |
| `agent/daily_recap.py:601-607` | 推送失败记录 `result` 详情（截断 1000 字符） | 下次能直接看到飞书返回的具体错误 |
| `agent/feishu_sync.py:106-145` | `send_rich_message` 加 node 直连分支（复用 `NODE_EXE` + `LARK_CLI_NODE_SCRIPT`，`shell=False`） | 绕过 cmd.exe 引号坑 |

### 验证

- `py_compile` 两个文件通过。
- `python daily_recap.py --dry-run --no-llm` 秒级返回，结构完整（2 个今日有动静项目 + 16 个静默项目模板评估 + 心力段）。
- **未主动发测试飞书消息**（半夜避免打扰老茅，留待下一次真实晚报验证）。

## 故障 2：状态栏 token 消失

### 现象

老茅：「终端对话框这，正常应该有项目和 token 消耗」— 状态栏空白。

### 根因

`settings.json` 顶层只有 3 个 key：`env` / `includeCoAuthoredBy` / `skipDangerousModePermissionPrompt`。**`statusLine` 字段不见了**。

脚本 `~/.claude/scripts/status_token.py` 完好（Jun 13 22:55），项目内 backup `agent/status_token_backup.py` 与 live 一致（diff IDENTICAL）。但 Claude Code 找不到 `statusLine` 配置，根本没调它。

时间线推断：6-13 密钥事故后重建 `settings.json` 时（见 memory `secret-leak-incident-2026-06-13`），只补回了 `env` 等核心字段，漏了 `statusLine`。

### 修复

不能用 Read/Edit（settings.json 含 `ANTHROPIC_AUTH_TOKEN`，全局禁读）。改用 python 脚本精确注入字段，密钥值不进对话上下文：

```python
d = json.load(open(p, encoding='utf-8'))
d['statusLine'] = {
    'type': 'command',
    'command': 'D:/miniconda3/python.exe "C:/Users/maoxu/.claude/scripts/status_token.py"',
    'padding': 0,
}
json.dump(d, f, ensure_ascii=False, indent=2)
```

- 备份：`~/.claude/settings.json.bak.20260619-234149`
- 验证：mock stdin 跑 `status_token.py`，输出 `🛰️ _ProjectOS 📊 今日 21.1M · 本月 2709.8M · 累计 2809.7M`，exit 0。

### 生效方式

状态栏在新会话或 `/statusline` 重载时才读新配置。当前会话不会立刻出现，需新开 Claude Code 窗口。

## 待办 / 后续

- [ ] 今晚 22:57 真实晚报验证推送是否恢复（应秒级返回 + 成功）。
- [ ] 若晚报仍失败，看 `daily_recap.log` 里新的 `[推送] 失败 result=...` 详情定位。
- [ ] statusline 在新会话确认蓝条 + token 出现。
- [ ] 考虑把 `settings.json` 关键字段（statusLine / env 存在性 / hooks）写进一个启动自检脚本，避免下次重建再漏。

## 教训

1. **重建关键配置文件要 checklist** — settings.json 重建漏 statusLine 花了 6 天才被发现（期间老茅一直没看到 token 用量）。重建 ≠ 恢复，要逐字段核对。
2. **LLM 不能挡关键推送链路** — 静默项目评估是「锦上添花」，用规则模板就够；LLM 只留给真正有今日动静的项目。
3. **飞书发送路径要统一** — cmd.exe 吃引号的坑早就修过一次（交互卡片），但富文本没同步，属于「同类坑踩两次」。下次改 CLI 调用方式要全量覆盖所有发送方法。
4. **失败日志要带原因** — `[推送] 失败` 四个字等于没记。已改成带 `result` 详情。
