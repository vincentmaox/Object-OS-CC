#!/usr/bin/env python3
"""
ProjectOS Agent - 项目探路先遣队
扫描、分析、追踪、归档 D:\\ClaudeCodeProjects 下所有项目

执行纪律：
- 24小时A→D闭环：任何新信息24小时内完成转化
- 72小时MVA：Day1理论→Day2市场→Day3组织，72小时后All-in/Watch/Kill
"""

import os
import sys
import io

# Fix Windows GBK encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import json
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import urllib.request
import urllib.error

BASE_DIR = Path("D:/ClaudeCodeProjects")
OS_DIR = BASE_DIR / "_ProjectOS"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_env_file(OS_DIR / "agent" / "project_os.env")

DATA_DIR = OS_DIR / "data"
REGISTRY_FILE = DATA_DIR / "registry.json"
STATE_FILE = DATA_DIR / "state.json"
ARCHIVE_DIR = OS_DIR / "archive"
INBOX_DIR = OS_DIR / "_inbox"
TEMPLATES_DIR = OS_DIR / "templates"

OBSIDIAN_API_KEY = os.environ.get("OBSIDIAN_API_KEY", "")
OBSIDIAN_PORT = int(os.environ.get("OBSIDIAN_PORT", "27123"))  # insecure HTTP


class ObsidianClient:
    """Obsidian REST API 客户端 —— 使魔接口"""

    def __init__(self, api_key: str, port: int = 27123):
        self.api_key = api_key
        self.base_url = f"http://127.0.0.1:{port}"

    def request(self, method: str, path: str, data: bytes = None, headers: dict = None):
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, method=method, data=data)
        req.add_header("Authorization", f"Bearer {self.api_key}")
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            print(f"  [WARN] Obsidian API {e.code} {e.reason} on {path}")
            return None
        except Exception as e:
            print(f"  [WARN] Obsidian connection failed: {e}")
            return None

    def write_file(self, path: str, content: str):
        encoded = content.encode("utf-8")
        headers = {"Content-Type": "text/markdown"}
        return self.request("PUT", f"/vault/{path}", encoded, headers)

    def read_file(self, path: str):
        return self.request("GET", f"/vault/{path}")


