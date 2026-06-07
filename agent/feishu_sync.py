#!/usr/bin/env python3
"""
Feishu Sync Engine - 飞书同步引擎
将ProjectOS数据同步到飞书：
1. 每日项目晨报推送（机器人消息）
2. 项目注册表同步到飞书多维表格
3. Obsidian文档同步到飞书文档
4. 卡点/决策提醒推送
"""

import os
import sys
import io
import json
import subprocess
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Fix Windows encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE_DIR = Path("D:/ClaudeCodeProjects")
OS_DIR = BASE_DIR / "_ProjectOS"
DATA_DIR = OS_DIR / "data"
REGISTRY_FILE = DATA_DIR / "registry.json"

# Feishu/Lark CLI wrapper
class FeishuClient:
    """飞书CLI客户端封装"""

    def __init__(self, cli_path: str = "lark-cli"):
        # Windows: use .cmd extension
        if os.name == "nt" and not cli_path.endswith(".cmd"):
            cli_path += ".cmd"
        self.cli_path = cli_path

    def _run(self, args: List[str], format_json: bool = True) -> Dict:
        # lark-cli outputs JSON by default; no --format flag needed
        try:
            if os.name == "nt":
                # Windows: build escaped command string for cmd.exe so JSON quotes survive
                parts = [self.cli_path]
                for a in args:
                    if a.startswith("-") or not any(c in a for c in ' "\'{}[]'):
                        parts.append(a)
                    else:
                        escaped = a.replace('"', '\\"')
                        parts.append(f'"{escaped}"')
                cmd_str = " ".join(parts)
                result = subprocess.run(
                    cmd_str,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=60,
                    shell=True
                )
            else:
                result = subprocess.run(
                    [self.cli_path] + args,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=60
                )
            if result.returncode != 0:
                print(f"[ERR] lark-cli exited with {result.returncode}: {result.stderr}")
                return {"ok": False, "error": result.stderr}
            if format_json:
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    return {"ok": True, "raw": result.stdout}
            return {"ok": True, "raw": result.stdout}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # === Message / IM ===
    def send_message(self, target: str, content: str, target_type: str = "user_id", as_bot: bool = True) -> Dict:
        """发送消息

        target_type: 'user_id' (ou_xxx) or 'chat_id' (oc_xxx)
        as_bot: default True — use bot identity (doesn't need user scopes)
        """
        flag = "--user-id" if target_type == "user_id" else "--chat-id"
        args = [
            "im", "+messages-send",
            flag, target,
            "--text", content
        ]
        if as_bot:
            args.extend(["--as", "bot"])
        return self._run(args)

    def send_rich_message(self, target: str, title: str, content: str, target_type: str = "user_id", as_bot: bool = True) -> Dict:
        """发送富文本消息（项目晨报格式）"""
        flag = "--user-id" if target_type == "user_id" else "--chat-id"
        post_content = {
            "zh_cn": {
                "title": title,
                "content": [
                    [{"tag": "text", "text": line}]
                    for line in content.split("\n") if line.strip()
                ]
            }
        }
        args = [
            "im", "+messages-send",
            flag, target,
            "--msg-type", "post",
            "--content", json.dumps(post_content, ensure_ascii=False)
        ]
        if as_bot:
            args.extend(["--as", "bot"])
        return self._run(args)

    def send_markdown(self, target: str, markdown: str, target_type: str = "user_id", as_bot: bool = True) -> Dict:
        """发送Markdown消息"""
        flag = "--user-id" if target_type == "user_id" else "--chat-id"
        args = [
            "im", "+messages-send",
            flag, target,
            "--markdown", markdown
        ]
        if as_bot:
            args.extend(["--as", "bot"])
        return self._run(args)

    # === Base / Multidimensional Table ===
    def create_base(self, name: str, folder_token: str = None) -> Dict:
        """创建多维表格"""
        args = ["base", "+base-create", "--name", name]
        if folder_token:
            args.extend(["--folder-token", folder_token])
        return self._run(args)

    def create_table(self, app_token: str, table_name: str, fields: List[Dict]) -> Dict:
        """创建数据表"""
        return self._run([
            "base", "+table-create",
            "--base-token", app_token,
            "--name", table_name,
            "--fields", json.dumps(fields, ensure_ascii=False)
        ])

    def add_records(self, app_token: str, table_id: str, payload: Dict) -> Dict:
        """批量添加记录

        payload: {"fields": ["F1", "F2"], "rows": [[v1, v2], ...]}
        """
        return self._run([
            "base", "+record-batch-create",
            "--base-token", app_token,
            "--table-id", table_id,
            "--json", json.dumps(payload, ensure_ascii=False)
        ])

    def update_records(self, app_token: str, table_id: str, payload: Dict) -> Dict:
        """批量更新记录"""
        return self._run([
            "base", "+record-batch-update",
            "--base-token", app_token,
            "--table-id", table_id,
            "--json", json.dumps(payload, ensure_ascii=False)
        ])

    # === Docs ===
    def create_doc(self, title: str, content: str, folder_token: str = None) -> Dict:
        """创建飞书文档"""
        # First create empty doc
        create_result = self._run([
            "docs", "+create",
            "--title", title,
            "--folder-token", folder_token or ""
        ])
        return create_result

    def import_markdown(self, title: str, md_content: str) -> Dict:
        """导入Markdown为飞书文档"""
        # Write temp file
        temp_path = OS_DIR / "temp_import.md"
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        # Use markdown import
        result = self._run([
            "markdown", "+import",
            "--title", title,
            "--file", str(temp_path)
        ])
        temp_path.unlink(missing_ok=True)
        return result

    # === Calendar / Tasks ===
    def create_task(self, summary: str, due_date: str = None) -> Dict:
        """创建飞书任务"""
        args = ["task", "+task-create", "--summary", summary]
        if due_date:
            args.extend(["--due-date", due_date])
        return self._run(args)

    # === Auth ===
    def auth_status(self) -> Dict:
        """检查认证状态"""
        return self._run(["auth", "status"])

    def get_me(self) -> Dict:
        """获取当前用户信息"""
        return self._run(["contact", "+users-get-me"])


