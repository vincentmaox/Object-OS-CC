import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\ClaudeCodeProjects\_ProjectOS")
AGENT = ROOT / "agent"
PYTHON = sys.executable
REPORT_LOG = AGENT / "daily_report.log"


def _log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    try:
        with open(REPORT_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run(args: list[str], timeout: int = 600) -> int:
    """跑子进程并实时打印 stdout，避免 Windows PIPE 缓冲死锁。

    返回 0=成功，1=失败/超时/异常。失败不抛异常，让 main() 用 code |= 继续下一步。
    """
    _log(f"$ {' '.join(args)}")
    try:
        proc = subprocess.Popen(
            args,
            cwd=str(AGENT),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
            bufsize=1,
        )
    except Exception as e:
        _log(f"  [SPAWN-ERROR] {e}")
        return 1

    try:
        for ln in proc.stdout:
            _log(f"  {ln.rstrip()}")
        proc.wait(timeout=timeout)
        rc = proc.returncode
        if rc != 0:
            _log(f"  [exit={rc}]")
        return 0 if rc == 0 else 1
    except subprocess.TimeoutExpired:
        proc.kill()
        _log(f"  [TIMEOUT after {timeout}s, killed]")
        return 1
    except Exception as e:
        proc.kill()
        _log(f"  [RUN-ERROR] {e}")
        return 1


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
    code |= run([PYTHON, str(AGENT / "project_agent.py")], timeout=600)
    code |= run([PYTHON, str(AGENT / "export_public_registry.py")], timeout=300)
    code |= git_push_public_data()
    code |= run([PYTHON, str(AGENT / "feishu_sync.py"), "sync-base"], timeout=300)
    # v0.7.0 信息减负（2026-09-10）：send-cards 90+ 张卡片 / alert / 独立主频推送下线，
    # 合并为一条群早报（含主频咒语 + 今日三启动），发「AI项目」群
    code |= run([PYTHON, str(AGENT / "daily_digest.py"), "--morning"], timeout=300)
    _log(f"=== 完成 exit_code={code} ===")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
