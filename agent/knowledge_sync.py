#!/usr/bin/env python3
"""项目知识库生成器 (v0.6.2)

从 data/registry.json 为每个项目生成一张知识卡片:
  knowledge/projects/<registry_key>.md   — 每项目一张, 覆盖式更新
  knowledge/index.md                     — 全局索引, 按状态分组

由 hermes-desktop scan_projects_now 在 project_agent.py 跑完后自动调用, 也可独立运行:
  python knowledge_sync.py

卡片 <!-- MANUAL --> 标记线以下的内容不会被自动更新覆盖 (老茅/老赫可手动追加笔记)。
只有内容变化时才写文件, 避免 mtime 抖动干扰活动扫描。
"""
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECTOS_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = PROJECTOS_ROOT / "data" / "registry.json"
KNOWLEDGE_DIR = PROJECTOS_ROOT / "knowledge"
PROJECTS_DIR = KNOWLEDGE_DIR / "projects"
MANUAL_MARKER = "<!-- MANUAL -->"
MAX_TODOS = 5

_STATUS_ORDER = {"活跃": 0, "进行中": 0, "All-in": 0, "卡点": 1, "停滞": 2, "待归档": 3, "已归档": 4}


def _yesno(b: bool) -> str:
    return "✓" if b else "✗"


def render_card(key: str, p: dict, now: str) -> str:
    git = p.get("git") or {}
    activity = p.get("activity") or {}
    tech = p.get("tech") or {}
    docs = p.get("docs") or {}
    last_commit = git.get("last_commit") or {}

    lines = [
        f"# {p.get('name', key)}",
        "",
        f"- registry_key: {key}",
        f"- path: {p.get('path', '')}",
        f"- status: {p.get('status', '')}"
        + (f" (manual: {p['manual_status']})" if p.get("manual_status") else ""),
    ]
    if p.get("mva_decision"):
        lines.append(f"- mva: {p['mva_decision']}" + (f" @ {p['mva_date']}" if p.get("mva_date") else ""))
    stack = tech.get("stack") or []
    if stack:
        lines.append(f"- tech: {', '.join(stack)}")
    scripts = tech.get("scripts") or {}
    if scripts:
        lines.append("- scripts: " + "; ".join(f"{k}={v}" for k, v in scripts.items()))
    needs = tech.get("needs") or []
    if needs:
        lines.append(f"- tech_needs: {', '.join(needs)}")
    if git.get("is_repo"):
        dirty = f"{git.get('uncommitted_count', 0)} uncommitted" if git.get("uncommitted") else "clean"
        lines.append(f"- git: {git.get('branch', '?')}, {dirty}")
        if last_commit:
            lines.append(
                f"- last_commit: {last_commit.get('hash', '')} {last_commit.get('date', '')[:10]} {last_commit.get('message', '')[:80]}"
            )
    if activity:
        lines.append(
            f"- activity: last_code_edit {str(activity.get('last_code_edit') or '')[:10]}"
            f" ({activity.get('days_since_code', '?')}d), files {activity.get('file_count', '?')}"
        )
    lines.append(
        f"- docs: readme{_yesno(docs.get('has_readme', False))} claude_md{_yesno(docs.get('has_claude_md', False))} docs_dir{_yesno(docs.get('has_docs_dir', False))}"
    )

    blockers = p.get("blockers") or []
    if blockers:
        lines += ["", "## blockers"]
        for b in blockers:
            lines.append(f"- [{b.get('severity', '?')}] {b.get('type', '?')}: {b.get('message', '')}")

    todos = (p.get("todos") or [])[:MAX_TODOS]
    if todos:
        lines += ["", "## todos"]
        for t in todos:
            lines.append(f"- {t.get('file', '?')}:{t.get('line', '?')} {t.get('text', '')[:120]}")

    lines += [
        "",
        f"_自动更新: {now}_",
        "",
        MANUAL_MARKER,
    ]
    return "\n".join(lines) + "\n"


def render_index(projects: dict, now: str) -> str:
    def sort_key(item):
        _, p = item
        days = (p.get("activity") or {}).get("days_since_edit")
        return (_STATUS_ORDER.get(p.get("status", ""), 9), days if days is not None else 9999)

    lines = [
        "# 项目知识库索引",
        "",
        f"_共 {len(projects)} 个项目_",
        f"_自动更新: {now}_",
        "",
        "| 项目 | 状态 | MVA | 最近编辑 | 卡片 |",
        "|---|---|---|---|---|",
    ]
    for key, p in sorted(projects.items(), key=sort_key):
        last_edit = str((p.get("activity") or {}).get("last_modified") or "")[:10]
        lines.append(
            f"| {p.get('name', key)} | {p.get('status', '')} | {p.get('mva_decision', '')} | {last_edit} | [卡片](projects/{key}.md) |"
        )
    return "\n".join(lines) + "\n"


def _strip_update_line(text: str) -> str:
    """去掉 _自动更新: ..._ 行, 用于内容比较 (时间戳每次运行都变, 不参与幂等判断)。"""
    return "\n".join(l for l in text.split("\n") if not l.startswith("_自动更新: "))


def _write_if_changed(path: Path, content: str) -> bool:
    if path.exists() and _strip_update_line(path.read_text(encoding="utf-8")) == _strip_update_line(content):
        return False
    path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    if not REGISTRY_PATH.exists():
        print(f"[knowledge] registry 不存在: {REGISTRY_PATH}", file=sys.stderr)
        return 1
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    projects = data.get("projects", {}) if isinstance(data, dict) else {}
    now = datetime.now().isoformat(timespec="seconds")

    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    for key, p in projects.items():
        if not isinstance(p, dict):
            continue
        card = render_card(key, p, now)
        card_path = PROJECTS_DIR / f"{key}.md"
        # 保留 MANUAL 标记线以下的手动笔记
        if card_path.exists():
            old = card_path.read_text(encoding="utf-8")
            if MANUAL_MARKER in old:
                manual_tail = old.split(MANUAL_MARKER, 1)[1]
                card = card + manual_tail.lstrip("\n") if manual_tail.strip() else card
        if _write_if_changed(card_path, card):
            written += 1

    # 清理 registry 里已不存在项目的卡片 (手动笔记区有内容的除外, 防误删)
    removed = 0
    for f in PROJECTS_DIR.glob("*.md"):
        key = f.stem
        if key not in projects:
            old = f.read_text(encoding="utf-8")
            if MANUAL_MARKER in old and old.split(MANUAL_MARKER, 1)[1].strip():
                continue
            f.unlink()
            removed += 1

    _write_if_changed(KNOWLEDGE_DIR / "index.md", render_index(projects, now))
    print(f"[knowledge] {len(projects)} 项目, {written} 卡片更新, {removed} 卡片清理 -> {KNOWLEDGE_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
