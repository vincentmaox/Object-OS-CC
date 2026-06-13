#!/usr/bin/env python3
"""
save_conversation_turn.py — Claude Code hook: 三层防御对话存档

支持四个 hook 事件：

| Event             | 行为                                                            |
|-------------------|-----------------------------------------------------------------|
| UserPromptSubmit  | 老茅 prompt 一提交就 append 到 today.md，标记 [PENDING:sid]    |
| Stop              | 找到最后一个 [PENDING:sid] 块，追加老赫回复，清掉标记           |
| PreCompact        | 压缩前把整段 transcript 快照存到 conversation_log/_snapshots/  |
| SessionStart      | 启动时输出近 5 轮对话摘要到 stdout，自动注入上下文              |

主体标签：**老茅:** / **老赫:**（命名详见 memory/assistant-identity.md）

安装：在 .claude/settings.json 注册四个 hook 都指向本脚本。
"""
from __future__ import annotations

import json
import sys
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

# Windows 默认 cp936 — 强制 stdout/stderr utf-8 输出，否则 SessionStart 注入摘要中文乱码
for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    if stream and stream.encoding and stream.encoding.lower() not in ("utf-8", "utf8"):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

CWD = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
PROJECT_ROOT = Path(CWD)
LOG_DIR = PROJECT_ROOT / "conversation_log"
SNAPSHOT_DIR = LOG_DIR / "_snapshots"

USER_LABEL = "老茅"
ASSISTANT_LABEL = "老赫"

USER_TRUNC = 4000
ASSISTANT_TRUNC = 8000


def _today_log() -> Path:
    return LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.md"


def _ensure_header(fp, session_id: str):
    if fp.tell() == 0:
        today = datetime.now().strftime("%Y-%m-%d")
        fp.write(f"# 对话日志 {today}\n\n")
        fp.write(f"Session: `{session_id[:8]}...`\n\n")


def _extract_user_prompt(data: dict) -> str:
    msg = data.get("message", {})
    content = msg.get("content", "") if isinstance(msg, dict) else ""
    if isinstance(content, str) and content:
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        joined = "\n".join(p for p in parts if p)
        if joined:
            return joined
    if isinstance(data.get("prompt"), str):
        return data["prompt"]
    return ""


def _truncate(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    return text[:n] + f"\n\n... [truncated {len(text) - n} chars]"


def handle_user_prompt_submit(data: dict):
    """老茅一提交 prompt 就落盘。"""
    session_id = data.get("session_id", "unknown")
    sid_short = session_id[:8]
    prompt_text = _extract_user_prompt(data).strip()
    if not prompt_text:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = _today_log()
    ts = datetime.now().strftime("%H:%M:%S")

    with open(log_file, "a", encoding="utf-8") as f:
        _ensure_header(f, session_id)
        f.write(f"## {ts} [PENDING:{sid_short}]\n\n")
        f.write(f"**{USER_LABEL}:**\n\n{_truncate(prompt_text, USER_TRUNC)}\n\n")


def handle_stop(data: dict):
    """老赫回复完成，找到最后一个 [PENDING:sid] 块补上回复。"""
    session_id = data.get("session_id", "unknown")
    sid_short = session_id[:8]
    assistant_msg = (data.get("last_assistant_message") or "").strip()

    log_file = _today_log()
    if not log_file.exists():
        # 没有 prompt 落盘记录（可能是 SessionStart 后第一轮被跳过等）— 兜底新建
        if not assistant_msg:
            return
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            _ensure_header(f, session_id)
            f.write(f"## {ts}\n\n")
            f.write(f"**{ASSISTANT_LABEL}:**\n\n{_truncate(assistant_msg, ASSISTANT_TRUNC)}\n\n---\n\n")
        return

    text = log_file.read_text(encoding="utf-8")
    marker = f"[PENDING:{sid_short}]"

    # 找最后一个本 session 的 PENDING 块（严格匹配 sid，避免吃掉别的 session）
    idx = text.rfind(marker)
    if idx == -1:
        # 没有 PENDING 块（可能 prompt 没被 hook 捕获）— 直接 append 一段
        if not assistant_msg:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"## {ts}\n\n**{ASSISTANT_LABEL}:**\n\n{_truncate(assistant_msg, ASSISTANT_TRUNC)}\n\n---\n\n")
        return

    # 1. 清 PENDING 标记（含前导空格）
    head = text[:idx].rstrip(" ")
    tail = text[idx + len(marker):]
    new_text = head + tail

    # 2. 在文件末尾追加老赫块
    if assistant_msg:
        body = f"\n**{ASSISTANT_LABEL}:**\n\n{_truncate(assistant_msg, ASSISTANT_TRUNC)}\n\n---\n\n"
        new_text = new_text.rstrip() + "\n\n" + body.lstrip()
    else:
        # 空回复 — 也清 PENDING，加分隔符
        new_text = new_text.rstrip() + "\n\n---\n\n"

    log_file.write_text(new_text, encoding="utf-8")


def handle_pre_compact(data: dict):
    """压缩前快照整段 transcript。"""
    transcript_path = data.get("transcript_path") or data.get("transcriptPath")
    if not transcript_path:
        return
    src = Path(transcript_path)
    if not src.exists():
        return
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    session_id = data.get("session_id", "unknown")[:8]
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dst = SNAPSHOT_DIR / f"{ts}_{session_id}_precompact.jsonl"
    try:
        shutil.copy2(src, dst)
    except Exception:
        pass


def handle_session_start(data: dict):
    """启动时把近 5 轮对话喂回上下文。"""
    log_file = _today_log()
    candidates = []
    if log_file.exists():
        candidates.append(log_file)
    # 还不够就拿前几天
    if LOG_DIR.exists():
        all_logs = sorted(
            [p for p in LOG_DIR.glob("*.md") if p.is_file()],
            reverse=True,
        )
        for p in all_logs:
            if p not in candidates:
                candidates.append(p)
            if len(candidates) >= 3:
                break

    if not candidates:
        return

    # 提取最后 5 个 turn（## 时间戳 段）
    turns = []
    for p in candidates:
        text = p.read_text(encoding="utf-8", errors="replace")
        # 按 ## 切（保留分隔符）
        blocks = re.split(r"^## ", text, flags=re.MULTILINE)
        for b in blocks[1:]:
            if not b.strip():
                continue
            turns.append((p.stem, "## " + b.rstrip()))
        if len(turns) >= 10:
            break

    if not turns:
        return

    # 取最近 5 轮（按文件顺序，文件内是时间正序）
    recent = turns[-5:]
    print("# 近期对话回顾（自动注入）\n")
    print(f"_来自 {LOG_DIR.relative_to(PROJECT_ROOT) if LOG_DIR.is_relative_to(PROJECT_ROOT) else LOG_DIR}_\n")
    for date_stem, body in recent:
        snippet = body[:1500] + ("..." if len(body) > 1500 else "")
        print(f"### [{date_stem}]\n{snippet}\n")


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    event = data.get("hook_event_name", "")

    if event == "UserPromptSubmit":
        handle_user_prompt_submit(data)
    elif event == "Stop":
        handle_stop(data)
    elif event == "PreCompact":
        handle_pre_compact(data)
    elif event == "SessionStart":
        handle_session_start(data)


if __name__ == "__main__":
    main()
