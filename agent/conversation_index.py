#!/usr/bin/env python3
"""
conversation_index.py — 对话存档检索 API

读 conversation_log/*.md，提供三个调阅入口：

  python conversation_index.py last [N]            # 近 N 轮（默认 5）
  python conversation_index.py search <keyword>    # 全文搜索
  python conversation_index.py recall <project>    # 按项目名召回

输出：紧凑 markdown，可直接喂回老赫上下文或飞书 Bot /recall 命令。

主体标签：**老茅:** / **老赫:**
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Iterable

# Windows 默认 cp936 — 强制 stdout utf-8 输出，否则中文乱码
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

CWD = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
PROJECT_ROOT = Path(CWD)
LOG_DIR = PROJECT_ROOT / "conversation_log"

USER_LABEL = "老茅"
ASSISTANT_LABEL = "老赫"

TURN_HEADER = re.compile(r"^## (\d{2}:\d{2}:\d{2})", re.MULTILINE)


def _iter_log_files() -> list[Path]:
    if not LOG_DIR.exists():
        return []
    return sorted([p for p in LOG_DIR.glob("*.md") if p.is_file()])


def _split_turns(text: str, date: str) -> list[dict]:
    """把一份日志切成 turn list。每个 turn = {date, time, body}。"""
    turns = []
    blocks = re.split(r"^## ", text, flags=re.MULTILINE)
    for b in blocks[1:]:
        if not b.strip():
            continue
        first_line, _, rest = b.partition("\n")
        time = first_line.strip().split()[0] if first_line.strip() else "??:??:??"
        # 干掉 [PENDING:xxx] 这种残留
        time = time.replace(",", "").strip()
        turns.append({
            "date": date,
            "time": time,
            "body": "## " + b.rstrip(),
        })
    return turns


def _all_turns() -> list[dict]:
    out = []
    for p in _iter_log_files():
        text = p.read_text(encoding="utf-8", errors="replace")
        out.extend(_split_turns(text, p.stem))
    return out


def cmd_last(n: int = 5) -> str:
    turns = _all_turns()
    if not turns:
        return "_(无存档)_"
    recent = turns[-n:]
    lines = [f"# 近 {len(recent)} 轮对话\n"]
    for t in recent:
        lines.append(f"### [{t['date']} {t['time']}]\n")
        body = t["body"]
        # 去掉时间行（已在 heading 体现）
        body = re.sub(r"^## \S+\s*", "", body, count=1)
        if len(body) > 2000:
            body = body[:2000] + "\n\n... [truncated]"
        lines.append(body)
        lines.append("")
    return "\n".join(lines)


def cmd_search(keyword: str, limit: int = 10) -> str:
    if not keyword:
        return "_(关键词为空)_"
    keyword_lower = keyword.lower()
    hits = []
    for t in _all_turns():
        if keyword_lower in t["body"].lower():
            hits.append(t)
    hits = hits[-limit:]  # 最近的 N 个
    if not hits:
        return f"_未找到包含 `{keyword}` 的对话_"
    lines = [f"# 搜索 `{keyword}` — {len(hits)} 命中\n"]
    for t in hits:
        body = t["body"]
        body = re.sub(r"^## \S+\s*", "", body, count=1)
        # 高亮关键词所在段（截前后 200 字）
        idx = body.lower().find(keyword_lower)
        start = max(0, idx - 200)
        end = min(len(body), idx + len(keyword) + 200)
        snippet = ("..." if start > 0 else "") + body[start:end] + ("..." if end < len(body) else "")
        lines.append(f"### [{t['date']} {t['time']}]\n\n{snippet}\n")
    return "\n".join(lines)


def cmd_recall(project: str, limit: int = 10) -> str:
    """按项目名召回 — 模糊匹配项目名出现的对话。"""
    if not project:
        return "_(项目名为空)_"
    project_lower = project.lower()
    hits = []
    for t in _all_turns():
        body_lower = t["body"].lower()
        # 匹配 [项目名] 或者直接出现项目名
        if f"[{project_lower}]" in body_lower or project_lower in body_lower:
            hits.append(t)
    hits = hits[-limit:]
    if not hits:
        return f"_项目 `{project}` 在对话中未出现_"
    lines = [f"# 项目 `{project}` 相关对话 — {len(hits)} 命中\n"]
    for t in hits:
        body = t["body"]
        body = re.sub(r"^## \S+\s*", "", body, count=1)
        if len(body) > 1500:
            body = body[:1500] + "\n... [truncated]"
        lines.append(f"### [{t['date']} {t['time']}]\n\n{body}\n")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "last":
        n = int(argv[2]) if len(argv) > 2 else 5
        print(cmd_last(n))
    elif cmd == "search":
        kw = " ".join(argv[2:])
        print(cmd_search(kw))
    elif cmd == "recall":
        proj = " ".join(argv[2:])
        print(cmd_recall(proj))
    else:
        print(f"unknown command: {cmd}")
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
