#!/usr/bin/env python3
"""
save_conversation_turn.py — Claude Code hook: 自动保存对话轮次到项目本地文件

作为 Claude Code 的 Stop hook 使用。每轮助手回复完成后触发，
将用户消息 + 助手回复追加到项目目录下的 conversation_log/ 日期文件中。

安装方式：在 .claude/settings.json 的 hooks 中注册 Stop 事件。
"""
from __future__ import annotations

import json
import sys
import os
from datetime import datetime
from pathlib import Path

# 项目根目录 — 按当前工作目录自动定位
CWD = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
PROJECT_ROOT = Path(CWD)
LOG_DIR = PROJECT_ROOT / "conversation_log"
TEMP_PROMPT = PROJECT_ROOT / ".claude" / ".last_user_prompt.txt"


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    event = data.get("hook_event_name", "")
    session_id = data.get("session_id", "unknown")

    if event == "UserPromptSubmit":
        # 保存用户消息到临时文件，等 Stop hook 读取
        prompt_text = ""
        # UserPromptSubmit 的 stdin 结构：data.message.content 可能是 str 或 list
        msg = data.get("message", {})
        content = msg.get("content", "")
        if isinstance(content, str):
            prompt_text = content
        elif isinstance(content, list):
            # content 是 block list，取 text block
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            prompt_text = "\n".join(parts)
        elif isinstance(data.get("prompt"), str):
            prompt_text = data["prompt"]

        if prompt_text:
            TEMP_PROMPT.parent.mkdir(parents=True, exist_ok=True)
            TEMP_PROMPT.write_text(prompt_text, encoding="utf-8")
        return

    if event == "Stop":
        assistant_msg = data.get("last_assistant_message", "")
        user_msg = ""
        if TEMP_PROMPT.exists():
            try:
                user_msg = TEMP_PROMPT.read_text(encoding="utf-8").strip()
                TEMP_PROMPT.unlink()
            except Exception:
                pass

        if not user_msg and not assistant_msg:
            return

        # 过滤掉纯工具调用轮（assistant_msg 为空但 user_msg 有内容 = 可能是工具结果）
        if not assistant_msg.strip() and not user_msg.strip():
            return

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = LOG_DIR / f"{today}.md"

        ts = datetime.now().strftime("%H:%M:%S")

        with open(log_file, "a", encoding="utf-8") as f:
            # 如果文件是新建的，写头部
            if f.tell() == 0:
                f.write(f"# 对话日志 {today}\n\n")
                f.write(f"Session: `{session_id[:8]}...`\n\n")

            f.write(f"## {ts}\n\n")
            if user_msg:
                # 截断过长的用户消息
                display = user_msg[:2000] + ("..." if len(user_msg) > 2000 else "")
                f.write(f"**User:**\n\n{display}\n\n")
            if assistant_msg:
                display = assistant_msg[:4000] + ("..." if len(assistant_msg) > 4000 else "")
                f.write(f"**Assistant:**\n\n{display}\n\n")
            f.write("---\n\n")


if __name__ == "__main__":
    main()
