#!/usr/bin/env python3
"""Status line script for Claude Code.

Reads stdin JSON (Claude Code passes session info), prints a single colored line:
    📊 今日 45K · 本月 2.3M · 累计 8.7M · [project]

Runs the aggregator inline (fast, due to mtime cache).
"""
import json
import os
import sys
from pathlib import Path

# Force UTF-8 output on Windows (Claude Code terminal is UTF-8 capable)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Import sibling module
sys.path.insert(0, str(Path(__file__).parent))
try:
    import token_stats
except Exception as e:
    print(f"\033[31m[token-stats error: {e}]\033[0m")
    sys.exit(0)


def fmt(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


PROJECT_EMOJI = {
    "PhysicsAI": "⚛️",
    "MailForge": "📧",
    "ProjectOS": "🛰️",
    "ai-router": "🔀",
    "obsidian": "🧠",
    "NuclearPowerAI": "☢️",
    "TexasPhilosopher": "🤠",
    "TokenChrono": "⏳",
    "docreview-ai": "📑",
    "disk-manager": "💾",
    "ValveDrawing": "🔧",
    "claude-channel": "📡",
    "product-idea": "💡",
    "AI-NoteBook": "📓",
    "upwork": "💼",
}


def project_label(cwd):
    if not cwd:
        return "📁 ?"
    name = os.path.basename(cwd.rstrip("\\/")) or cwd
    for key, emo in PROJECT_EMOJI.items():
        if key.lower() in cwd.lower():
            return f"{emo} {name}"
    return f"📁 {name}"


def resolve_cwd(stdin_data):
    """三层 fallback：stdin workspace → CLAUDE_PROJECT_DIR env → os.getcwd()。"""
    if stdin_data:
        cwd = (stdin_data.get("workspace") or {}).get("current_dir") or stdin_data.get("cwd")
        if cwd:
            return cwd
    env_cwd = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_cwd:
        return env_cwd
    return os.getcwd()


def main():
    data = None
    try:
        raw = sys.stdin.read()
        if raw.strip():
            data = json.loads(raw)
    except Exception:
        pass

    cwd = resolve_cwd(data)

    try:
        token_stats.aggregate()
        s = token_stats.summarize()
    except Exception as e:
        print(f"\033[31m📊 stats error: {e}\033[0m")
        return

    # 蓝条项目名置顶（蓝底白字 + bold），其余 token 信息跟在后面
    proj_text = project_label(cwd)
    proj_bar = f"\033[1;97;44m {proj_text} \033[0m"

    today = f"\033[36m今日 {fmt(s['today'])}\033[0m"
    month = f"\033[33m本月 {fmt(s['month'])}\033[0m"
    total = f"\033[90m累计 {fmt(s['grand_total'])}\033[0m"
    print(f"{proj_bar} 📊 {today} · {month} · {total}", end="")


if __name__ == "__main__":
    main()
