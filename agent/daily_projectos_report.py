import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"D:\ClaudeCodeProjects\_ProjectOS")
AGENT = ROOT / "agent"
PYTHON = sys.executable
USER_OPEN_ID = "ou_59a5d4b0cc115a66295961a1aec66a9e"


def run(args: list[str]) -> int:
    print(f"$ {' '.join(args)}", flush=True)
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
    print(proc.stdout, flush=True)
    return proc.returncode


def main() -> int:
    code = 0
    code |= run([PYTHON, str(AGENT / "project_agent.py")])
    code |= run([PYTHON, str(AGENT / "feishu_sync.py"), "sync-base"])
    code |= run([PYTHON, str(AGENT / "feishu_sync.py"), "send-report", USER_OPEN_ID])
    code |= run([PYTHON, str(AGENT / "feishu_sync.py"), "alert", USER_OPEN_ID])
    return code


if __name__ == "__main__":
    raise SystemExit(main())
