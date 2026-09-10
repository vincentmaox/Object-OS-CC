#!/usr/bin/env python3
"""
coding_usage_monitor.py — 三家 coding plan 用量监控 + 飞书预警（v1 2026-09-10）

数据源：
- 智谱: GET open.bigmodel.cn/api/monitor/usage/quota/limit (裸 token, 不带 Bearer)
        → limits[] 含 5h/周窗口 percentage + nextResetTime
- Kimi: GET api.kimi.com/coding/v1/usages (Bearer sk-kimi- key)
        → usage(周) + limits[](5h 窗口)
- 火山: v1 不做 API（需 AK/SK SigV4 签名）；本地 token 近似走 cc-switch.db，
        真值用 CC Switch ≥3.16.4 的 UI（配 IAM AK/SK 后原生支持）
- 本地: cc-switch.db proxy_request_logs 任意窗口聚合（session 日志实时同步）

Key 来源：cc-switch.db providers 表 settings_config（脚本运行时读，绝不打印/落日志）。
预警：任一窗口 ≥80% → 飞书私聊；同 provider+窗口 2 小时去重。

用法:
  python coding_usage_monitor.py --status    # 打印全部状态, 不推送
  python coding_usage_monitor.py             # 常规轮询 + 超阈值推送
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

WORKDIR = Path(r"D:\ClaudeCodeProjects\_ProjectOS")
CC_SWITCH_DB = Path(os.path.expanduser("~/.cc-switch/cc-switch.db"))
STATE_FILE = WORKDIR / "agent" / "usage_monitor_state.json"
LOG_FILE = WORKDIR / "agent" / "usage_monitor.log"

USER_OPEN_ID = "ou_59a5d4b0cc115a66295961a1aec66a9e"
# v0.7.1 快照落盘：hermes-desktop 驾驶舱额度条读取（Rust 侧 read_usage_snapshot）
SNAPSHOT_FILE = WORKDIR / "agent" / "usage_snapshot.json"

ALERT_THRESHOLD = int(os.environ.get("USAGE_ALERT_THRESHOLD", "80"))  # percentage ≥ 此值预警
ALERT_DEDUP_SECONDS = 2 * 3600  # 同 key 2 小时内不重推
HTTP_TIMEOUT = 15

LOG_MAX_BYTES = 2 * 1024 * 1024


def _log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, file=sys.stderr, flush=True)
    try:
        p = LOG_FILE
        if p.exists() and p.stat().st_size > LOG_MAX_BYTES:
            p.write_bytes(p.read_bytes()[-512 * 1024:])
        with open(p, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(s: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        _log(f"[state] save error: {e}")


# === Key 获取（从 cc-switch.db, 不打印任何 key 内容） ===

def _provider_keys() -> dict[str, str]:
    """按 base_url 匹配返回 {'zhipu': key, 'kimi': key}。匹配不到返回空串。"""
    out = {"zhipu": "", "kimi": ""}
    if not CC_SWITCH_DB.exists():
        _log("[keys] cc-switch.db 不存在")
        return out
    try:
        db = sqlite3.connect(f"file:{CC_SWITCH_DB}?mode=ro", uri=True)
        rows = db.execute(
            "SELECT settings_config FROM providers WHERE app_type='claude'"
        ).fetchall()
        for (cfg,) in rows:
            try:
                env = (json.loads(cfg) or {}).get("env", {})
            except Exception:
                continue
            base = (env.get("ANTHROPIC_BASE_URL") or "").lower()
            token = env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY") or ""
            if not token:
                continue
            if ("bigmodel.cn" in base or "z.ai" in base) and not out["zhipu"]:
                out["zhipu"] = token
            elif ("kimi.com" in base or "moonshot" in base) and not out["kimi"]:
                out["kimi"] = token
        db.close()
    except Exception as e:
        _log(f"[keys] db read error: {e}")
    return out


# === 平台查询 ===

def _num(v):
    """宽容数字转换（Kimi 返回字符串数字）。失败返回 None。"""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fmt_reset(v) -> str:
    """重置时间：毫秒/秒时间戳 或 ISO 8601 字符串 或 '3h 43m' 人话。"""
    if not v:
        return "?"
    if isinstance(v, str):
        if "T" in v and "-" in v:  # ISO 8601, e.g. 2026-09-13T11:49:24.974235Z
            try:
                from datetime import datetime as dt
                return dt.fromisoformat(v.replace("Z", "+00:00")).astimezone().strftime("%m-%d %H:%M")
            except Exception:
                pass
        return v  # 已是人话（如 '3h 43m'）
    ts = _num(v)
    if ts is None:
        return str(v)
    if ts > 1e12:  # 毫秒
        ts /= 1000
    return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")


def query_zhipu(token: str) -> list[dict]:
    """智谱: 裸 token 认证。返回 [{'window': '5h'|'周', 'pct': int, 'reset': str}]。"""
    try:
        r = requests.get(
            "https://open.bigmodel.cn/api/monitor/usage/quota/limit",
            headers={"Authorization": token, "Accept-Language": "en-US,en",
                     "Content-Type": "application/json"},
            timeout=HTTP_TIMEOUT,
        )
        data = r.json()
        if data.get("code") != 200:
            _log(f"[zhipu] api code={data.get('code')} msg={str(data.get('msg'))[:80]}")
            return []
        windows = []
        for lim in (data.get("data") or {}).get("limits") or []:
            # 防御解析: 实测 unit=3&number=5 → 5小时, unit=6&number=1 → 每周, TIME_LIMIT → V2月度MCP
            unit, num = lim.get("unit"), lim.get("number")
            if lim.get("type") == "TIME_LIMIT":
                label = "月MCP"
            elif unit == 3 and num == 5:
                label = "5h"
            elif unit == 6 or (num == 7 and unit == 3):
                label = "周"
            else:
                label = f"{num}u{unit}"
            pct = lim.get("percentage")
            if pct is None:
                continue
            windows.append({"window": label, "pct": int(pct),
                            "reset": _fmt_reset(lim.get("nextResetTime"))})
        return windows
    except Exception as e:
        _log(f"[zhipu] error: {e}")
        return []


def query_kimi(token: str) -> list[dict]:
    """Kimi: Bearer sk-kimi- key。usage=周额度, limits[] 含 5h 窗口。"""
    if not token.startswith("sk-kimi-"):
        _log(f"[kimi] key 非 sk-kimi- 前缀 ({token[:3]}***), 跳过 — CC Switch 里配的可能是其他平台 key")
        return []
    try:
        r = requests.get(
            "https://api.kimi.com/coding/v1/usages",
            headers={"Authorization": f"Bearer {token}"},
            timeout=HTTP_TIMEOUT,
        )
        if r.status_code == 404:
            r = requests.get(
                "https://api.kimi.com/coding/v1/usage",
                headers={"Authorization": f"Bearer {token}"},
                timeout=HTTP_TIMEOUT,
            )
        data = r.json()
        windows = []
        usage = data.get("usage") or {}
        limit = _num(usage.get("limit") or usage.get("limit_amount"))
        used = _num(usage.get("used") or usage.get("used_amount"))
        if limit:
            pct = round(100 * (used or 0) / limit)
            windows.append({"window": "周", "pct": pct,
                            "reset": _fmt_reset(usage.get("resetTime") or usage.get("reset_in"))})
        for lim in data.get("limits") or []:
            win = (lim.get("window") or {})
            if win.get("duration") == 300:  # 300 分钟 = 5h
                detail = lim.get("detail") or lim
                limit5 = _num(detail.get("limit") or detail.get("limit_amount"))
                used5 = _num(detail.get("used") or detail.get("used_amount"))
                if limit5:
                    pct = round(100 * (used5 or 0) / limit5)
                    windows.append({"window": "5h", "pct": pct,
                                    "reset": _fmt_reset(detail.get("resetTime") or detail.get("reset_in"))})
        return windows
    except Exception as e:
        _log(f"[kimi] error: {e}")
        return []


# === 本地聚合（cc-switch.db） ===

def local_usage() -> list[str]:
    """本地 token 消耗（任意窗口）, 按 provider 分组近似。"""
    if not CC_SWITCH_DB.exists():
        return []
    try:
        db = sqlite3.connect(f"file:{CC_SWITCH_DB}?mode=ro", uri=True)
        now = time.time()
        lines = []
        for hours, label in ((5, "5h"), (24, "24h"), (7 * 24, "7d")):
            row = db.execute(
                """SELECT count(*), sum(input_tokens+output_tokens+cache_read_tokens+cache_creation_tokens)
                   FROM proxy_request_logs WHERE created_at >= ?""",
                (now - hours * 3600,),
            ).fetchone()
            n, tok = row
            lines.append(f"{label}: {n} 请求 / {(tok or 0)/1e6:.0f}M tokens")
        db.close()
        return lines
    except Exception as e:
        _log(f"[local] error: {e}")
        return []


# === 推送 ===

def push_alert(content: str) -> bool:
    sys.path.insert(0, str(WORKDIR / "agent"))
    try:
        from feishu_sync import FeishuClient
    except Exception as e:
        _log(f"[push] import error: {e}")
        return False
    result = FeishuClient().send_rich_message(
        target=USER_OPEN_ID,
        title=f"⚠️ Coding Plan 额度预警 · {datetime.now().strftime('%H:%M')}",
        content=content,
        target_type="user_id",
    )
    ok = bool(result.get("data"))
    _log(f"[push] {'ok' if ok else 'failed'}")
    return ok


# === 主流程 ===

def main() -> int:
    status_only = "--status" in sys.argv
    _log(f"=== 启动 usage_monitor status_only={status_only} ===")

    keys = _provider_keys()
    report: list[str] = []
    alerts: list[str] = []
    snapshot_providers: list[dict] = []  # 喂 usage_snapshot.json 的结构化数据
    state = _load_state()
    now_ts = time.time()

    for name, token, fn in (("智谱", keys["zhipu"], query_zhipu),
                            ("Kimi", keys["kimi"], query_kimi)):
        if not token:
            report.append(f"**{name}**: (未在 CC Switch 匹配到 key)")
            continue
        windows = fn(token)
        if not windows:
            report.append(f"**{name}**: 查询失败/无数据")
            continue
        snapshot_providers.append({"name": name, "windows": windows})
        parts = [f"**{name}**: " + " | ".join(
            f"{w['window']} {w['pct']}%(重置 {w['reset']})" for w in windows)]
        report.extend(parts)
        for w in windows:
            if w["pct"] >= ALERT_THRESHOLD:
                dedup_key = f"{name}_{w['window']}"
                last = state.get(dedup_key, 0)
                if now_ts - last < ALERT_DEDUP_SECONDS:
                    _log(f"[alert] {dedup_key} {w['pct']}% 已在 2h 内推过, 跳过")
                else:
                    alerts.append(f"**{name}** {w['window']} 窗口已用 **{w['pct']}%**（重置 {w['reset']}）")
                    state[dedup_key] = now_ts

    local = local_usage()
    report.append("\n**本地消耗**（CC Switch 会话统计，全平台合计）:\n" + "\n".join(local))
    report.append("\n**火山**: 真值请在 CC Switch 3.20.2 UI 配 IAM AK/SK 查看（或装官方 ark-cli）")

    # 快照落盘（供 hermes-desktop 额度条读）
    snapshot = {"ts": now_ts, "providers": snapshot_providers, "local_lines": local}
    try:
        SNAPSHOT_FILE.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        _log(f"[snapshot] write error: {e}")

    text = "\n".join(report)
    print(text)
    print()

    if status_only:
        _log("=== status 模式结束 ===")
        return 0
    _save_state(state)
    if alerts:
        body = "额度预警：\n\n" + "\n".join(alerts) + "\n\n建议：切换 CC Switch 到额度充足的供应商，或等窗口重置。\n\n---\n" + text
        push_alert(body)
        _log(f"=== 完成 alerts={len(alerts)} ===")
    else:
        _log("=== 完成 alerts=0 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
