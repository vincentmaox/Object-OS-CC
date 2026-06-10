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


def main() -> int:
    _log("=== 启动 daily_projectos_report ===")
    code = 0
    code |= run([PYTHON, str(AGENT / "project_agent.py")])
    code |= run([PYTHON, str(AGENT / "feishu_sync.py"), "sync-base"])
    code |= run([PYTHON, str(AGENT / "feishu_sync.py"), "send-cards", USER_OPEN_ID])
    code |= run([PYTHON, str(AGENT / "feishu_sync.py"), "alert", USER_OPEN_ID])
    _log(f"=== 完成 exit_code={code} ===")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
