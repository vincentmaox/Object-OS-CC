"""
env_loader.py — 共享环境变量加载器

加载顺序（后者覆盖前者）：
1. cc_bot.env（飞书凭据 + ANTHROPIC fallback）
2. ~/.claude/settings.json 的 env 字段（CC Switch 实时值，优先级最高）

这样 CC Switch 切换模型/token 后，定时任务下次运行自动生效。
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def load_env_file(path: Path) -> None:
    """从 .env 文件加载环境变量（不覆盖已有值）。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if value.strip():
            os.environ.setdefault(key.strip(), value.strip())


def load_cc_switch_env() -> None:
    """从 ~/.claude/settings.json 的 env 字段覆盖 ANTHROPIC_* 变量。

    CC Switch 修改的就是这个文件，所以这里取到的是最新值。
    只覆盖 ANTHROPIC_ 开头的 key，避免影响其他环境变量。
    """
    settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.exists():
        return
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        env = data.get("env", {})
        for key, value in env.items():
            if key.startswith("ANTHROPIC_") and value:
                os.environ[key] = value
    except Exception:
        pass


def load_all(env_file: Path | None = None) -> None:
    """完整加载：先 .env fallback，再 CC Switch 覆盖。"""
    if env_file:
        load_env_file(env_file)
    load_cc_switch_env()