class ProjectSyncEngine:
    """项目同步引擎"""

    def __init__(self):
        self.feishu = FeishuClient()
        self.registry = self._load_registry()

    def _load_registry(self) -> Dict:
        if REGISTRY_FILE.exists():
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"projects": {}, "version": 2, "last_update": None}

    # === 1. Daily Morning Report ===
    def generate_daily_report_text(self) -> str:
        """生成晨报文本"""
        projects = self.registry.get("projects", {})
        now = datetime.now()
        date_str = now.strftime("%Y年%m月%d日")

        lines = [f"📊 ProjectOS 项目晨报 — {date_str}", "", "今日优先事项："]

        priority_projects = []
        for name, p in projects.items():
            status = p.get("status", "未知")
            blockers = p.get("blockers", [])
            blockers_high = [b for b in blockers if b.get("severity") == "high"]
            blockers_med = [b for b in blockers if b.get("severity") == "medium"]

            if blockers_high:
                for b in blockers_high:
                    lines.append(f"🔴 【{name}】{b.get('message', '')}")
            if blockers_med:
                for b in blockers_med:
                    lines.append(f"🟡 【{name}】{b.get('message', '')}")

            if status in ["活跃", "进行中"] and not blockers_high:
                days_edit = p.get("activity", {}).get("days_since_edit")
                days_str = f"{days_edit:.0f}天前" if days_edit else "?"
                lines.append(f"🟢 【{name}】持续推进，上次活动 {days_str}")

            if status == "停滞":
                days = p.get("activity", {}).get("days_since_edit", 0)
                lines.append(f"⚪ 【{name}】已停滞 {days:.0f} 天，需决策")

            priority = p.get("priority")
            if priority in ["P0", "P1"]:
                priority_projects.append((priority, name, status))

        lines.extend(["", "项目状态总览："])
        status_counts = {}
        for _, p in projects.items():
            s = p.get("status", "未知")
            status_counts[s] = status_counts.get(s, 0) + 1
        for status, count in sorted(status_counts.items()):
            lines.append(f"- {status}: {count} 个")

        # MVA 72h check
        mva_due = []
        for name, p in projects.items():
            first_seen = p.get("first_seen")
            if first_seen:
                try:
                    fs = datetime.fromisoformat(first_seen)
                    days_alive = (now - fs).days
                    if days_alive >= 3 and p.get("mva_decision", "未决策") == "未决策":
                        mva_due.append((name, days_alive))
                except (ValueError, TypeError):
                    pass
        if mva_due:
            lines.extend(["", "⏰ 72小时 MVA 决策待处理："])
            for name, days in mva_due:
                lines.append(f"- {name} 已运行 {days} 天")

        lines.extend(["", "---"])
        lines.append("在 Obsidian 中查看完整看板: ProjectOS-Dashboard.md")
        return "\n".join(lines)

    def send_daily_report(self, target: str, target_type: str = "user_id") -> Dict:
        """发送每日项目晨报"""
        title = f"ProjectOS 项目晨报 — {datetime.now().strftime('%Y-%m-%d')}"
        content = self.generate_daily_report_text()
        print(f"[Sending] 晨报发送至 {target_type}={target}")
        return self.feishu.send_rich_message(target, title, content, target_type)

    # === 2. Sync Registry to Feishu Base (Multidimensional Table) ===
    def _get_base_config(self) -> Optional[Dict]:
        """获取已保存的base配置"""
        config_file = DATA_DIR / "feishu-base-config.json"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def _save_base_config(self, config: Dict):
        """保存base配置"""
        config_file = DATA_DIR / "feishu-base-config.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def create_project_base(self, base_name: str = "ProjectOS 项目注册表") -> Dict:
        """创建项目多维表格结构（如已存在则复用）"""
        config = self._get_base_config()
        if config:
            return {"ok": True, "config": config, "reused": True}

        # Create base app
        result = self.feishu.create_base(base_name)
        if not result.get("ok"):
            return result

        app_token = (
            result.get("data", {}).get("base", {}).get("base_token")
            or result.get("data", {}).get("base_token")
            or result.get("base_token")
            or result.get("app_token")
        )
        if not app_token:
            return {"ok": False, "error": "No base_token in result", "raw": result}

        # Define table fields (type: text/number/select/datetime/...)
        fields = [
            {"field_name": "项目名称", "type": "text"},
            {"field_name": "项目状态", "type": "text"},
            {"field_name": "优先级", "type": "text"},
            {"field_name": "技术栈", "type": "text"},
            {"field_name": "卡点数量", "type": "number"},
            {"field_name": "高严重卡点", "type": "number"},
            {"field_name": "上次编辑(天前)", "type": "number"},
            {"field_name": "MVA决策", "type": "text"},
            {"field_name": "首次发现", "type": "text"},
            {"field_name": "最后更新", "type": "text"},
            {"field_name": "备注", "type": "text"},
        ]

        # Create main table
        table_result = self.feishu.create_table(app_token, "项目总览", fields)

        config = {
            "base_name": base_name,
            "app_token": app_token,
            "main_table_id": table_result.get("table_id", ""),
            "created_at": datetime.now().isoformat()
        }
        self._save_base_config(config)
        return {"ok": True, "config": config}

    def sync_registry_to_base(self) -> Dict:
        """同步注册表到多维表格（三表联动：项目主表+卡点+任务）"""
        config = self._get_base_config()
        if not config:
            return {"ok": False, "error": "feishu-base-config.json missing"}

        app_token = config["app_token"]
        main_tid = config["main_table_id"]
        blocker_tid = config.get("blocker_table_id")
        task_tid = config.get("task_table_id")

        projects = self.registry.get("projects", {})
        now_ms = int(datetime.now().timestamp() * 1000)

        # === 1. 清空三表旧数据（全量重建，简单可靠）===
        for tid in [main_tid, blocker_tid, task_tid]:
            if not tid:
                continue
            list_result = self.feishu._run([
                "base", "+record-list",
                "--base-token", app_token,
                "--table-id", tid,
                "--format", "json",
                "--limit", "200"
            ])
            record_ids = list_result.get("data", {}).get("record_id_list", [])
            if record_ids:
                # batch delete via JSON payload
                for i in range(0, len(record_ids), 500):
                    batch_ids = record_ids[i:i+500]
                    self.feishu._run([
                        "base", "+record-delete",
                        "--base-token", app_token,
                        "--table-id", tid,
                        "--json", json.dumps({"record_id_list": batch_ids}),
                        "--yes"
                    ])

        # === 2. 同步项目主表 ===
        main_fields = [
            "项目名称", "项目状态", "优先级", "MVA决策", "技术栈",
            "健康度(%)", "卡点数", "高严重卡点", "上次活动(天前)", "运行天数",
            "Git分支", "未提交数", "首次发现", "最后扫描", "本地路径"
        ]
        main_rows = []
        project_name_to_seen_ms = {}  # 卡点表/任务表link字段用
        for name, p in projects.items():
            activity = p.get("activity", {})
            git = p.get("git", {})
            blockers = p.get("blockers", [])
            blockers_high = [b for b in blockers if b.get("severity") == "high"]
            docs = p.get("docs", {})

            # 健康度 = doc完整度50% + 无卡点30% + 活跃度20%
            health = 0
            if docs.get("has_readme"): health += 15
            if docs.get("has_claude_md"): health += 20
            if docs.get("has_deployment_plan"): health += 15
            if not blockers: health += 30
            elif not blockers_high: health += 15
            days_edit = activity.get("days_since_edit")
            if days_edit is not None and days_edit < 1: health += 20
            elif days_edit is not None and days_edit < 7: health += 10

            first_seen = self._iso_to_ms(p.get("first_seen"))
            last_scan = self._iso_to_ms(p.get("last_scan"))
            days_alive = 0
            if first_seen:
                days_alive = (now_ms - first_seen) // (86400 * 1000)
                project_name_to_seen_ms[name] = first_seen

            main_rows.append([
                name,
                p.get("status", "活跃"),
                p.get("priority", "未设置"),
                p.get("mva_decision", "未决策"),
                ", ".join(p.get("tech", {}).get("stack", [])) or "—",
                health,
                len(blockers),
                len(blockers_high),
                round(days_edit or 0, 1),
                int(days_alive),
                git.get("branch") or "—",
                git.get("uncommitted_count", 0),
                first_seen,
                last_scan,
                p.get("path", "")
            ])

        main_result = {"ok": True, "skipped": "no rows"}
        if main_rows:
            main_result = self.feishu.add_records(app_token, main_tid, {
                "fields": main_fields, "rows": main_rows
            })

        # === 3. 拿到项目主表的 record_id 映射，用于link字段 ===
        project_record_map = {}
        if main_result.get("ok"):
            list_main = self.feishu._run([
                "base", "+record-list",
                "--base-token", app_token,
                "--table-id", main_tid,
                "--format", "json",
                "--limit", "200"
            ])
            data = list_main.get("data", {})
            record_ids = data.get("record_id_list", [])
            rows_data = data.get("data", [])
            fields_order = data.get("fields", [])
            # 找到"项目名称"列的索引
            try:
                name_idx = fields_order.index("项目名称")
            except ValueError:
                name_idx = -1
            if name_idx >= 0:
                for rid, row in zip(record_ids, rows_data):
                    if name_idx < len(row):
                        project_record_map[row[name_idx]] = rid

        # === 4. 同步卡点表 ===
        blocker_result = {"ok": True, "skipped": "no blockers"}
        if blocker_tid:
            blocker_fields = ["卡点描述", "严重度", "类型", "状态", "所属项目", "发现日期"]
            blocker_rows = []
            sev_map = {"high": "高", "medium": "中", "low": "低"}
            type_map = {
                "missing_doc": "文档缺失",
                "tech_need": "技术需求",
                "deploy_block": "部署阻塞",
                "missing_dep": "依赖缺失",
                "stale": "停滞风险"
            }
            for name, p in projects.items():
                rid = project_record_map.get(name)
                link_val = [{"id": rid}] if rid else []
                for b in p.get("blockers", []):
                    blocker_rows.append([
                        b.get("message", ""),
                        sev_map.get(b.get("severity"), "低"),
                        type_map.get(b.get("type"), "技术需求"),
                        "未处理",
                        link_val,
                        project_name_to_seen_ms.get(name, now_ms)
                    ])
            if blocker_rows:
                blocker_result = self.feishu.add_records(app_token, blocker_tid, {
                    "fields": blocker_fields, "rows": blocker_rows
                })

        # === 5. 同步任务表（资源需求作为待办任务）===
        task_result = {"ok": True, "skipped": "no tasks"}
        if task_tid:
            task_fields = ["任务描述", "状态", "优先级", "所属项目", "已完成"]
            task_rows = []
            for name, p in projects.items():
                rid = project_record_map.get(name)
                link_val = [{"id": rid}] if rid else []
                needs = p.get("tech", {}).get("needs", [])
                proj_prio = p.get("priority", "未设置")
                task_prio = "高" if proj_prio in ["P0", "P1"] else ("中" if proj_prio == "P2" else "低")
                for need in needs:
                    task_rows.append([
                        need,
                        "待办",
                        task_prio,
                        link_val,
                        False
                    ])
            if task_rows:
                task_result = self.feishu.add_records(app_token, task_tid, {
                    "fields": task_fields, "rows": task_rows
                })

        return {
            "ok": True,
            "main": {"synced": len(main_rows), "result": main_result.get("ok")},
            "blockers": {"synced": len([b for p in projects.values() for b in p.get("blockers", [])]), "result": blocker_result.get("ok")},
            "tasks": {"synced": len([n for p in projects.values() for n in p.get("tech", {}).get("needs", [])]), "result": task_result.get("ok")}
        }

    @staticmethod
    def _iso_to_ms(iso: Optional[str]) -> int:
        """ISO字符串转毫秒时间戳"""
        if not iso:
            return 0
        try:
            return int(datetime.fromisoformat(iso).timestamp() * 1000)
        except (ValueError, TypeError):
            return 0

    # === 3. Sync Obsidian Docs to Feishu Docs ===
    def sync_document_to_feishu(self, doc_path: Path, title_prefix: str = "") -> Dict:
        """同步单个Obsidian文档到飞书"""
        if not doc_path.exists():
            return {"ok": False, "error": f"File not found: {doc_path}"}

        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        title = title_prefix + doc_path.stem
        print(f"[Syncing] 同步文档: {title}")
        return self.feishu.import_markdown(title, content)

    def sync_all_project_docs(self) -> Dict:
        """同步所有项目相关文档"""
        results = {}
        # Dashboard
        results["dashboard"] = self.sync_document_to_feishu(
            BASE_DIR / "ProjectOS-Dashboard.md",
            "[项目看板] "
        )
        # Daily report
        results["daily_report"] = self.sync_document_to_feishu(
            BASE_DIR / "ProjectOS-DailyReport.md",
            "[每日晨报] "
        )
        return results

    # === 4. Blocker Alert / Decision Reminder ===
    def send_blocker_alert(self, target: str, target_type: str = "user_id") -> Dict:
        """发送高严重度卡点提醒"""
        projects = self.registry.get("projects", {})
        alerts = []
        for name, p in projects.items():
            for b in p.get("blockers", []):
                if b.get("severity") == "high":
                    alerts.append(f"【{name}】{b.get('message', '')}")

        if not alerts:
            return {"ok": True, "skipped": "No high-severity blockers"}

        title = f"⚠️ ProjectOS 卡点紧急提醒 — {datetime.now().strftime('%Y-%m-%d')}"
        content = "检测到高优先级项目卡点，需要立即处理：\n\n" + "\n".join(alerts)
        return self.feishu.send_rich_message(target, title, content, target_type)

    def send_decision_request(self, target: str, project_name: str, context: str, target_type: str = "user_id") -> Dict:
        """发送决策请求（如72h MVA决策）"""
        content = f"⏰ 需要您对项目 [{project_name}] 做出MVA决策\n\n"
        content += f"决策依据：{context}\n\n"
        content += "请选择：\n- All-in: 继续投入资源\n- Watch: 观察一周\n- Kill: 归档项目"
        return self.feishu.send_message(target, content, target_type)


