import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\ClaudeCodeProjects\_ProjectOS")
AGENT = ROOT / "agent"
PYTHON = sys.executable
USER_OPEN_ID = "ou_59a5d4b0cc115a66295961a1aec66a9e"
REPORT_LOG = AGENT / "daily_report.log"


def _log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    try:
        with open(REPORT_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run(args: list[str]) -> int:
    _log(f"$ {' '.join(args)}")
    proc = subprocess.run(
        args,
        cwd=str(AGENT),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=os.environ.copy(),
    )
    for ln in proc.stdout.splitlines():
        _log(f"  {ln}")
    return proc.returncode


def git_push_public_data() -> int:
    """Auto-commit + push if public data files changed (triggers site rebuild via webhook)."""
    changed = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=str(ROOT), capture_output=True, text=True,
    ).stdout.strip()
    public_files = [f for f in changed.splitlines()
                    if f.startswith("data/public-")]
    if not public_files:
        _log("git: no public data changes, skip push")
        return 0
    _log(f"git: public data changed: {public_files}")
    for f in public_files:
        subprocess.run(["git", "add", f], cwd=str(ROOT))
    date_tag = datetime.now().strftime("%Y-%m-%d")
    subprocess.run(
        ["git", "commit", "-m",
         f"auto: daily public-registry update {date_tag}"],
        cwd=str(ROOT),
    )
    rc = subprocess.run(["git", "push"], cwd=str(ROOT)).returncode
    _log(f"git: push rc={rc}")
    return rc


def main() -> int:
    _log("=== 启动 daily_projectos_report ===")
    code = 0
    code |= run([PYTHON, str(AGENT / "project_agent.py")])
    code |= run([PYTHON, str(AGENT / "export_public_registry.py")])
    code |= git_push_public_data()
    code |= run([PYTHON, str(AGENT / "feishu_sync.py"), "sync-base"])
    code |= run([PYTHON, str(AGENT / "feishu_sync.py"), "send-cards", USER_OPEN_ID])
    code |= run([PYTHON, str(AGENT / "feishu_sync.py"), "alert", USER_OPEN_ID])
    _log(f"=== 完成 exit_code={code} ===")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
