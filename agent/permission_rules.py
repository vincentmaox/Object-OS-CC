"""
权限自动判定规则：白名单 / 灰名单 / 黑名单。

设计：can_use_tool 入口先过 evaluate()，返回三种判定：
  - 'allow'  无声放行（不发卡片，只记日志）
  - 'ask'    走卡片/命令通道让用户决定
  - 'deny'   无声拒绝（黑名单，防误操作）

规则按顺序匹配，先命中先生效。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Literal

Decision = Literal["allow", "ask", "deny"]


@dataclass
class Rule:
    name: str
    decision: Decision
    matches: Callable[[str, dict], bool]
    reason: str = ""


def _bash_starts_with(prefixes: tuple[str, ...]):
    def check(tool: str, inp: dict) -> bool:
        if tool not in ("Bash", "PowerShell"):
            return False
        cmd = (inp.get("command") or "").strip()
        return any(cmd.startswith(p) for p in prefixes)
    return check


def _bash_matches(pattern: str):
    rx = re.compile(pattern)
    def check(tool: str, inp: dict) -> bool:
        if tool not in ("Bash", "PowerShell"):
            return False
        cmd = (inp.get("command") or "").strip()
        return bool(rx.match(cmd))
    return check


def _tool_in(names: tuple[str, ...]):
    def check(tool: str, _inp: dict) -> bool:
        return tool in names
    return check


# ── 规则表（顺序敏感，黑名单要在白名单之前）─────────────────────────────────

RULES: list[Rule] = [
    # ─ 黑名单 ─（即使是 Read 类也不能碰）
    Rule(
        "deny_rm_rf_root",
        "deny",
        _bash_matches(r"^(rm\s+-rf|Remove-Item\s+.*-Recurse.*-Force)\s+[\"']?[A-Za-z]:[\\/]?\s*$"),
        "禁止删除盘符根目录",
    ),
    Rule(
        "deny_git_force_push_main",
        "deny",
        _bash_matches(r"^git\s+push\s+.*--force.*(main|master)"),
        "禁止 force push main/master",
    ),
    Rule(
        "deny_reset_hard_no_target",
        "deny",
        _bash_matches(r"^git\s+reset\s+--hard\s*$"),
        "禁止裸 git reset --hard",
    ),

    # ─ 白名单：只读工具 ─
    Rule(
        "allow_readonly_tools",
        "allow",
        _tool_in(("Read", "Grep", "Glob", "WebFetch", "WebSearch", "TodoRead", "NotebookRead")),
        "只读工具",
    ),

    # ─ 白名单：git 只读 ─
    Rule(
        "allow_git_readonly",
        "allow",
        _bash_matches(r"^git\s+(status|log|diff|branch|show|blame|remote\s+-v|config\s+--get|fetch|ls-files|rev-parse)"),
        "git 只读子命令",
    ),

    # ─ 白名单：常见无害诊断 ─
    Rule(
        "allow_diagnostics",
        "allow",
        _bash_matches(r"^(ls|dir|pwd|cd|echo|cat|head|tail|wc|which|where|whoami|hostname|date|uname|node\s+--version|python\s+--version|npm\s+--version|pip\s+list|pip\s+show)"),
        "诊断/版本类命令",
    ),
    Rule(
        "allow_powershell_diagnostics",
        "allow",
        _bash_matches(r"^(Get-(ChildItem|Item|Process|Service|Content|Location|Date|Host)|Select-Object|Where-Object|Measure-Object|Test-Path)"),
        "PowerShell 只读 cmdlet",
    ),

    # ─ 白名单：dry-run / --help ─
    Rule(
        "allow_dry_run",
        "allow",
        _bash_matches(r".*(\s--dry-run\b|\s-n\s|\s--help\b|\s-h\s*$)"),
        "dry-run / help",
    ),

    # ─ 白名单：Python 跑 ProjectOS agent 脚本 ─
    Rule(
        "allow_projectos_agent_scripts",
        "allow",
        _bash_matches(r"^python\s+[\"']?D:[\\/]ClaudeCodeProjects[\\/]_ProjectOS[\\/]agent[\\/]"),
        "ProjectOS agent 自家脚本",
    ),
]


def evaluate(tool_name: str, input_args: dict) -> tuple[Decision, str]:
    """返回 (decision, rule_name|reason)。

    未命中任何规则 → 默认 'ask'。
    """
    for rule in RULES:
        try:
            if rule.matches(tool_name, input_args):
                return rule.decision, rule.name
        except Exception:
            continue
    return "ask", "no_match"


if __name__ == "__main__":
    # 自测
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", write_through=True)

    cases = [
        ("Read", {"file_path": "x.md"}, "allow"),
        ("Grep", {"pattern": "foo"}, "allow"),
        ("Bash", {"command": "git status"}, "allow"),
        ("Bash", {"command": "git push --force origin main"}, "deny"),
        ("Bash", {"command": "rm -rf D:/"}, "deny"),
        ("Bash", {"command": "rm -rf node_modules"}, "ask"),
        ("Bash", {"command": "git reset --hard"}, "deny"),
        ("Bash", {"command": "git reset --hard HEAD~1"}, "ask"),
        ("Bash", {"command": "ls -la"}, "allow"),
        ("PowerShell", {"command": "Get-ChildItem D:/"}, "allow"),
        ("PowerShell", {"command": "python D:/ClaudeCodeProjects/_ProjectOS/agent/project_agent.py"}, "allow"),
        ("Bash", {"command": "npm install"}, "ask"),
        ("Write", {"file_path": "x.md", "content": "hi"}, "ask"),
        ("Edit", {"file_path": "x.md"}, "ask"),
    ]
    for tool, inp, expected in cases:
        got, rule = evaluate(tool, inp)
        mark = "✅" if got == expected else "❌"
        cmd_preview = (inp.get("command") or inp.get("file_path") or "")[:50]
        print(f"  {mark} {tool}({cmd_preview!r}) → {got} [{rule}] (expected {expected})")
