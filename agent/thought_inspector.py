#!/usr/bin/env python3
"""
thought_inspector.py - 思考池巡检脚本

每周一 09:07 通过 cron 触发：
  1. 扫 inbox.md 所有未处理思考
  2. 对每条判断：
     - 已 14 天未动 → 建议决断
     - 反复出现 ≥3 次（项目+关键词模糊匹配） → 强信号
     - 项目最近 git 有相关 commit → 已自然落地，建议归档
  3. 输出报告卡片推飞书

数据格式（inbox.md 一行）：
  [2026-06-07T21:30:15] [docreview-ai] 想给审查报告加历史时间轴
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Fix Windows encoding
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

WORKDIR = Path(r"D:\ClaudeCodeProjects\_ProjectOS")
THOUGHTS_DIR = WORKDIR / "thoughts"
INBOX = THOUGHTS_DIR / "inbox.md"
REGISTRY = WORKDIR / "data" / "registry.json"
BASE_DIR = Path(r"D:\ClaudeCodeProjects")

THOUGHT_RE = re.compile(
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\]\s+\[(?P<project>[^\]]+)\]\s+(?P<text>.+?)\s*$"
)
ANCHOR = "<!-- BOT_APPEND_BELOW_THIS_LINE -->"

STALE_DAYS = 14
RECURRENCE_THRESHOLD = 3


def parse_inbox() -> list[dict]:
    """读 inbox.md 返回 [{ts, project, text, raw_line}]。

    只解析 ANCHOR 注释行之后的内容（避开格式说明里的示例）。
    """
    if not INBOX.exists():
        return []
    content = INBOX.read_text(encoding="utf-8")
    if ANCHOR not in content:
        return []
    payload = content.split(ANCHOR, 1)[1]
    rows = []
    for line in payload.splitlines():
        m = THOUGHT_RE.match(line.strip())
        if not m:
            continue
        rows.append({
            "ts": datetime.fromisoformat(m.group("ts")),
            "project": m.group("project").strip(),
            "text": m.group("text").strip(),
            "raw": line,
        })
    return rows


def project_recent_commits(project_path: Path, since_days: int = 14) -> list[str]:
    """返回项目 since_days 内的 commit 消息列表（空目录/非 git 返回空）。"""
    if not (project_path / ".git").exists():
        return []
    try:
        out = subprocess.run(
            ["git", "log", f"--since={since_days}.days.ago", "--pretty=format:%s", "--all"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
            encoding="utf-8",
            errors="replace",
        )
        return [l for l in out.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def extract_keywords(text: str) -> set[str]:
    """提取思考关键词（粗：去停用词后的中文实词 + 英文单词）。"""
    # 简化：去掉标点和常见动词/虚词
    stopwords = {"想", "做", "加", "改", "给", "的", "了", "在", "把", "我", "要", "能", "可以", "应该", "需要", "一个", "这个", "那个", "可能"}
    tokens = re.findall(r"[一-龥]{2,}|[A-Za-z][A-Za-z0-9_-]{2,}", text)
    return {t for t in tokens if t not in stopwords and len(t) >= 2}


def find_recurrence(thoughts: list[dict]) -> dict[tuple[str, frozenset], list[dict]]:
    """按 (project, keyword_set 交集) 聚类，找重复出现的思考。"""
    by_project = defaultdict(list)
    for t in thoughts:
        by_project[t["project"]].append(t)

    recurrence = {}
    for project, items in by_project.items():
        # 简化：同项目内任意两条 keyword 交集 >= 2 视为同主题
        for i, t in enumerate(items):
            kw = extract_keywords(t["text"])
            cluster = [t]
            for j, other in enumerate(items):
                if i == j:
                    continue
                if len(kw & extract_keywords(other["text"])) >= 2:
                    cluster.append(other)
            if len(cluster) >= RECURRENCE_THRESHOLD:
                key = (project, frozenset(kw))
                if key not in recurrence:
                    recurrence[key] = cluster
    return recurrence


def find_landed(thoughts: list[dict], registry: dict) -> list[tuple[dict, str]]:
    """找 git commit 中能匹配思考关键词的（已自然落地）。返回 [(thought, commit_msg)]。"""
    landed = []
    for t in thoughts:
        project_meta = registry.get("projects", {}).get(t["project"])
        if not project_meta:
            continue
        path = Path(project_meta["path"])
        if not path.exists():
            continue
        commits = project_recent_commits(path, since_days=(datetime.now() - t["ts"]).days + 1)
        kw = extract_keywords(t["text"])
        for c in commits:
            commit_kw = extract_keywords(c)
            if len(kw & commit_kw) >= 1:
                landed.append((t, c))
                break
    return landed


def find_stale(thoughts: list[dict]) -> list[dict]:
    """找超过 STALE_DAYS 天未决断的。"""
    cutoff = datetime.now() - timedelta(days=STALE_DAYS)
    return [t for t in thoughts if t["ts"] < cutoff]


def build_report(thoughts: list[dict], registry: dict) -> dict:
    """生成巡检报告 dict（给卡片用）。"""
    stale = find_stale(thoughts)
    recurrence = find_recurrence(thoughts)
    landed = find_landed(thoughts, registry)

    return {
        "total": len(thoughts),
        "stale": stale,
        "recurrence": recurrence,
        "landed": landed,
        "scan_time": datetime.now().isoformat(timespec="seconds"),
    }


def render_text_report(report: dict) -> str:
    """渲染纯文本报告（备用：卡片失败时降级）。"""
    lines = [
        f"🧠 思考池巡检（{report['scan_time']}）",
        f"共 {report['total']} 条思考",
        "",
    ]

    if report["stale"]:
        lines.append(f"📌 已 {STALE_DAYS} 天未动（{len(report['stale'])} 条） — 建议决断：")
        for i, t in enumerate(report["stale"][:10], 1):
            days = (datetime.now() - t["ts"]).days
            lines.append(f"  {i}. [{t['project']}] {t['text']} （{days}天）")
        lines.append("")

    if report["recurrence"]:
        lines.append(f"🔥 反复出现 ≥{RECURRENCE_THRESHOLD} 次（强信号）：")
        for (project, _), cluster in list(report["recurrence"].items())[:5]:
            lines.append(f"  • [{project}] 出现 {len(cluster)} 次：{cluster[0]['text']}")
        lines.append("")

    if report["landed"]:
        lines.append(f"✅ 已自然落地（git 见相关 commit，{len(report['landed'])} 条）：")
        for t, commit in report["landed"][:10]:
            lines.append(f"  • [{t['project']}] {t['text']}")
            lines.append(f"    → commit: {commit[:60]}")
        lines.append("")

    if not (report["stale"] or report["recurrence"] or report["landed"]):
        lines.append("✨ 所有思考都在新鲜期，无需决断。")

    lines.append("")
    lines.append("回我「1 Go, 2 Kill, 3 Watch」式决断，我自动归档到 active/killed/watching.md")
    return "\n".join(lines)


def push_to_feishu(text: str) -> bool:
    """走 feishu_sync 推到飞书。"""
    sys.path.insert(0, str(WORKDIR / "agent"))
    try:
        from feishu_sync import FeishuClient
        client = FeishuClient()
        open_id = "ou_59a5d4b0cc115a66295961a1aec66a9e"
        # 用 rich_message（post 类型，稳定）
        result = client.send_rich_message(
            target=open_id,
            title="🧠 思考池周巡检",
            content=text,
            target_type="user_id",
        )
        return bool(result.get("data"))
    except Exception as e:
        print(f"[ERROR] 推飞书失败: {e}", file=sys.stderr)
        return False


def main():
    if not INBOX.exists():
        print(f"[SKIP] inbox 不存在: {INBOX}")
        return

    thoughts = parse_inbox()
    if not thoughts:
        print("[SKIP] inbox 为空，无需巡检")
        return

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    report = build_report(thoughts, registry)
    text = render_text_report(report)
    print(text)
    print()

    if "--dry-run" in sys.argv:
        print("[DRY-RUN] 跳过推送")
        return

    ok = push_to_feishu(text)
    print(f"[推送] {'成功' if ok else '失败'}")


if __name__ == "__main__":
    main()
