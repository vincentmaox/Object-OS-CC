#!/usr/bin/env python3
"""
daily_recap.py - 每晚 23:00 全项目极简日报

收集每个活跃项目当日的动静（git commits / CHANGELOG / journal / 思考池），
调火山方舟代理总结成五段式（做成/失败/教训/下一步/状态），推飞书。

用法：
  python daily_recap.py              # 正常执行
  python daily_recap.py --dry-run    # 只打印不推
  python daily_recap.py --no-llm     # 跳过 LLM，输出原始数据
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

WORKDIR = Path(r"D:\ClaudeCodeProjects\_ProjectOS")
REGISTRY = WORKDIR / "data" / "registry.json"
INBOX = WORKDIR / "thoughts" / "inbox.md"
BASE_DIR = Path(r"D:\ClaudeCodeProjects")
OPEN_ID = "ou_59a5d4b0cc115a66295961a1aec66a9e"

ANCHOR = "<!-- BOT_APPEND_BELOW_THIS_LINE -->"
THOUGHT_RE = re.compile(
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\]\s+\[(?P<project>[^\]]+)\]\s+(?P<text>.+?)\s*$"
)

# 让模块导入时把 cc_bot.env 灌进环境（NSSM/schtasks 跑时未必继承 User env）
def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

load_env_file(WORKDIR / "agent" / "cc_bot.env")


def today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


def git_commits_today(project_path: Path) -> list[str]:
    """项目今日 commit 标题列表（短 SHA + subject）。"""
    if not (project_path / ".git").exists():
        return []
    try:
        out = subprocess.run(
            ["git", "log", "--since=midnight", "--pretty=format:%h %s", "--all"],
            cwd=project_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        return [l for l in out.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def changelog_today_lines(project_path: Path) -> list[str]:
    """CHANGELOG.md 中今日提到的新增行（粗略：找包含今日日期的段落）。"""
    cl = project_path / "CHANGELOG.md"
    if not cl.exists():
        return []
    try:
        text = cl.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    today = today_str()
    # 找包含今日日期的 section，截取到下一个 ## 标题前
    lines = text.splitlines()
    out, in_section = [], False
    for ln in lines:
        if ln.startswith("## ") and today in ln:
            in_section = True
            continue
        if in_section and ln.startswith("## "):
            break
        if in_section and ln.strip():
            out.append(ln.rstrip())
    return out[:30]  # 最多 30 行避免 prompt 爆


def journal_today_files(project_path: Path) -> list[str]:
    """docs/journal/ 下今日新增/修改的文件名。"""
    jdir = project_path / "docs" / "journal"
    if not jdir.exists():
        return []
    today = today_str()
    out = []
    for f in jdir.glob("*.md"):
        # 文件名带日期，或 mtime 在今天
        if today in f.name:
            out.append(f.name)
            continue
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime).date()
            if mtime == date.today():
                out.append(f.name)
        except Exception:
            pass
    return out


def thoughts_today_for(project: str) -> list[str]:
    """思考池 inbox 中今日新增的、该项目的思考文本。"""
    if not INBOX.exists():
        return []
    content = INBOX.read_text(encoding="utf-8")
    if ANCHOR not in content:
        return []
    payload = content.split(ANCHOR, 1)[1]
    today = date.today()
    out = []
    for line in payload.splitlines():
        m = THOUGHT_RE.match(line.strip())
        if not m:
            continue
        try:
            ts = datetime.fromisoformat(m.group("ts"))
        except Exception:
            continue
        if ts.date() == today and m.group("project").strip() == project:
            out.append(m.group("text").strip())
    return out


def collect_today_activity(registry: dict) -> dict[str, dict]:
    """遍历活跃项目，收集今日动静 + 注册表元数据。

    返回 {project: {commits, changelog, journal, thoughts, status, ...registry_meta}}。
    只保留至少有一项今日动静非空的项目。
    """
    result = {}
    for name, info in registry.get("projects", {}).items():
        status = info.get("status", "")
        if status in ("已归档", "已Kill", "killed"):
            continue
        path = Path(info.get("path", ""))
        if not path.exists():
            continue
        activity = {
            "commits": git_commits_today(path),
            "changelog": changelog_today_lines(path),
            "journal": journal_today_files(path),
            "thoughts": thoughts_today_for(name),
            "status": status,
            # registry 元数据（供评估用）
            "days_since_edit": info.get("activity", {}).get("days_since_edit"),
            "days_since_code": info.get("activity", {}).get("days_since_code"),
            "blockers": [b.get("severity", "") + ": " + b.get("type", "") for b in info.get("blockers", [])],
            "missing_docs": info.get("docs", {}).get("missing_critical", []),
            "tech_stack": info.get("tech", {}).get("stack", []),
            "deploy_ready": info.get("tech", {}).get("deploy_ready", False),
            "file_count": info.get("activity", {}).get("file_count", 0),
        }
        if any([activity["commits"], activity["changelog"],
                activity["journal"], activity["thoughts"]]):
            result[name] = activity
    return result


def build_prompt_for(project: str, activity: dict) -> str:
    """单项目 LLM 总结 prompt。"""
    parts = [f"# 项目：{project}\n", f"当前状态：{activity['status']}\n"]
    if activity["commits"]:
        parts.append("## 今日 Git commits")
        parts.extend(f"- {c}" for c in activity["commits"])
        parts.append("")
    if activity["changelog"]:
        parts.append("## 今日 CHANGELOG 新增")
        parts.extend(activity["changelog"])
        parts.append("")
    if activity["journal"]:
        parts.append("## 今日 journal 新增")
        parts.extend(f"- {f}" for f in activity["journal"])
        parts.append("")
    if activity["thoughts"]:
        parts.append("## 今日新思考")
        parts.extend(f"- {t}" for t in activity["thoughts"])
        parts.append("")
    raw = "\n".join(parts)
    return (
        "请基于以下项目今日动静原始数据，输出**极简日报五段式**（每段一行，没有内容写「无」）：\n"
        "- 做成：今天交付了什么\n"
        "- 失败：今天碰壁了什么\n"
        "- 教训：可固化的经验\n"
        "- 下一步：明日/近期最该做的一件事\n"
        "- 状态：用 ✅ 推进 / ⚠️ 卡点 / 🛑 待决断 / 💤 静默 中选一个\n\n"
        "禁止扩写、禁止重复原文、禁止评分。每段不超过 40 字。\n\n"
        f"---\n{raw}"
    )


def summarize_one(project: str, activity: dict) -> str:
    """调 claude-agent-sdk 总结一个项目（复用 sdk_bot_server 验证过的链路）。

    失败回退原始数据 markdown。同步入口，内部跑 asyncio。
    """
    try:
        import asyncio
        from claude_agent_sdk import (
            ClaudeSDKClient, ClaudeAgentOptions,
            AssistantMessage, TextBlock,
        )
    except ImportError:
        return _fallback_render(project, activity)

    prompt = build_prompt_for(project, activity)

    async def _run() -> str:
        options = ClaudeAgentOptions(
            permission_mode="default",
            setting_sources=[],
            max_turns=1,
            cwd=str(WORKDIR),
            env={
                k: v for k, v in os.environ.items()
                if k.startswith("ANTHROPIC_") or k in (
                    "PATH", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
                    "HOME", "TEMP", "TMP", "SystemRoot",
                    "ProgramFiles", "ProgramFiles(x86)",
                )
            },
        )
        parts: list[str] = []
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for b in msg.content:
                        if isinstance(b, TextBlock):
                            parts.append(b.text)
        return "".join(parts).strip()

    try:
        text = asyncio.run(_run())
        if not text:
            return _fallback_render(project, activity)
        return f"### {project}\n{text}\n"
    except Exception as e:
        print(f"[WARN] {project} LLM 总结失败: {e}", file=sys.stderr)
        return _fallback_render(project, activity)


def _fallback_render(project: str, activity: dict) -> str:
    """LLM 失败或 --no-llm 时的纯模板渲染。"""
    lines = [f"### {project}（{activity['status']}）"]
    if activity["commits"]:
        lines.append(f"- 做成：{len(activity['commits'])} commits — {activity['commits'][0].split(' ', 1)[1] if ' ' in activity['commits'][0] else activity['commits'][0]}")
    else:
        lines.append("- 做成：无 commit")
    if activity["changelog"]:
        lines.append(f"- CHANGELOG：{len(activity['changelog'])} 行新增")
    if activity["journal"]:
        lines.append(f"- Journal：{', '.join(activity['journal'])}")
    if activity["thoughts"]:
        lines.append(f"- 新思考：{activity['thoughts'][0][:50]}")
    lines.append("- 状态：✅ 推进" if activity["commits"] else "- 状态：💤 静默")
    return "\n".join(lines) + "\n"


def build_report(registry: dict, use_llm: bool = True) -> tuple[str, str]:
    """返回 (title, content) 用于飞书 send_rich_message。"""
    today = today_str()
    activities = collect_today_activity(registry)
    title = f"📅 {today} 每日复盘"

    if not activities:
        return title, "今日所有活跃项目无动静。建议看看是否需要重排优先级。"

    sections = []
    for name in sorted(activities.keys()):
        if use_llm:
            sections.append(summarize_one(name, activities[name]))
        else:
            sections.append(_fallback_render(name, activities[name]))

    footer = f"\n---\n共 {len(activities)} 个项目今日有动静。"
    return title, "\n".join(sections) + footer


def push_to_feishu(title: str, content: str) -> bool:
    sys.path.insert(0, str(WORKDIR / "agent"))
    try:
        from feishu_sync import FeishuClient
        client = FeishuClient()
        result = client.send_rich_message(
            target=OPEN_ID,
            title=title,
            content=content,
            target_type="user_id",
        )
        return bool(result.get("data"))
    except Exception as e:
        print(f"[ERROR] 推飞书失败: {e}", file=sys.stderr)
        return False


def main():
    if not REGISTRY.exists():
        print(f"[ERROR] registry 不存在: {REGISTRY}", file=sys.stderr)
        sys.exit(1)

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    use_llm = "--no-llm" not in sys.argv
    title, content = build_report(registry, use_llm=use_llm)

    print(f"=== {title} ===")
    print(content)
    print()

    if "--dry-run" in sys.argv:
        print("[DRY-RUN] 跳过推送")
        return

    ok = push_to_feishu(title, content)
    print(f"[推送] {'成功' if ok else '失败'}")


if __name__ == "__main__":
    main()
