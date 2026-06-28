#!/usr/bin/env python3
"""FrequencyOS daily sampler.

Runs standalone (no ProjectOS dependency). Reads today's daily_log.md,
computes the Organization Index, prints a one-screen summary.

Usage:
    python frequency_daily.py                 # today
    python frequency_daily.py --date 2026-06-28
    python frequency_daily.py --weekly        # weekly roll-up
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Windows console defaults to GBK; force UTF-8 so CJK + symbols don't crash.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", write_through=True)
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", write_through=True)

ROOT = Path(__file__).resolve().parent.parent
DAILY_LOG = ROOT / "daily_log.md"
ANTI_SWING = ROOT / "anti_swing_inbox.md"
GOALS = ROOT / "goals.md"


def parse_daily_block(text: str, target: str) -> dict | None:
    pattern = re.compile(rf"## {re.escape(target)}.*?(?=\n## |\Z)", re.S)
    m = pattern.search(text)
    if not m:
        return None
    block = m.group(0)
    return {
        "main_freq": _grep(r"今日唯一主频：[ \t]*([^\n]+)", block),
        "main_hours": _grep(r"主频投入时间：[ \t]*([0-9.]+)", block),
        "noise_hours": _grep(r"高频噪音时间：[ \t]*([0-9.]+)", block),
        "morning_mood": _grep(r"晨间情绪评分：[ \t]*(\d+)", block),
        "evening_mood": _grep(r"晚间情绪评分：[ \t]*(\d+)", block),
        "energy": _grep(r"身体能量评分：[ \t]*(\d+)", block),
        "compliance": _grep(r"今日行为是否服从主频目标：[ \t]*([^\n]+)", block),
        "swing_events": _grep(r"目标摇摆事件：[ \t]*([^\n]+)", block),
        "recap": _grep(r"一句话复盘[^\n]*\n+([^\n#][^\n]*)", block),
        "tomorrow": _grep(r"明日主频咒语[^\n]*\n+([^\n#-][^\n]*)", block),
    }


def _grep(pattern: str, text: str) -> str:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else "—"


def count_swing_events(text: str, target_week_start: date) -> dict:
    matches = re.findall(r"### \[(\d{4}-\d{2}-\d{2})", text)
    week_dates = [target_week_start + timedelta(days=i) for i in range(7)]
    week_strs = {d.strftime("%Y-%m-%d") for d in week_dates}
    in_week = [d for d in matches if d in week_strs]
    return {"total": len(in_week)}


def org_index(daily: dict, swings: dict) -> int:
    # Heuristic V0: 4 inputs we usually have, normalized to 0-100.
    # This is intentionally simple — V0.1 just needs a number to trend, not a perfect score.
    score = 0
    weights_seen = 0

    # Main frequency hours (target: 4h/day)
    try:
        h = float(re.sub(r"[^\d.]", "", daily.get("main_hours") or "0"))
    except ValueError:
        h = 0
    s = min(100, int(h / 4 * 100))
    score += s * 0.30
    weights_seen += 0.30

    # Mood stability (smaller evening-morning gap = better)
    try:
        m1 = int(daily.get("morning_mood") or 0)
        m2 = int(daily.get("evening_mood") or 0)
        if m1 and m2:
            gap = abs(m2 - m1)
            s = max(0, 100 - gap * 15)
            score += s * 0.20
            weights_seen += 0.20
    except ValueError:
        pass

    # Swing events (fewer = better, 0 = 100, 3+ = 0)
    s = max(0, 100 - swings.get("total", 0) * 33)
    score += s * 0.25
    weights_seen += 0.25

    # Noise control (< 1h = 100, 4h+ = 0)
    try:
        n = float(re.sub(r"[^\d.]", "", daily.get("noise_hours") or "0"))
        s = max(0, 100 - int(n / 4 * 100))
        score += s * 0.25
        weights_seen += 0.25
    except ValueError:
        pass

    if weights_seen == 0:
        return -1
    return int(score / weights_seen) if weights_seen < 1 else int(score)


def print_summary(daily: dict, swings: dict, idx: int, target: str) -> None:
    line = "-" * 56
    print(line)
    print(f"  FrequencyOS · {target}")
    print(line)
    print(f"  主频        : {daily.get('main_freq', '—')}")
    print(f"  主频投入    : {daily.get('main_hours', '—')} h")
    print(f"  高频噪音    : {daily.get('noise_hours', '—')} h")
    print(f"  情绪(晨/晚) : {daily.get('morning_mood', '—')} / {daily.get('evening_mood', '—')}")
    print(f"  身体能量    : {daily.get('energy', '—')}")
    print(f"  服从主频    : {daily.get('compliance', '—')}")
    print(f"  摇摆事件    : {daily.get('swing_events', '—')} (本周累计 {swings.get('total', 0)})")
    print(line)
    if idx >= 0:
        flag = "[OK]" if idx >= 75 else ("[!!]" if idx >= 60 else "[XX]")
        print(f"  组织度指数  : {flag}  {idx} / 100")
    else:
        print(f"  组织度指数  : -- (data insufficient)")
    print(line)
    recap = daily.get("recap") or "（未填）"
    tomorrow = daily.get("tomorrow") or "（未填）"
    print(f"  今日复盘    : {recap}")
    print(f"  明日咒语    : {tomorrow}")
    print(line)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().strftime("%Y-%m-%d"))
    ap.add_argument("--weekly", action="store_true", help="roll up current week")
    args = ap.parse_args()

    if not DAILY_LOG.exists():
        print(f"[ERR] {DAILY_LOG} not found", file=sys.stderr)
        return 2

    text = DAILY_LOG.read_text(encoding="utf-8")
    daily = parse_daily_block(text, args.date)
    if not daily:
        print(f"[ERR] No daily block for {args.date} in {DAILY_LOG}", file=sys.stderr)
        print("[HINT] Copy templates/daily_sample.md to the top of daily_log.md", file=sys.stderr)
        return 1

    target = datetime.strptime(args.date, "%Y-%m-%d").date()
    week_start = target - timedelta(days=target.weekday())  # Monday
    swings = {"total": 0}
    if ANTI_SWING.exists():
        swings = count_swing_events(ANTI_SWING.read_text(encoding="utf-8"), week_start)

    idx = org_index(daily, swings)
    print_summary(daily, swings, idx, args.date)

    if args.weekly:
        print("\n[weekly roll-up not yet implemented — see weekly_report.md]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
