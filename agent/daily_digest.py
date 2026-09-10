#!/usr/bin/env python3
"""
daily_digest.py — 精简群日报（发「AI项目」群，早晚各一条）

v0.7.0 信息减负改造（2026-09-10，老茅拍板）：
- 替代 send-cards（90+ 张项目确认卡片，信息过载源头）
- 替代 daily_recap.py 的 96 段巨长私聊汇总（其中 ~100 次 LLM 调用）
- 早报：今日主频咒语 + 今天最重要启动的三个项目（1 条消息，1 次 LLM）
- 晚报：今日进展 + 重点关注 + 关键卡壳点 + 静默预警（1 条消息，1 次 LLM）

用法:
  python daily_digest.py --morning [--dry-run]
  python daily_digest.py --evening [--dry-run]
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

WORKDIR = Path(r"D:\ClaudeCodeProjects\_ProjectOS")
REGISTRY = WORKDIR / "data" / "registry.json"
FREQ_DAILY_LOG = WORKDIR / "frequency_os" / "daily_log.md"
DIGEST_LOG = WORKDIR / "agent" / "daily_digest.log"

# 「AI项目」群（2026-09-10 老茅建，bot 已入群）
GROUP_CHAT_ID = "oc_5d4f19d5324dc0f84a9377796ff8e9e5"

# 让模块导入时把 cc_bot.env 灌进环境，再用 CC Switch settings.json 覆盖 ANTHROPIC_*
from env_loader import load_all

load_all(WORKDIR / "agent" / "cc_bot.env")

LLM_TIMEOUT = 180  # 单次 digest LLM 调用超时（一次生成整份内容，比旧版 96 次调用省时省 token）


def today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


def _log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, file=sys.stderr, flush=True)
    try:
        with open(DIGEST_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# === 数据收集 ===

def _compact_active(registry: dict) -> list[dict]:
    """全活跃项目的紧凑指标（含路径，供 LLM 挑选）。"""
    out = []
    for name, info in registry.get("projects", {}).items():
        status = info.get("status", "")
        if status in ("已归档", "已Kill", "killed"):
            continue
        if not Path(info.get("path", "")).exists():
            continue
        act = info.get("activity", {})
        blockers = info.get("blockers", [])
        out.append({
            "name": info.get("name") or name,
            "path": info.get("path", ""),
            "status": status,
            "mva": info.get("mva_decision", ""),
            "days_edit": act.get("days_since_edit"),
            "days_code": act.get("days_since_code"),
            "blockers": [
                f"{b.get('severity', '?')}:{b.get('type', '?')} {str(b.get('message', ''))[:60]}"
                for b in blockers[:2]
            ],
        })
    return out


def _render_project_line(p: dict) -> str:
    """单项目一行给 LLM 的摘要。"""
    parts = [p["name"], f"状态:{p['status'] or '?'}"]
    if p["mva"]:
        parts.append(f"MVA:{p['mva']}")
    if p["days_edit"] is not None:
        parts.append(f"静默:{p['days_edit']:.0f}天")
    if p["blockers"]:
        parts.append("卡点[" + "; ".join(p["blockers"]) + "]")
    return "- " + " | ".join(parts)


def _read_freq_today() -> tuple[str, str]:
    """读 frequency_os 今日主频 + 咒语（缺失返回空）。"""
    if not FREQ_DAILY_LOG.exists():
        return "", ""
    try:
        text = FREQ_DAILY_LOG.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "", ""
    today = today_str()
    m = re.search(rf"## {re.escape(today)}.*?(?=\n## |\Z)", text, re.S)
    if not m:
        return "", ""
    block = m.group(0)

    def grep(p: str) -> str:
        mm = re.search(p, block)
        return mm.group(1).strip() if mm else ""

    return grep(r"今日唯一主频：[ \t]*([^\n]+)"), grep(r"今日主频咒语：[ \t]*([^\n]+)")


def _today_activity(registry: dict) -> dict[str, dict]:
    """今日有动静项目的原始动静（复用 daily_recap 的收集器）。"""
    sys.path.insert(0, str(WORKDIR / "agent"))
    from daily_recap import collect_today_activity
    return collect_today_activity(registry)


# === LLM ===

def _llm(prompt: str, tag: str) -> str | None:
    """单次 LLM 调用生成整份 digest。失败返回 None 走 fallback。"""
    try:
        from claude_agent_sdk import (
            ClaudeSDKClient, ClaudeAgentOptions,
            AssistantMessage, TextBlock,
        )
    except ImportError:
        _log(f"[{tag}] SDK 不可导入")
        return None

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
        text = asyncio.run(asyncio.wait_for(_run(), timeout=LLM_TIMEOUT))
        if not text:
            _log(f"[{tag}] LLM 返回空")
            return None
        _log(f"[{tag}] LLM 成功 ({len(text)} chars)")
        return text
    except Exception as e:
        _log(f"[{tag}] LLM 异常: {e}")
        return None


# === 早报 ===

def build_morning(registry: dict) -> tuple[str, str]:
    """早 9 点：今日主频 + 最重要启动的三个项目。"""
    today = today_str()
    actives = _compact_active(registry)
    title = f"🌅 早报 · {today} — 今日三启动"

    projects_block = "\n".join(_render_project_line(p) for p in actives)
    prompt = (
        "你是老茅（虚空建筑师）的项目参谋。下面是他所有活跃项目的当日指标快照。\n"
        f"请选出**今天最该启动的 3 个项目**。挑选标准：\n"
        "1. All-in / 活跃状态优先，接近交付或决断窗口的优先\n"
        "2. 有卡点但可突破的优先（卡点是今天的突破口）\n"
        "3. 长期静默但 MVA=All-in 的需要激活\n"
        "禁止选已归档项目，禁止并列第 4 名。\n\n"
        "输出格式（严格遵守，不要多余文字）：\n"
        "1. <项目名>\n   为什么: <≤25字>\n   首个动作: <具体可执行, ≤30字>\n"
        "2. <项目名>\n   ...\n3. <项目名>\n   ...\n\n"
        f"---\n共 {len(actives)} 个活跃项目：\n{projects_block}"
    )
    body = _llm(prompt, "morning")

    if not body:
        # fallback: 按指标粗排前 3（All-in > 有卡点 > 最近活跃）
        def _sort_key(p: dict):
            score = 0
            if p["mva"] == "All-in":
                score += 100
            if p["status"] in ("活跃", "进行中"):
                score += 50
            if p["blockers"]:
                score += 20
            if p["days_edit"] is not None and p["days_edit"] < 3:
                score += 10
            return -score
        top3 = sorted(actives, key=_sort_key)[:3]
        body = "\n".join(
            f"{i}. {p['name']}（{p['status']}{', MVA=' + p['mva'] if p['mva'] else ''}）"
            for i, p in enumerate(top3, 1)
        )

    main_freq, mantra = _read_freq_today()
    freq_block = ""
    if main_freq:
        freq_block = f"🎯 **今日主频**：{main_freq}\n"
        if mantra:
            freq_block += f"📜 **咒语**：{mantra}\n\n"

    content = f"{freq_block}**今天最重要启动的三个项目：**\n\n{body}\n\n_（AI 挑选 · 共 {len(actives)} 活跃项目）_"
    return title, content


# === 晚报 ===

def build_evening(registry: dict) -> tuple[str, str]:
    """晚 21:30：今日进展 + 重点关注 + 关键卡壳点 + 静默预警。"""
    today = today_str()
    actives = _compact_active(registry)
    activities = _today_activity(registry)
    title = f"🌙 晚报 · {today} — 项目进展汇总"

    # 今日动静详情（有动静的项目）
    dyn_parts = []
    for name in sorted(activities.keys()):
        a = activities[name]
        seg = [f"### {name}（{a['status']}）"]
        if a["commits"]:
            seg.append("commits: " + " / ".join(
                c.split(" ", 1)[1][:60] if " " in c else c for c in a["commits"][:5]))
        if a["changelog"]:
            seg.append(f"changelog +{len(a['changelog'])} 行")
        if a["journal"]:
            seg.append("journal: " + ", ".join(a["journal"][:3]))
        if a["thoughts"]:
            seg.append("思考: " + " / ".join(t[:50] for t in a["thoughts"][:2]))
        dyn_parts.append("\n".join(seg))
    dyn_block = "\n\n".join(dyn_parts) if dyn_parts else "（今日无项目动静）"

    # 全活跃指标快照
    metrics_block = "\n".join(_render_project_line(p) for p in actives)

    prompt = (
        "你是老茅的项目参谋。基于今日项目动静 + 全活跃项目指标，输出**晚报汇总**。\n"
        "要求：每段聚焦重点，禁止罗列全部项目，总输出不超过 45 行。\n\n"
        "输出格式（严格遵守）：\n"
        "## 📈 今日进展\n（有动静的项目每个一行：`项目 — 一句话干了什么`；没有动静则写「今日无动静」）\n"
        "## ⭐ 重点关注\n（3-5 个明天该优先关注的项目，每个一行带理由）\n"
        "## 🚧 关键卡壳点\n（高优先级卡点的要点 + 一句建议动作，最多 5 条；没有则写「无」）\n"
        "## 💤 静默预警\n（MVA=All-in 或状态活跃但静默 >7 天的，一行一个，最多 5 个；没有则写「无」）\n\n"
        f"---\n## 今日动静详情：\n{dyn_block}\n\n---\n## 全部 {len(actives)} 个活跃项目指标：\n{metrics_block}"
    )
    body = _llm(prompt, "evening")

    if not body:
        # fallback: 纯模板
        lines = ["## 📈 今日进展"]
        for name in sorted(activities.keys()):
            a = activities[name]
            first = a["commits"][0] if a["commits"] else (a["thoughts"][0][:40] if a["thoughts"] else "动静")
            lines.append(f"- {name} — {first}")
        if not activities:
            lines.append("今日无动静")
        blockers = [(p["name"], b) for p in actives for b in p["blockers"]]
        lines.append("\n## 🚧 关键卡壳点")
        for name, b in blockers[:5]:
            lines.append(f"- {name}: {b}")
        if not blockers:
            lines.append("- 无")
        body = "\n".join(lines)

    content = body + f"\n\n---\n_（共 {len(activities)} 项目有动静 · {len(actives)} 活跃 · AI 汇总）_"
    return title, content


# === 推送 ===

def push_to_group(title: str, content: str) -> bool:
    sys.path.insert(0, str(WORKDIR / "agent"))
    from feishu_sync import FeishuClient
    client = FeishuClient()
    result = client.send_rich_message(
        target=GROUP_CHAT_ID,
        title=title,
        content=content,
        target_type="chat_id",
    )
    ok = bool(result.get("data"))
    _log(f"[推送] {'成功' if ok else '失败'} title={title} result={json.dumps(result, ensure_ascii=False)[:500]}")
    return ok


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    dry_run = "--dry-run" in sys.argv
    _log(f"=== 启动 daily_digest mode={mode} args={sys.argv[1:]} ===")

    if mode not in ("--morning", "--evening"):
        print("Usage: python daily_digest.py --morning|--evening [--dry-run]")
        sys.exit(1)
    if not REGISTRY.exists():
        _log(f"[ERROR] registry 不存在: {REGISTRY}")
        sys.exit(1)

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    title, content = (build_morning if mode == "--morning" else build_evening)(registry)

    print(f"=== {title} ===")
    print(content)
    print()

    if dry_run:
        _log("[DRY-RUN] 跳过推送")
        return
    ok = push_to_group(title, content)
    _log(f"=== 完成 push_ok={ok} ===")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
