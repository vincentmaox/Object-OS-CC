import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\ClaudeCodeProjects\_ProjectOS")
AGENT = ROOT / "agent"
PYTHON = sys.executable
USER_OPEN_ID = "ou_59a5d4b0cc115a66295961a1aec66a9e"
REPORT_LOG = AGENT / "daily_report.log"
FREQ_DAILY_LOG = ROOT / "frequency_os" / "daily_log.md"


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


def _grep(pattern: str, text: str) -> str:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else ""


def push_frequency_focus() -> int:
    """读 frequency_os/daily_log.md 当日条目，推一条「今日主频咒语」到飞书。

    在项目卡片之前推送，让老茅进飞书第一眼就看到当天主线。
    daily_log.md 缺失 / 当日未填 / 主频或咒语为空 → 静默跳过，不阻塞主流程。
    """
    if not FREQ_DAILY_LOG.exists():
        _log("focus: frequency_os/daily_log.md not found, skip")
        return 0

    text = FREQ_DAILY_LOG.read_text(encoding="utf-8", errors="replace")
    today = datetime.now().strftime("%Y-%m-%d")
    m = re.search(rf"## {re.escape(today)}.*?(?=\n## |\Z)", text, re.S)
    if not m:
        _log(f"focus: no daily entry for {today}, skip")
        return 0
    block = m.group(0)
    main_freq = _grep(r"今日唯一主频：[ \t]*([^\n]+)", block)
    mantra = _grep(r"今日主频咒语：[ \t]*([^\n]+)", block)
    if not main_freq or "主频" in main_freq and not re.search(r"[^\s_]", main_freq):
        _log(f"focus: main_freq empty for {today}, skip")
        return 0

    sys.path.insert(0, str(AGENT))
    try:
        from feishu_sync import FeishuClient
        client = FeishuClient()
        content = (
            f"**主频目标**：{main_freq}\n\n"
            f"**今日咒语**：{mantra or '（未填）'}\n\n"
            f"_（来自 frequency_os/daily_log.md，前一晚 22:00 前填写）_"
        )
        result = client.send_rich_message(
            target=USER_OPEN_ID,
            title=f"🎯 今日主频 · {today}",
            content=content,
            target_type="user_id",
        )
        ok = bool(result.get("data"))
        _log(f"focus: push {'ok' if ok else 'failed'}")
        return 0 if ok else 1
    except Exception as e:
        _log(f"focus: error: {e}")
        return 1


def main() -> int:
    _log("=== 启动 daily_projectos_report ===")
    code = 0
    code |= run([PYTHON, str(AGENT / "project_agent.py")])
    code |= run([PYTHON, str(AGENT / "export_public_registry.py")])
    code |= git_push_public_data()
    code |= run([PYTHON, str(AGENT / "feishu_sync.py"), "sync-base"])
    code |= push_frequency_focus()
    code |= run([PYTHON, str(AGENT / "feishu_sync.py"), "send-cards", USER_OPEN_ID])
    code |= run([PYTHON, str(AGENT / "feishu_sync.py"), "alert", USER_OPEN_ID])
    _log(f"=== 完成 exit_code={code} ===")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