def main():
    engine = ProjectSyncEngine()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "auth":
            print("=== 认证状态 ===")
            result = engine.feishu.auth_status()
            print(json.dumps(result, ensure_ascii=False, indent=2))

            me = engine.feishu.get_me()
            print("\n=== 用户信息 ===")
            print(json.dumps(me, ensure_ascii=False, indent=2))

        elif cmd == "send-report":
            if len(sys.argv) < 3:
                print("Usage: python feishu_sync.py send-report <ou_xxx_user_id_or_oc_xxx_chat_id>")
                sys.exit(1)
            target = sys.argv[2]
            target_type = "chat_id" if target.startswith("oc_") else "user_id"
            result = engine.send_daily_report(target, target_type)
            print(json.dumps(result, ensure_ascii=False, indent=2))

        elif cmd == "sync-base":
            result = engine.sync_registry_to_base()
            print(json.dumps(result, ensure_ascii=False, indent=2))

        elif cmd == "sync-docs":
            result = engine.sync_all_project_docs()
            print(json.dumps(result, ensure_ascii=False, indent=2))

        elif cmd == "alert":
            if len(sys.argv) < 3:
                print("Usage: python feishu_sync.py alert <ou_xxx_or_oc_xxx>")
                sys.exit(1)
            target = sys.argv[2]
            target_type = "chat_id" if target.startswith("oc_") else "user_id"
            result = engine.send_blocker_alert(target, target_type)
            print(json.dumps(result, ensure_ascii=False, indent=2))

        else:
            print("Commands:")
            print("  auth                       - 检查认证状态")
            print("  send-report <email>        - 发送项目晨报")
            print("  sync-base                  - 同步注册表到多维表格")
            print("  sync-docs                  - 同步看板文档到飞书")
            print("  alert <email>              - 发送卡点紧急提醒")
    else:
        print("Feishu Sync Engine Ready")
        print("Use 'python feishu_sync.py <command>' to run")


if __name__ == "__main__":
    main()
