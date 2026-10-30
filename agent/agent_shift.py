#!/usr/bin/env python3
"""agent_shift.py — 军团上班/下班一键开关 (v0.7.13, 2026-10-30)

老茅内存吃紧 (16G 机器多 agent 并跑), 团队频道一键:
  off (下班): 禁用 agent 计划任务 + docker compose stop + 杀后台服务进程
  on  (上班): 启用计划任务 + docker compose start + 拉起后台服务

用法:
  python agent_shift.py off|on|status

状态: data/agent_shift.json。幂等: 重复 off/on 无害。
保护名单 (永不动): hermes-desktop。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

WORKDIR = Path(r"D:\ClaudeCodeProjects\_ProjectOS")
PROFILES_PATH = WORKDIR / "config" / "agent_profiles.json"
STATE_PATH = WORKDIR / "data" / "agent_shift.json"
LOG = WORKDIR / "agent" / "agent_shift.log"

PROTECTED = {"hermes-desktop"}


def _log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, file=sys.stderr, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_profiles() -> dict:
    return json.loads(PROFILES_PATH.read_text(encoding="utf-8"))


# ─── 计划任务开关 ──────────────────────────────────────────

def _tasks_by_prefix(prefix: str) -> list[str]:
    ps = f"Get-ScheduledTask | Where-Object {{ $_.TaskPath -eq '\\' -and $_.TaskName -like '{prefix}*' }} | Select-Object -ExpandProperty TaskName"
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=60)
    return [l.strip() for l in r.stdout.decode("utf-8", errors="replace").splitlines() if l.strip()]


def _shift_tasks(prefix: str, disable: bool) -> int:
    """禁用/启用一组计划任务, 返回操作数。"""
    names = _tasks_by_prefix(prefix)
    if not names:
        return 0
    verb = "Disable" if disable else "Enable"
    ok = 0
    for n in names:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"{verb}-ScheduledTask -TaskName '{n}' | Out-Null; if ($?) {{ Write-Output ok }}"],
            capture_output=True, timeout=60,
        )
        if "ok" in r.stdout.decode("utf-8", errors="replace"):
            ok += 1
    return ok


# ─── docker 服务开关 ───────────────────────────────────────

def _shift_docker(project_path: str, stop: bool) -> bool:
    """docker compose stop/start, cwd=项目根。docker 不可用返回 False。"""
    verb = "stop" if stop else "start"
    try:
        r = subprocess.run(
            ["docker", "compose", verb],
            cwd=project_path, capture_output=True, timeout=180,
        )
        return r.returncode == 0
    except Exception as e:
        _log(f"[shift] docker {verb} failed ({project_path}): {e}")
        return False


# ─── 后台进程 kill / 拉起 ─────────────────────────────────

def _kill_by_pattern(pattern: str) -> int:
    """杀 cmdline 含 pattern 的进程 (pythonw 后台服务等), 返回击杀数。"""
    import psutil
    killed = 0
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            cmd = " ".join(p.info["cmdline"] or []).lower()
            if pattern.lower() in cmd:
                p.kill()
                killed += 1
        except Exception:
            continue
    return killed


def _start_cmd(cmd: list[str], cwd: str | None = None) -> bool:
    """静默拉起后台服务 (无窗口)。"""
    flags = 0x08000000  # CREATE_NO_WINDOW
    try:
        subprocess.Popen(
            cmd, cwd=cwd, creationflags=flags,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as e:
        _log(f"[shift] start failed ({cmd[0]}): {e}")
        return False


# ─── 主流程 ────────────────────────────────────────────────

def shift(mode: str) -> dict:
    off = mode == "off"
    profiles = load_profiles()
    results = []
    for agent in profiles.get("agents", []):
        name = agent["name"]
        if name in PROTECTED:
            results.append({"agent": name, "action": "skip(protected)"})
            continue
        r = {"agent": name}
        prefix = agent.get("scheduled_task_prefix", "")
        if prefix and agent.get("run_mode") == "scheduled":
            r["tasks"] = _shift_tasks(prefix, disable=off)
        if agent.get("run_mode") == "service":
            r["docker"] = _shift_docker(agent.get("project_path", ""), stop=off)
        kill_pat = agent.get("shift_kill_pattern", "")
        start_cmd = agent.get("shift_start_cmd", "")
        if kill_pat and off:
            r["killed"] = _kill_by_pattern(kill_pat)
        if start_cmd and not off:
            r["started"] = _start_cmd(start_cmd, agent.get("project_path") or None)
        results.append(r)
        _log(f"[shift] {mode} {name}: {r}")

    state = {"mode": mode, "ts": datetime.now().isoformat(timespec="seconds"), "results": results}
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def status() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"mode": "on", "ts": "", "results": []}


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    if mode in ("on", "off"):
        state = shift(mode)
        print(json.dumps(state, ensure_ascii=False, indent=2))
    elif mode == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2))
    else:
        print("Usage: python agent_shift.py on|off|status")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