class ProjectScanner:
    """项目探路扫描器"""

    EXCLUDE_DIRS = {
        ".obsidian",
        ".claude",
        "_ProjectOS",
        "node_modules",
        ".git",
        ".next",
        ".clerk",
        ".playwright-mcp",
        "__pycache__",
        ".venv",
        "dist",
        "build",
        "out",
    }

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def scan(self) -> List[Dict]:
        projects = []
        for item in self.base_dir.iterdir():
            if not item.is_dir():
                continue
            name = item.name
            if name.startswith(".") or name.startswith("_") or name.startswith("ProjectOS-"):
                continue
            if name in self.EXCLUDE_DIRS:
                continue

            project = self.analyze_project(item)
            projects.append(project)
        return projects

    def analyze_project(self, path: Path) -> Dict:
        name = path.name
        git_info = self._analyze_git(path)
        doc_info = self._analyze_docs(path)
        activity = self._analyze_activity(path)
        tech = self._analyze_tech(path)
        blockers = self._find_blockers(path, git_info, doc_info, activity, tech)
        todos = self._extract_todos(path)

        status = self._determine_status(git_info, activity, blockers)

        return {
            "name": name,
            "path": str(path),
            "status": status,
            "git": git_info,
            "docs": doc_info,
            "activity": activity,
            "tech": tech,
            "blockers": blockers,
            "todos": todos,
            "last_scan": datetime.now().isoformat(),
        }

    def _analyze_git(self, path: Path) -> Dict:
        result = {
            "is_repo": False,
            "branch": None,
            "uncommitted": False,
            "uncommitted_count": 0,
            "unpushed": 0,
            "last_commit": None,
            "commits_ahead_behind": None,
        }
        git_dir = path / ".git"
        if not git_dir.exists():
            return result

        result["is_repo"] = True

        try:
            branch = subprocess.run(
                ["git", "-C", str(path), "branch", "--show-current"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            if branch.returncode == 0:
                result["branch"] = branch.stdout.strip()

            status = subprocess.run(
                ["git", "-C", str(path), "status", "--short"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            lines = [l for l in status.stdout.strip().split("\n") if l.strip()]
            result["uncommitted"] = len(lines) > 0
            result["uncommitted_count"] = len(lines)

            log = subprocess.run(
                ["git", "-C", str(path), "log", "-1", "--format=%H|%ci|%s"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            if log.returncode == 0 and log.stdout.strip():
                parts = log.stdout.strip().split("|", 2)
                result["last_commit"] = {
                    "hash": parts[0][:8],
                    "date": parts[1],
                    "message": parts[2] if len(parts) > 2 else "",
                }

            if result["branch"]:
                ahead = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(path),
                        "rev-list",
                        "--count",
                        f"origin/{result['branch']}..{result['branch']}",
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=5,
                )
                if ahead.returncode == 0:
                    try:
                        result["unpushed"] = int(ahead.stdout.strip())
                    except ValueError:
                        pass

                # Check if branch is behind remote
                behind = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(path),
                        "rev-list",
                        "--count",
                        f"{result['branch']}..origin/{result['branch']}",
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=5,
                )
                if behind.returncode == 0:
                    try:
                        behind_count = int(behind.stdout.strip())
                        if behind_count > 0:
                            result["commits_ahead_behind"] = f"behind {behind_count}"
                    except ValueError:
                        pass
        except Exception as e:
            print(f"  [WARN] Git analysis error for {path}: {e}")

        return result

    def _analyze_docs(self, path: Path) -> Dict:
        docs = {
            "has_readme": (path / "README.md").exists(),
            "has_claude_md": (path / "CLAUDE.md").exists(),
            "has_docs_dir": (path / "docs").exists(),
            "has_deployment_plan": False,
            "missing_critical": [],
        }

        # Check for deployment plan inside docs/
        if docs["has_docs_dir"]:
            dp = path / "docs" / "deployment-plan.md"
            docs["has_deployment_plan"] = dp.exists()

        if not docs["has_readme"]:
            docs["missing_critical"].append("README.md")
        if not docs["has_claude_md"]:
            docs["missing_critical"].append("CLAUDE.md")

        return docs

    def _analyze_activity(self, path: Path) -> Dict:
        newest = None
        code_newest = None
        file_count = 0

        for root, dirs, files in os.walk(path):
            dirs[:] = [
                d
                for d in dirs
                if d not in self.EXCLUDE_DIRS and not d.startswith(".")
            ]
            for f in files:
                if f.endswith((".tmp", ".log", ".db", ".sqlite", ".tsbuildinfo")):
                    continue
                fp = Path(root) / f
                try:
                    mtime = fp.stat().st_mtime
                    file_count += 1
                    if newest is None or mtime > newest:
                        newest = mtime
                    # Code files only for "real work" metric
                    if f.endswith((".ts", ".tsx", ".js", ".jsx", ".py", ".css", ".html", ".prisma")):
                        if code_newest is None or mtime > code_newest:
                            code_newest = mtime
                except (OSError, PermissionError):
                    pass

        now = datetime.now().timestamp()
        days_since_edit = (now - newest) / 86400 if newest else None
        days_since_code = (now - code_newest) / 86400 if code_newest else None

        return {
            "last_modified": datetime.fromtimestamp(newest).isoformat() if newest else None,
            "last_code_edit": datetime.fromtimestamp(code_newest).isoformat() if code_newest else None,
            "days_since_edit": round(days_since_edit, 1) if days_since_edit else None,
            "days_since_code": round(days_since_code, 1) if days_since_code else None,
            "stale": days_since_edit > 7 if days_since_edit else False,
            "code_stale": days_since_code > 7 if days_since_code else False,
            "file_count": file_count,
        }

    def _analyze_tech(self, path: Path) -> Dict:
        tech = {"stack": [], "deploy_ready": False, "needs": [], "scripts": {}}

        pkg_file = path / "package.json"
        if pkg_file.exists():
            tech["stack"].append("Node.js")
            try:
                with open(pkg_file, encoding="utf-8") as f:
                    pkg = json.load(f)
                    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                    if "next" in deps:
                        tech["stack"].append("Next.js")
                    if "react" in deps:
                        tech["stack"].append("React")
                    if "prisma" in deps:
                        tech["stack"].append("Prisma")
                    if "tailwindcss" in deps:
                        tech["stack"].append("Tailwind")
                    if "@clerk" in str(deps):
                        tech["stack"].append("Clerk")
                    tech["scripts"] = pkg.get("scripts", {})
            except Exception:
                pass

            nm = path / "node_modules"
            if not nm.exists():
                tech["needs"].append("npm install（缺少node_modules）")

        if (path / "requirements.txt").exists() or (path / "pyproject.toml").exists():
            tech["stack"].append("Python")

        if (path / "Dockerfile").exists():
            tech["stack"].append("Docker")
            tech["deploy_ready"] = True
        if (path / "vercel.json").exists() or (path / "next.config.ts").exists() or (path / "next.config.js").exists():
            tech["deploy_ready"] = True

        env_example = path / ".env.example"
        env_file = path / ".env"
        if env_example.exists() and not env_file.exists():
            tech["needs"].append("配置.env文件（有.example模板）")

        if not tech["deploy_ready"] and tech["stack"]:
            tech["needs"].append("部署配置缺失")

        return tech

    def _extract_todos(self, path: Path) -> List[Dict]:
        """从CLAUDE.md和README.md中提取TODO项"""
        todos = []
        for filename in ["CLAUDE.md", "README.md"]:
            fp = path / filename
            if not fp.exists():
                continue
            try:
                with open(fp, encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        line_stripped = line.strip()
                        if "TODO" in line_stripped.upper() or "FIXME" in line_stripped.upper():
                            todos.append({
                                "file": filename,
                                "line": i,
                                "text": line_stripped,
                            })
                        # Check markdown checkboxes
                        if line_stripped.startswith("- [ ]"):
                            todos.append({
                                "file": filename,
                                "line": i,
                                "text": line_stripped,
                            })
            except Exception:
                pass
        return todos

    def _find_blockers(self, path, git, docs, activity, tech) -> List[Dict]:
        blockers = []

        if git["uncommitted"]:
            severity = "high" if activity.get("days_since_edit", 0) > 1 else "medium"
            blockers.append({
                "type": "git_dirty",
                "severity": severity,
                "message": f"有 {git['uncommitted_count']} 个未提交更改（分支: {git['branch']}）",
            })

        if git["unpushed"] > 0:
            blockers.append({
                "type": "git_unpushed",
                "severity": "medium",
                "message": f"有 {git['unpushed']} 个提交未推送",
            })

        if git.get("commits_ahead_behind"):
            blockers.append({
                "type": "git_behind",
                "severity": "medium",
                "message": f"本地分支落后远程: {git['commits_ahead_behind']}",
            })

        for missing in docs["missing_critical"]:
            blockers.append({
                "type": "missing_doc",
                "severity": "medium",
                "message": f"缺少 {missing}",
            })

        for need in tech["needs"]:
            sev = "high" if "env" in need.lower() else "low"
            blockers.append({
                "type": "tech_need",
                "severity": sev,
                "message": need,
            })

        if activity.get("stale") and not git["uncommitted"]:
            blockers.append({
                "type": "stale",
                "severity": "low",
                "message": f"项目已停滞 {activity['days_since_edit']:.0f} 天",
            })

        return blockers

    def _determine_status(self, git, activity, blockers) -> str:
        high_blockers = [b for b in blockers if b["severity"] == "high"]
        if high_blockers:
            return "卡点"

        if activity.get("stale"):
            return "停滞"

        if git["uncommitted"]:
            return "进行中"

        return "活跃"


class RegistryManager:
    def __init__(self, registry_file: Path):
        self.registry_file = registry_file
        self.data = self._load()

    def _load(self) -> Dict:
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"  [WARN] Registry corrupted, creating new one")
                return {"projects": {}, "version": 2, "last_update": None}
        return {"projects": {}, "version": 2, "last_update": None}

    def save(self):
        self.data["last_update"] = datetime.now().isoformat()
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def update_project(self, project: Dict):
        name = project["name"]
        old = self.data["projects"].get(name, {})
        project["first_seen"] = old.get("first_seen", datetime.now().isoformat())

        # Preserve manual fields
        for key in [
            "priority",
            "deadline",
            "owner",
            "notes",
            "manual_status",
            "resources_needed",
            "mva_decision",
            "mva_date",
        ]:
            if key in old:
                project[key] = old[key]

        # manual_status overrides auto-detected status
        if old.get("manual_status"):
            project["status"] = old["manual_status"]

        self.data["projects"][name] = project

    def get_project(self, name: str) -> Optional[Dict]:
        return self.data["projects"].get(name)

    def list_projects(self) -> List[Dict]:
        return list(self.data["projects"].values())

    def set_manual_field(self, name: str, key: str, value):
        if name in self.data["projects"]:
            self.data["projects"][name][key] = value
            self.save()

    def remove_project(self, name: str):
        if name in self.data["projects"]:
            del self.data["projects"][name]
            self.save()


class DashboardGenerator:
    def __init__(self, registry: RegistryManager):
        self.registry = registry

    def generate_dashboard(self) -> str:
        projects = self.registry.list_projects()
        active_projects = [p for p in projects if p.get("status") != "已归档"]

        lines = [
            "# ProjectOS 项目看板",
            "",
            f"> 最后更新：`{datetime.now().strftime('%Y-%m-%d %H:%M')}` | 探路先遣队自动扫描",
            "> 编辑项目元数据：直接修改 `_ProjectOS/data/registry.json` 中对应项目字段",
            "",
            "## 项目状态总览",
            "",
            "| 项目 | 状态 | 技术栈 | 卡点 | 最后活动 | 优先级 |",
            "|------|------|--------|------|----------|--------|"
        ]

        for p in sorted(projects, key=lambda x: self._status_priority(x["status"])):
            status_emoji = {
                "活跃": "[OK]",
                "进行中": "[WIP]",
                "卡点": "[!]",
                "停滞": "[STALE]",
                "待归档": "[ARCH]",
                "已归档": "[DONE]",
            }.get(p["status"], "[?]")

            stack = ", ".join(p["tech"]["stack"][:2]) if p["tech"]["stack"] else "-"
            blockers = len(p["blockers"])
            last_act = p["activity"].get("days_since_edit")
            last_str = f"{last_act:.0f}天前" if last_act else "未知"
            priority = p.get("priority", "P2")

            lines.append(
                f"| {status_emoji} {p['name']} | {p['status']} | {stack} | {blockers} | {last_str} | {priority} |"
            )

        lines.extend(["", "## 紧急卡点", ""])

        urgent = []
        for p in active_projects:
            for b in p["blockers"]:
                if b["severity"] in ("high", "medium"):
                    urgent.append((p["name"], b))

        if urgent:
            for name, b in urgent:
                emoji = "[HIGH]" if b["severity"] == "high" else "[MED]"
                lines.append(f"- {emoji} **{name}**：{b['message']}")
        else:
            lines.append("> 当前无紧急卡点，全体探路者正常推进。"
            )

        lines.extend(["", "## 资源需求清单", ""])

        needs = []
        for p in active_projects:
            for n in p["tech"].get("needs", []):
                needs.append((p["name"], n))
            if "resources_needed" in p:
                for r in p["resources_needed"]:
                    needs.append((p["name"], r))

        if needs:
            for name, need in needs:
                lines.append(f"- [ ] **{name}**：{need}")
        else:
            lines.append("> 当前无明确资源缺口。")

        lines.extend(["", "## 待办项追踪", ""])
        has_todos = False
        for p in active_projects:
            if p["todos"]:
                has_todos = True
                lines.append(f"### {p['name']}")
                for todo in p["todos"][:5]:  # Max 5 per project
                    lines.append(f"- [ ] {todo['file']}:{todo['line']} — {todo['text']}")
                if len(p["todos"]) > 5:
                    lines.append(f"- ... 还有 {len(p['todos']) - 5} 项")
                lines.append("")
        if not has_todos:
            lines.append("> 当前无提取到待办项。")

        lines.extend(["", "## 行动建议", ""])
        advice = self._generate_advice(active_projects)
        for a in advice:
            lines.append(f"- {a}")

        lines.extend(
            [
                "",
                "---",
                "*由 ProjectOS Agent 自动生成。手动编辑请在 `_ProjectOS/data/registry.json` 中更新项目元数据。*",
            ]
        )

        return "\n".join(lines)

    def generate_daily_report(self) -> str:
        projects = [p for p in self.registry.list_projects() if p.get("status") != "已归档"]
        now = datetime.now()

        lines = [
            f"# ProjectOS 晨间日报 — {now.strftime('%Y年%m月%d日')}",
            "",
            "## 今日优先处理",
            "",
        ]

        todo = []
        for p in projects:
            for b in p["blockers"]:
                if b["severity"] == "high":
                    todo.append(
                        f"[!] **{p['name']}**：{b['message']} — 立即处理"
                    )
                elif b["severity"] == "medium" and (p["activity"].get("days_since_edit") or 0) < 3:
                    todo.append(
                        f"[MED] **{p['name']}**：{b['message']} — 建议今日处理"
                    )

        active = [
            p
            for p in projects
            if p["status"] in ("活跃", "进行中")
            and not any(b["severity"] == "high" for b in p["blockers"])
        ]
        for p in active[:3]:
            days = p["activity"].get("days_since_edit")
            days_str = f"{days:.0f}天前" if days else "?"
            todo.append(
                f"[OK] **{p['name']}**：持续推进，上次活动 {days_str}"
            )

        stale = [p for p in projects if p["status"] == "停滞"]
        for p in stale[:2]:
            days = p["activity"].get("days_since_edit", 0)
            todo.append(
                f"[STALE] **{p['name']}**：已停滞 {days:.0f} 天，评估All-in/Watch/Kill"
            )

        if todo:
            for i, item in enumerate(todo, 1):
                lines.append(f"{i}. {item}")
        else:
            lines.append("> 今日无紧急事项。建议：review现有项目，或启动新探路任务。"
            )

        lines.extend(["", "## 项目健康度", ""])
        status_counts = {}
        for p in projects:
            status_counts[p["status"]] = status_counts.get(p["status"], 0) + 1

        for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- {status}：{count} 个项目")

        lines.extend(["", "## 72小时MVA决策提醒", ""])
        mva_items = []
        for p in projects:
            first_seen = p.get("first_seen")
            if first_seen:
                try:
                    fs = datetime.fromisoformat(first_seen)
                    days_alive = (now - fs).days
                    if days_alive >= 3 and p["status"] not in ("已归档", "待归档"):
                        decision = p.get("mva_decision", "未决策")
                        mva_items.append(
                            (p["name"], days_alive, decision)
                        )
                except ValueError:
                    pass

        if mva_items:
            for name, days, decision in sorted(mva_items, key=lambda x: -x[1]):
                emoji = "[DUE]" if decision == "未决策" else "[DONE]"
                lines.append(
                    f"- {emoji} **{name}** 已运行 {days} 天，MVA状态：{decision}"
                )
        else:
            lines.append("> 无项目达到72小时MVA决策点。"
            )

        lines.extend(["", "## 昨日变化", ""])
        lines.append("> 对比昨日扫描结果的变化将在此处显示（需启用状态历史追踪）。"
        )

        lines.extend(
            [
                "",
                "---",
                "*晨间日报由 ProjectOS Agent 每日 9:07 自动生成。执行纪律：24小时A→D闭环，72小时MVA决策。*",
            ]
        )

        return "\n".join(lines)

    def _status_priority(self, status: str) -> int:
        return {
            "卡点": 0,
            "进行中": 1,
            "活跃": 2,
            "停滞": 3,
            "待归档": 4,
            "已归档": 5,
        }.get(status, 99)

    def _generate_advice(self, projects) -> List[str]:
        advice = []

        dirty_projects = [p for p in projects if p["git"].get("uncommitted")]
        if dirty_projects:
            names = ", ".join(p["name"] for p in dirty_projects)
            advice.append(f"立即提交：{names} 有未保存更改")

        stale_projects = [p for p in projects if p["status"] == "停滞"]
        if stale_projects:
            names = ", ".join(p["name"] for p in stale_projects)
            advice.append(f"评估去留：{names} 已超过7天无活动，需All-in/Watch/Kill决策")

        no_docs = [p for p in projects if not p["docs"].get("has_claude_md")]
        if no_docs:
            names = ", ".join(p["name"] for p in no_docs)
            advice.append(f"补充文档：{names} 缺少 CLAUDE.md")

        no_env = [p for p in projects if any("env" in n.lower() for n in p["tech"].get("needs", []))]
        if no_env:
            names = ", ".join(p["name"] for p in no_env)
            advice.append(f"配置环境：{names} 需要.env文件")

        if not advice:
            advice.append(
                "当前所有项目状态健康，建议推进高优先级任务或启动新探路。"
            )

        return advice


class ArchiveManager:
    def __init__(self, archive_dir: Path, registry: RegistryManager):
        self.archive_dir = archive_dir
        self.registry = registry

    def archive_project(self, project_name: str) -> bool:
        project = self.registry.get_project(project_name)
        if not project:
            print(f"  项目 {project_name} 不存在")
            return False

        src = Path(project["path"])
        if not src.exists():
            print(f"  源目录不存在：{src}")
            return False

        timestamp = datetime.now().strftime("%Y%m%d")
        dst = self.archive_dir / f"{project_name}-{timestamp}"

        # Create archive metadata
        archive_meta = {
            "name": project_name,
            "archived_at": datetime.now().isoformat(),
            "original_path": str(src),
            "final_status": project["status"],
            "blockers_at_archive": project["blockers"],
            "tech_stack": project["tech"]["stack"],
        }

        try:
            shutil.move(str(src), str(dst))
            # Write archive metadata
            with open(dst / "_archive-meta.json", "w", encoding="utf-8") as f:
                json.dump(archive_meta, f, ensure_ascii=False, indent=2)

            # Update registry
            self.registry.set_manual_field(project_name, "status", "已归档")
            self.registry.set_manual_field(project_name, "manual_status", "已归档")
            self.registry.set_manual_field(project_name, "blockers", [])
            self.registry.set_manual_field(project_name, "tech", {**project.get("tech", {}), "needs": []})
            self.registry.set_manual_field(project_name, "archived_at", archive_meta["archived_at"])
            self.registry.set_manual_field(project_name, "archive_path", str(dst))

            print(f"  [OK] 项目 {project_name} 已归档到 {dst}")
            return True
        except Exception as e:
            print(f"  [ERR] 归档失败：{e}")
            return False

    def generate_archive_index(self) -> str:
        lines = [
            "# ProjectOS 归档索引",
            "",
            f"> 最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "| 项目 | 归档日期 | 最终状态 | 技术栈 |",
            "|------|----------|----------|--------|"
        ]

        archived = []
        for p in self.registry.list_projects():
            if p.get("status") == "已归档":
                archived.append(p)

        for p in sorted(archived, key=lambda x: x.get("archived_at", ""), reverse=True):
            stack = ", ".join(p["tech"]["stack"][:2]) if p["tech"]["stack"] else "-"
            date = p.get("archived_at", "未知")[:10]
            lines.append(f"| {p['name']} | {date} | {p['status']} | {stack} |")

        if not archived:
            lines.append("| - | - | - | - |")

        return "\n".join(lines)


class FileOrganizer:
    """文件秩序维护者"""

    def __init__(self, base_dir: Path, os_dir: Path):
        self.base_dir = base_dir
        self.os_dir = os_dir
        self.inbox = os_dir / "_inbox"

    def organize(self):
        """整理根目录散落文件"""
        print("\n[文件秩序维护]")
        moved = 0
        for item in self.base_dir.iterdir():
            if not item.is_file():
                continue
            if item.suffix != ".md":
                continue
            if item.name.startswith("ProjectOS-"):
                continue

            # These are loose project notes, move to inbox with timestamp prefix
            dest = self.inbox / item.name
            if dest.exists():
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest = self.inbox / f"{ts}_{item.name}"

            try:
                shutil.move(str(item), str(dest))
                print(f"  [MOVE] 归类散落文件：{item.name} -> _inbox/")
                moved += 1
            except Exception as e:
                print(f"  [ERR] 移动失败 {item.name}: {e}")

        if moved == 0:
            print("  [OK] 根目录无散落md文件需归类")
        else:
            print(f"  [OK] 共归类 {moved} 个文件到 _inbox/")

        # Clean old temp files
        temp_patterns = ["*.tmp", "*.log", "*.base"]
        for pattern in temp_patterns:
            for fp in self.base_dir.glob(pattern):
                try:
                    fp.unlink()
                    print(f"  [CLEAN] 清理临时文件：{fp.name}")
                except Exception:
                    pass


class ProjectAgent:
    """ProjectOS 核心使魔"""

    def __init__(self):
        self.base_dir = BASE_DIR
        self.os_dir = OS_DIR
        self.data_dir = DATA_DIR
        self.archive_dir = ARCHIVE_DIR

        self.scanner = ProjectScanner(self.base_dir)
        self.registry = RegistryManager(REGISTRY_FILE)
        self.dashboard = DashboardGenerator(self.registry)
        self.archive_mgr = ArchiveManager(self.archive_dir, self.registry)
        self.organizer = FileOrganizer(self.base_dir, self.os_dir)
        self.obsidian = ObsidianClient(OBSIDIAN_API_KEY, OBSIDIAN_PORT)

        self._ensure_dirs()

    def _ensure_dirs(self):
        for d in [
            self.os_dir,
            self.data_dir,
            self.archive_dir,
            INBOX_DIR,
            TEMPLATES_DIR,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    def run(self):
        print("=" * 60)
        print("ProjectOS Agent 启动")
        print(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # 1. Scan
        print("\n[1/6] 扫描项目...")
        projects = self.scanner.scan()
        print(f"  发现 {len(projects)} 个项目")

        # 2. Update registry
        print("\n[2/6] 更新注册表...")
        for system_name in ["ProjectOS-Projects"]:
            if self.registry.get_project(system_name):
                self.registry.remove_project(system_name)
                print(f"  [OK] 移除系统目录记录：{system_name}")
        for p in projects:
            self.registry.update_project(p)
            sev_counts = {"high": 0, "medium": 0, "low": 0}
            for b in p["blockers"]:
                sev_counts[b["severity"]] = sev_counts.get(b["severity"], 0) + 1
            sev_str = " ".join([f"{k[0].upper()}{v}" for k, v in sev_counts.items() if v > 0])
            print(f"  [OK] {p['name']:20s} -> {p['status']:6s} ({sev_str})")
        self.registry.save()

        # 3. Generate dashboard
        print("\n[3/6] 生成看板...")
        dashboard_md = self.dashboard.generate_dashboard()
        self._write_to_vault("ProjectOS-Dashboard.md", dashboard_md)

        # 4. Generate daily report
        print("\n[4/6] 生成日报...")
        report_md = self.dashboard.generate_daily_report()
        self._write_to_vault("ProjectOS-DailyReport.md", report_md)

        # 5. Archive index
        print("\n[5/6] 更新归档索引...")
        archive_index = self.archive_mgr.generate_archive_index()
        self._write_to_vault("ProjectOS-ArchiveIndex.md", archive_index)

        # 5b. Per-project frontmatter notes (for Dataview)
        print("\n[5b/6] 生成项目frontmatter笔记...")
        self._write_project_notes(projects)

        # 6. File management
        print("\n[6/6] 文件秩序维护...")
        self.organizer.organize()

        print("\n" + "=" * 60)
        print("ProjectOS Agent 执行完毕")
        print("=" * 60)

        return {
            "projects_scanned": len(projects),
            "registry_updated": True,
            "dashboard_generated": True,
        }

    def _write_to_vault(self, filename: str, content: str):
        # Try Obsidian REST API first
        result = self.obsidian.write_file(filename, content)
        if result is not None:
            print(f"  [OK] Obsidian API: {filename}")
        else:
            # Fallback to filesystem
            path = self.base_dir / filename
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  [OK] Filesystem: {filename}")

    def _write_project_notes(self, projects):
        """为每个项目生成带frontmatter的笔记，供Dataview查询"""
        notes_dir = self.base_dir / "ProjectOS-Projects"
        notes_dir.mkdir(exist_ok=True)
        for p in projects:
            high_blockers = [b for b in p["blockers"] if b["severity"] == "high"]
            med_blockers = [b for b in p["blockers"] if b["severity"] == "medium"]
            first_seen = p.get("first_seen", "")
            try:
                fs = datetime.fromisoformat(first_seen)
                days_alive = (datetime.now() - fs).days
            except (ValueError, TypeError):
                days_alive = 0

            # Build frontmatter
            stack_str = ", ".join(p["tech"]["stack"][:3]) if p["tech"]["stack"] else "-"
            blocker_msgs = [b["message"] for b in p["blockers"]]
            high_blocker_msgs = [b["message"] for b in high_blockers]

            frontmatter = [
                "---",
                f"project: {p['name']}",
                f"status: {p['status']}",
                f"priority: {p.get('priority', 'P2')}",
                f"stack: \"{stack_str}\"",
                f"blockers: {len(p['blockers'])}",
                f"highBlockerCount: {len(high_blockers)}",
                f"mediumBlockerCount: {len(med_blockers)}",
                f"daysSinceEdit: {p['activity'].get('days_since_edit', 0)}",
                f"daysAlive: {days_alive}",
                f"mvaDecision: {p.get('mva_decision', '未决策')}",
                f"firstSeen: {first_seen[:10] if first_seen else 'unknown'}",
                f"lastScan: {p.get('last_scan', '')[:10]}",
                "highBlockers:",
            ]
            for b in high_blocker_msgs:
                frontmatter.append(f"  - \"{b}\"")
            frontmatter.append("blockerList:")
            for b in blocker_msgs:
                frontmatter.append(f"  - \"{b}\"")
            frontmatter.append("---")
            frontmatter.append("")
            frontmatter.append(f"# {p['name']}")
            frontmatter.append("")
            frontmatter.append(f"**项目路径**: `{p['path']}`")
            frontmatter.append("")
            if p["blockers"]:
                frontmatter.append("## 卡点详情")
                for b in p["blockers"]:
                    sev_tag = {"high": "🔴", "medium": "🟡", "low": "⚪"}.get(b["severity"], "")
                    frontmatter.append(f"- {sev_tag} **{b['type']}**: {b['message']}")
                frontmatter.append("")
            if p["tech"].get("needs"):
                frontmatter.append("## 资源需求 #resource-needed")
                for need in p["tech"]["needs"]:
                    frontmatter.append(f"- [ ] {need}")
                frontmatter.append("")
            frontmatter.append("## Git 状态")
            git = p["git"]
            if git["is_repo"]:
                frontmatter.append(f"- 分支: `{git.get('branch', '-')}`")
                if git.get("last_commit"):
                    lc = git["last_commit"]
                    frontmatter.append(f"- 最后提交: `{lc['hash']}` — {lc['message']}")
                frontmatter.append(f"- 未提交: {git.get('uncommitted_count', 0)}, 未推送: {git.get('unpushed', 0)}")
            else:
                frontmatter.append("- 非Git仓库")

            content = "\n".join(frontmatter)
            # Safe filename
            safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in p["name"])
            note_path = f"ProjectOS-Projects/{safe_name}.md"
            self.obsidian.write_file(note_path, content)
            print(f"  [OK] Project note: {note_path}")

    def archive(self, project_name: str):
        """手动归档项目"""
        self.archive_mgr.archive_project(project_name)
        # Regenerate dashboard
        dashboard_md = self.dashboard.generate_dashboard()
        self._write_to_vault("ProjectOS-Dashboard.md", dashboard_md)

    def set_priority(self, project_name: str, priority: str):
        """设置项目优先级 P0/P1/P2/P3"""
        self.registry.set_manual_field(project_name, "priority", priority)
        print(f"设置 {project_name} 优先级为 {priority}")

    def set_mva(self, project_name: str, decision: str):
        """记录MVA决策: All-in / Watch / Kill"""
        self.registry.set_manual_field(project_name, "mva_decision", decision)
        self.registry.set_manual_field(project_name, "mva_date", datetime.now().isoformat())
        print(f"记录 {project_name} MVA决策: {decision}")


def main():
    agent = ProjectAgent()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "archive" and len(sys.argv) > 2:
            agent.archive(sys.argv[2])
        elif cmd == "priority" and len(sys.argv) > 3:
            agent.set_priority(sys.argv[2], sys.argv[3])
        elif cmd == "mva" and len(sys.argv) > 3:
            agent.set_mva(sys.argv[2], sys.argv[3])
        else:
            print("用法:")
            print("  python project_agent.py           # 执行完整扫描")
            print("  python project_agent.py archive <项目名>  # 归档项目")
            print("  python project_agent.py priority <项目名> P0/P1/P2/P3")
            print("  python project_agent.py mva <项目名> All-in/Watch/Kill")
    else:
        agent.run()


if __name__ == "__main__":
    main()
