"""
飞书交互卡片模板（纯函数，返回 dict）

参考 Ceeon/claude-channel-feishu server.ts:475-509 的卡片结构。
所有函数返回飞书 interactive 卡片的 content dict，由调用方 json.dumps 后
通过 lark-cli 或 lark-sdk 的 im.message.create 发送（msg_type='interactive'）。

按钮 value 约定：
  {"action": "allow"|"deny"|"more"|"all_in"|"watch"|"kill", "request_id": "..."}
card.action.trigger 回调取 event.action.value 反查 pending 事件。
"""
from __future__ import annotations

from typing import Any


# ─── Permission Card (can_use_tool 拦截 → 飞书按钮) ──────────────────────────

def build_permission_card(
    tool_name: str,
    input_preview: str,
    request_id: str,
    description: str = "",
) -> dict[str, Any]:
    """工具权限请求卡片。Allow/Deny/See more 三按钮。

    Args:
        tool_name: 工具名（Bash/Read/Write/...）
        input_preview: 入参摘要（建议 ≤200 字符，长内容截断后加 "..."）
        request_id: SDK can_use_tool 的请求 id，回调时回填
        description: 可选，工具用途说明
    """
    body = f"Tool: {tool_name}"
    if description:
        body += f"\nDescription: {description}"
    body += f"\n\nInput:\n{input_preview}"

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"🔐 Permission: {tool_name}"},
            "template": "orange",
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "plain_text", "content": body},
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "✅ Allow"},
                        "type": "primary",
                        "value": {"action": "allow", "request_id": request_id},
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "❌ Deny"},
                        "type": "danger",
                        "value": {"action": "deny", "request_id": request_id},
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "See more"},
                        "value": {"action": "more", "request_id": request_id},
                    },
                ],
            },
        ],
    }


def build_permission_resolved_card(
    tool_name: str,
    decision: str,  # "allow" | "deny" | "timeout"
    request_id: str,
) -> dict[str, Any]:
    """权限请求被点过之后用于替换原卡片的"已处理"态。"""
    label, template = {
        "allow": ("✅ 已批准", "green"),
        "deny": ("❌ 已拒绝", "red"),
        "timeout": ("⏰ 已超时（默认拒绝）", "grey"),
    }.get(decision, ("· 已处理", "grey"))

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{label}: {tool_name}"},
            "template": template,
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "plain_text", "content": f"request_id: {request_id}"},
            }
        ],
    }


# ─── Morning Report Card (每日晨报 → 每个项目一张) ──────────────────────────

def build_morning_report_card(
    project_name: str,
    status: str,           # 'active' | 'paused' | 'kill_candidate' | ...
    mva_day: int | None,   # 当前在 72h MVA 哪一天
    last_active: str,      # ISO 日期字符串
    summary: str,          # 一句话进展
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    """单项目晨报卡片，附 All-in/Watch/Kill 三按钮。

    按钮回调通过 card.action.trigger，value.action ∈ {all_in, watch, kill}，
    value.project = project_name 由 router 路由到 feishu_sync 的状态更新。
    """
    template = {
        "active": "blue",
        "paused": "grey",
        "kill_candidate": "red",
    }.get(status, "blue")

    mva_line = f"MVA Day {mva_day}/3" if mva_day else "MVA 未启动"
    body = (
        f"**{project_name}**\n"
        f"状态: {status} · {mva_line}\n"
        f"最后活动: {last_active}\n\n"
        f"{summary}"
    )
    if blockers:
        body += "\n\n卡点:\n" + "\n".join(f"- {b}" for b in blockers)

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"📊 {project_name}"},
            "template": template,
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": body},
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "🚀 All-in"},
                        "type": "primary",
                        "value": {"action": "all_in", "project": project_name},
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "👀 Watch"},
                        "value": {"action": "watch", "project": project_name},
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "🪦 Kill"},
                        "type": "danger",
                        "value": {"action": "kill", "project": project_name},
                    },
                ],
            },
        ],
    }


# ─── Status Card (任务执行流式更新) ─────────────────────────────────────────

def build_status_card(
    title: str,
    body: str,
    template: str = "blue",
    footer: str | None = None,
) -> dict[str, Any]:
    """通用状态卡片，用于 SDK 执行过程中的进度流式更新。

    调用方持有 message_id 后用 im.message.patch 更新 content 即可。
    """
    elements: list[dict[str, Any]] = [
        {"tag": "div", "text": {"tag": "lark_md", "content": body}},
    ]
    if footer:
        elements.append({"tag": "hr"})
        elements.append(
            {
                "tag": "note",
                "elements": [{"tag": "plain_text", "content": footer}],
            }
        )

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": template,
        },
        "elements": elements,
    }


# ─── 截断辅助 ────────────────────────────────────────────────────────────────

def truncate_preview(s: str, limit: int = 200) -> str:
    if s is None:
        return ""
    if len(s) <= limit:
        return s
    return s[:limit] + f"... (truncated, total {len(s)} chars)"


if __name__ == "__main__":
    # 自测：dump 三种卡片
    import io
    import json
    import sys

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", write_through=True)

    print("--- permission ---")
    print(json.dumps(
        build_permission_card("Bash", "echo hello > test.txt", "req_abc123", "Run shell command"),
        ensure_ascii=False, indent=2,
    ))
    print("\n--- morning ---")
    print(json.dumps(
        build_morning_report_card(
            "NuclearPowerAI", "active", 2, "2026-06-07",
            "MVA Day2 验证完成，待 Day3 实施", ["缺第三方 API"],
        ),
        ensure_ascii=False, indent=2,
    ))
    print("\n--- resolved ---")
    print(json.dumps(
        build_permission_resolved_card("Bash", "allow", "req_abc123"),
        ensure_ascii=False, indent=2,
    ))
