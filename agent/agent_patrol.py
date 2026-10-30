#!/usr/bin/env python3
"""agent_patrol.py — 使魔军团巡检 + 内存哨兵 (P0, 2026-10-14)

老茅的 agent 团队管理入口。两个模式:

1. 全量巡检 (默认, 每晚一次, 挂 daily_digest 前或单独计划任务):
   python agent_patrol.py
   对 agent_profiles.json 里每个 agent 采集证据:
   - Windows 计划任务最近运行 (state/last_run/last_result)
   - git 当日 commit 数
   - conversation_log.md 当日段
   - 进程扫描 (process_patterns 匹配 -> 进程数 + 内存合计)
   判定: 在岗干活 / 在岗摸鱼 / 未上岗 / 阵亡
   输出 data/agent_patrol.json (daily_digest 军团点名段的数据源)

2. 内存哨兵 (--memory-watch, 10 分钟一次, 挂现有监控节奏):
   python agent_patrol.py --memory-watch
   只做内存水位 + agent 归属; 可用内存 < 阈值 (profiles.memory_alert_threshold_gb)
   推飞书「AI项目」群, 点名建议暂停的非主线高内存 agent。
   2 小时内同状态去重 (state 文件 agent_patrol_memstate.json)。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

WORKDIR = Path(r"D:\ClaudeCodeProjects\_ProjectOS")
PROFILES_PATH = WORKDIR / "config" / "agent_profiles.json"
OUT_PATH = WORKDIR / "data" / "agent_patrol.json"
MEMSTATE_PATH = WORKDIR / "data" / "agent_patrol_memstate.json"
PATROL_LOG = WORKDIR / "agent" / "agent_patrol.log"

GROUP_CHAT_ID = "oc_5d4f19d5324dc0f84a9377796ff8e9e5"  # 「AI项目」群

# 主线保护名单: 内存吃紧时绝不建议暂停 (老茅的核心工作台)
PROTECTED = {"hermes-desktop"}

MEM_DEDUPE_S = 2 * 60 * 60


def _log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, file=sys.stderr, flush=True)
    try:
        with open(PATROL_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_profiles() -> dict:
    return json.loads(PROFILES_PATH.read_text(encoding="utf-8"))


# ─── 证据采集 ──────────────────────────────────────────────

def _schtasks_snapshot() -> dict[str, dict]:
    """一次拉全部计划任务: name -> {state, last_run, last_result}。失败返回 {}。"""
    ps = (
        "$tasks = Get-ScheduledTask | Where-Object { $_.TaskPath -eq '\\' }; "
        "foreach ($t in $tasks) { $i = $t | Get-ScheduledTaskInfo; "
        "$lr = if ($i.LastRunTime -and $i.LastRunTime.Year -gt 2000) { $i.LastRunTime.ToString('yyyy-MM-dd HH:mm') } else { '' }; "
        "$res = $i.LastTaskResult; "
        "$ok = if ($res -eq 0 -or $res -eq 267009 -or $res -eq 267011) { 'ok' } else { 'fail' }; "
        "Write-Output ($t.TaskName + '|' + $t.State + '|' + $lr + '|' + $ok) }"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, timeout=120,
        )
        out = r.stdout.decode("utf-8", errors="replace")
    except Exception as e:
        _log(f"[patrol] schtasks snapshot failed: {e}")
        return {}
    snap: dict[str, dict] = {}
    for line in out.splitlines():
        parts = line.strip().split("|")
        if len(parts) != 4:
            continue
        name, state, last_run, result = parts
        snap[name] = {"state": state, "last_run": last_run, "last_result": result}
    return snap


def _scan_processes(patterns: list[str]) -> dict:
    """按进程名或命令行匹配 pattern (node/python 等通用名靠 cmdline 路径归属),
    返回 {count, mem_mb, top: [(name, mb)]}。"""
    if not patterns:
        return {"count": 0, "mem_mb": 0, "top": []}
    try:
        import psutil
    except ImportError:
        return {"count": 0, "mem_mb": 0, "top": []}
    pats = [pat.lower() for pat in patterns]
    hits = []
    try:
        for p in psutil.process_iter(["name", "memory_info", "cmdline"]):
            try:
                name = (p.info["name"] or "").lower()
                cmdline = " ".join(p.info["cmdline"] or []).lower()
                if not any(pat in name or pat in cmdline for pat in pats):
                    continue
                rss = p.info["memory_info"].rss if p.info["memory_info"] else 0
                hits.append((p.info["name"], rss / 1e6))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        _log(f"[patrol] process scan failed: {e}")
        return {"count": 0, "mem_mb": 0, "top": []}
    hits.sort(key=lambda x: -x[1])
    return {
        "count": len(hits),
        "mem_mb": round(sum(mb for _, mb in hits)),
        "top": [(n, round(mb)) for n, mb in hits[:4]],
    }


def _git_today_commits(project_path: str) -> int:
    """项目当日 commit 数 (证据之一)。"""
    if not project_path or not Path(project_path).exists():
        return 0
    try:
        r = subprocess.run(
            ["git", "-C", project_path, "log", "--oneline", "--since", "00:00", "--until", "23:59"],
            capture_output=True, timeout=30,
        )
        return len([l for l in r.stdout.decode("utf-8", errors="replace").splitlines() if l.strip()])
    except Exception:
        return 0


def _convlog_today(project_path: str) -> bool:
    """conversation_log.md 是否有当日段 (被老茅手动调用过的痕迹)。"""
    p = Path(project_path or "") / "conversation_log.md"
    if not p.exists():
        return False
    try:
        return f"## {date.today().isoformat()}" in p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False


# ─── 判定 ──────────────────────────────────────────────────

def _judge(agent: dict, tasks: dict, procs: dict, git_commits: int, conv_today: bool) -> tuple[str, str]:
    """返回 (status, evidence)。status: working/idle_resident/not_deployed/dead"""
    name = agent["name"]
    run_mode = agent.get("run_mode", "ondemand")
    prefix = agent.get("scheduled_task_prefix", "")

    my_tasks = {k: v for k, v in tasks.items() if prefix and k.startswith(prefix)}
    task_fail = [k for k, v in my_tasks.items() if v["last_result"] == "fail"]
    task_recent_today = any(v["last_run"].startswith(date.today().isoformat()) for v in my_tasks.values())

    ev = []
    if my_tasks:
        ev.append(f"任务x{len(my_tasks)}(今日跑{sum(1 for v in my_tasks.values() if v['last_run'].startswith(date.today().isoformat()))})")
    if procs["count"]:
        ev.append(f"进程x{procs['count']}({procs['mem_mb']}MB)")
    if git_commits:
        ev.append(f"commit+{git_commits}")
    if conv_today:
        ev.append("今日有对话")

    # 阵亡: 全部任务上次运行都失败 (部分失败只标注, 常见 0x800710E0 条件类)
    if my_tasks and len(task_fail) == len(my_tasks):
        return "dead", "; ".join(ev) or "无证据"
    if task_fail:
        ev.append(f"⚠️部分任务失败x{len(task_fail)}/共{len(my_tasks)}")
    # resident 常驻型 (hermes/secretary server): 进程在 = 活着, 不要求"今日产出"
    if run_mode == "resident":
        if procs["count"] > 0:
            return "working", "; ".join(ev) or f"常驻进程x{procs['count']}"
    # 在岗干活: 有今日证据 (任务今天跑过 / commit / 对话)
    if task_recent_today or git_commits > 0 or conv_today:
        return "working", "; ".join(ev)
    # 在岗摸鱼: 进程在或任务是 Ready 但今日无产出
    if procs["count"] > 0 or (my_tasks and run_mode == "scheduled"):
        return "idle_resident", "; ".join(ev) or "任务在但今日无产出"
    # 未上岗: 无进程无任务无今日活动
    return "not_deployed", "; ".join(ev) or "无进程/无任务/无今日活动"


STATUS_LABEL = {
    "working": "在岗干活",
    "idle_resident": "在岗摸鱼",
    "not_deployed": "未上岗",
    "dead": "阵亡",
}


def patrol_all() -> dict:
    profiles = load_profiles()
    tasks = _schtasks_snapshot()
    _log(f"[patrol] schtasks snapshot: {len(tasks)} tasks")

    agents_out = []
    for agent in profiles.get("agents", []):
        procs = _scan_processes(agent.get("process_patterns", []))
        commits = _git_today_commits(agent.get("project_path", ""))
        conv_today = _convlog_today(agent.get("project_path", ""))
        status, evidence = _judge(agent, tasks, procs, commits, conv_today)
        agents_out.append({
            "name": agent["name"],
            "role": agent.get("role", ""),
            "run_mode": agent.get("run_mode", ""),
            "status": status,
            "status_label": STATUS_LABEL[status],
            "evidence": evidence,
            "proc_count": procs["count"],
            "mem_mb": procs["mem_mb"],
        })
        _log(f"[patrol] {agent['name']}: {status} ({evidence})")

    mem = _mem_snapshot()
    result = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "memory": mem,
        "agents": agents_out,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"[patrol] written {OUT_PATH}")
    return result


# ─── 内存哨兵 ──────────────────────────────────────────────

def _mem_snapshot() -> dict:
    import psutil
    m = psutil.virtual_memory()
    return {
        "total_gb": round(m.total / 1e9, 1),
        "available_gb": round(m.available / 1e9, 1),
        "percent": m.percent,
    }


def memory_watch() -> None:
    """轻量模式: 内存水位 + agent 归属 + 阈值预警。10 分钟一跑。"""
    profiles = load_profiles()
    threshold = float(profiles.get("memory_alert_threshold_gb", 2.0))
    mem = _mem_snapshot()
    _log(f"[memwatch] avail {mem['available_gb']}GB / {mem['percent']}%")

    agent_mem = []
    for agent in profiles.get("agents", []):
        procs = _scan_processes(agent.get("process_patterns", []))
        if procs["mem_mb"] > 50:  # 只记有存在感的
            agent_mem.append((agent["name"], procs["mem_mb"], procs["count"]))
    agent_mem.sort(key=lambda x: -x[1])
    _log(f"[memwatch] agent mem: {[(n, mb) for n, mb, _ in agent_mem]}")

    alerting = mem["available_gb"] < threshold
    if not alerting:
        _write_memstate("ok")
        return

    # 去重: 同状态 2h 内不重复推
    if _read_memstate() == "alert" and _memstate_fresh():
        _log("[memwatch] alert 状态 2h 内已推过, 跳过")
        return

    # 建议暂停名单: 非保护 + 内存大 + 非在岗干活优先 (摸鱼的大户先停)
    patrol = {}
    try:
        patrol = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    status_map = {a["name"]: a.get("status") for a in patrol.get("agents", [])}
    suspend_candidates = [
        (n, mb, c) for n, mb, c in agent_mem
        if n not in PROTECTED and status_map.get(n) != "working"
    ] or agent_mem and [(n, mb, c) for n, mb, c in agent_mem if n not in PROTECTED] or []

    lines = [
        "⚠️ 内存水位预警",
        "",
        f"可用 {mem['available_gb']}GB / 共 {mem['total_gb']}GB (已用 {mem['percent']}%)，低于阈值 {threshold}GB。",
        "",
        "各 agent 内存占用:",
    ]
    for n, mb, c in agent_mem[:8]:
        lines.append(f"- {n}: {mb}MB ({c} 进程)")
    if suspend_candidates:
        lines.append("")
        lines.append("建议优先暂停（非主线 + 高占用）:")
        for n, mb, c in suspend_candidates[:3]:
            lines.append(f"- {n} ({mb}MB)")
    lines.append("")
    lines.append("_(内存哨兵 · 每 10 分钟巡检 · 电脑升级前凑合版)_")

    ok = _push_feishu("🚨 军团内存预警", "\n".join(lines))
    _write_memstate("alert" if ok else "alert_failed")
    _log(f"[memwatch] alert pushed ok={ok}")


def _push_feishu(title: str, content: str) -> bool:
    sys.path.insert(0, str(WORKDIR / "agent"))
    try:
        from feishu_sync import FeishuClient
        result = FeishuClient().send_rich_message(
            target=GROUP_CHAT_ID, title=title, content=content, target_type="chat_id",
        )
        return bool(result.get("data"))
    except Exception as e:
        _log(f"[memwatch] feishu push failed: {e}")
        return False


def _read_memstate() -> str | None:
    try:
        return json.loads(MEMSTATE_PATH.read_text(encoding="utf-8")).get("state")
    except Exception:
        return None


def _memstate_fresh() -> bool:
    try:
        ts = json.loads(MEMSTATE_PATH.read_text(encoding="utf-8")).get("ts", 0)
        return (datetime.now().timestamp() - ts) < MEM_DEDUPE_S
    except Exception:
        return False


def _write_memstate(state: str) -> None:
    try:
        MEMSTATE_PATH.write_text(
            json.dumps({"state": state, "ts": datetime.now().timestamp()}), encoding="utf-8"
        )
    except Exception:
        pass


def main() -> int:
    if "--memory-watch" in sys.argv:
        memory_watch()
        return 0
    result = patrol_all()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
