"""ProjectOS → 工作室站公开数据导出

只导出对外可见字段（约定见用户决断 2026-06-14）：
  - name           项目名
  - description    项目简介（从 README 首段抽，或留空）
  - stage          阶段（registry.status / 自定义 stage）
  - freq_total     三频共振总分
  - freq_suggestion All-in / Watch / Kill
  - last_action    最近一次 commit message + 日期
  - github_url     GitHub 仓库链接（如开源）
  - cover_image    公开产品图 URL / 站点内绝对路径（可选，手动维护）
  - tech_stack     技术栈标签

写入 data/public-registry.json（入 git 公开），voidarchitect-site 构建期 fetch 此文件。

设计原则：
  - 严禁导出 path / blockers / todos / activity 细节
  - github_url 通过 git remote 解析，仅公开域名 = github.com 的（不暴露内网/SSH）
  - description 用 _ProjectOS/data/public-bios.json 手动维护（可选），未配置则留空
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "registry.json"
PUBLIC_BIOS = ROOT / "data" / "public-bios.json"
OUT = ROOT / "data" / "public-registry.json"

# 黑名单：这些项目不对外公开（隐私 / 客户敏感 / 已废弃）
HIDDEN = {
    "_ProjectOS",
    "ProjectOS-Projects",
    "Private-Wealth-AI-Steward",
    "TexasPhilosopher",
    "obsidian manager",
}


def get_github_url(project_path: str) -> str | None:
    p = Path(project_path)
    if not (p / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(p), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        url = result.stdout.strip()
        if not url:
            return None
        m = re.match(r"git@github\.com:([^/]+)/(.+?)(?:\.git)?$", url)
        if m:
            return f"https://github.com/{m.group(1)}/{m.group(2)}"
        m = re.match(r"https://github\.com/([^/]+)/(.+?)(?:\.git)?/?$", url)
        if m:
            return f"https://github.com/{m.group(1)}/{m.group(2)}"
        return None
    except Exception:
        return None


def derive_stage(info: dict) -> str:
    suggestion = info.get("freq_suggestion")
    if suggestion in ("All-in", "Watch", "Kill"):
        return suggestion
    status = info.get("status")
    return status or "in-progress"


def export() -> dict:
    if not REGISTRY.exists():
        raise SystemExit(f"registry not found: {REGISTRY}")
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    bios = {}
    if PUBLIC_BIOS.exists():
        bios = json.loads(PUBLIC_BIOS.read_text(encoding="utf-8"))

    projects = []
    for name, info in (reg.get("projects") or {}).items():
        if name in HIDDEN:
            continue

        commit = (info.get("git") or {}).get("last_commit") or {}
        last_action = None
        if commit.get("message"):
            last_action = {
                "message": commit["message"][:120],
                "date": commit.get("date", "")[:10],
            }

        item = {
            "name": name,
            "description": bios.get(name, {}).get("description", ""),
            "stage": derive_stage(info),
            "freq_total": info.get("freq_total"),
            "freq_suggestion": info.get("freq_suggestion"),
            "last_action": last_action,
            "github_url": get_github_url(info.get("path", "")),
            "cover_image": bios.get(name, {}).get("cover_image"),
            "tech_stack": (info.get("tech") or {}).get("stack", [])[:6],
        }
        projects.append(item)

    # 排序：有三频分的优先（高分先）→ 无分按名字
    projects.sort(
        key=lambda x: (
            -1 if x["freq_total"] is None else -x["freq_total"],
            x["name"],
        )
    )

    output = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(projects),
        "projects": projects,
    }
    return output


def main() -> None:
    output = export()
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {OUT}")
    print(f"[OK] count: {output['count']}")
    for p in output["projects"][:5]:
        scored = f"{p['freq_total']}/15 {p['freq_suggestion']}" if p['freq_total'] else "未评分"
        print(f"  - {p['name']:30s} | {p['stage']:12s} | {scored}")


if __name__ == "__main__":
    main()
