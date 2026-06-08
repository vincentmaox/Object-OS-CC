"""
飞书 card.action.trigger 事件路由 + pending permissions 注册表。

设计思路：
  SDK can_use_tool(req_id) ─┐
                            │ 1. 创建 asyncio.Event 入册
                            │ 2. 发卡片到飞书
                            └─> await Event.wait(timeout)
                                  ↑
                                  │ 路由模块在事件循环中 set_result(req_id, decision)
                                  │
  飞书按钮点击 → bot 收到 card.action.trigger
              → router(P2CardActionTrigger) 解析 action.value
              → set_result(req_id, decision)
              → 返回替换卡片让 UI 立即响应

关键约束：
- bot 服务跑在自己的事件循环里（asyncio.run_until_complete or async main）
- lark 回调可能在另一个线程里（lark ws client 的 worker pool）
  → 不能直接 event.set()，必须 loop.call_soon_threadsafe(event.set)
- pending 表用全局 dict + asyncio.Lock 保护，足够这种低频场景
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from feishu_cards import build_permission_resolved_card


@dataclass
class PendingPermission:
    request_id: str
    tool_name: str
    open_id: str                  # 发卡片的目标用户
    message_id: Optional[str]     # 用于点完按钮后 patch 卡片
    event: asyncio.Event = field(default_factory=asyncio.Event)
    decision: Optional[str] = None  # 'allow' | 'deny' | 'timeout'
    created_at: float = field(default_factory=time.time)


class PermissionRouter:
    """单例式 pending 表 + card.action.trigger 路由。

    用法（在 sdk_bot_server.py 里）：

        router = PermissionRouter()
        router.bind_loop(asyncio.get_event_loop())

        # 在 lark handler 注册：
        handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_card_action_trigger(router.handle_card_action)
            ...
        )

        # SDK 的 can_use_tool 里：
        decision = await router.await_decision(req_id, tool, open_id, message_id, timeout=120)
    """

    def __init__(self) -> None:
        self._pending: dict[str, PendingPermission] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """绑定 bot 主事件循环。lark 回调在 worker 线程里，需要 thread-safe 派发。"""
        self._loop = loop

    def register(
        self,
        request_id: str,
        tool_name: str,
        open_id: str,
        message_id: Optional[str] = None,
    ) -> PendingPermission:
        """SDK 侧调：登记一个等待中的权限请求。"""
        if request_id in self._pending:
            raise ValueError(f"duplicate request_id: {request_id}")
        p = PendingPermission(
            request_id=request_id,
            tool_name=tool_name,
            open_id=open_id,
            message_id=message_id,
        )
        self._pending[request_id] = p
        return p

    async def await_decision(
        self,
        request_id: str,
        timeout: float = 120.0,
    ) -> str:
        """SDK 侧调：阻塞等待用户点击。

        返回 'allow' / 'deny' / 'timeout'。超时后默认 'timeout'（调用方决定如何映射成 Allow/Deny）。
        """
        p = self._pending.get(request_id)
        if p is None:
            raise KeyError(f"no pending permission for {request_id}")
        try:
            await asyncio.wait_for(p.event.wait(), timeout=timeout)
            return p.decision or "timeout"
        except asyncio.TimeoutError:
            p.decision = "timeout"
            return "timeout"
        finally:
            # 让 router 在响应卡片里仍能读 tool_name / open_id
            # 真正回收交给 cleanup（可由调用方在 await 之后调）
            pass

    def cleanup(self, request_id: str) -> None:
        self._pending.pop(request_id, None)

    # ─── 命令通道（文本消息也能解 pending）───────────────────────────────

    def list_pending(self) -> list[PendingPermission]:
        return list(self._pending.values())

    def resolve_by_text(self, text: str) -> Optional[tuple[str, str]]:
        """解析"y"/"n"/"y req_xxx"/"n req_xxx"等文本指令，命中则解 pending。

        语法：
          y / yes / 同意 / 允许   → allow
          n / no  / 拒绝 / 否     → deny
          可选附加 req_xxx 指定（多个 pending 时必须带）。

        返回 (req_id, decision) 命中；否则 None。
        """
        import re
        s = text.strip().lower()
        m = re.match(r"^(y|yes|n|no|同意|允许|拒绝|否)\b\s*(req_[\w]+)?", s, re.IGNORECASE)
        if not m:
            return None
        verb, req_id = m.group(1), m.group(2)
        decision = "allow" if verb in ("y", "yes", "同意", "允许") else "deny"

        if req_id:
            p = self._pending.get(req_id)
        else:
            pending = list(self._pending.values())
            if len(pending) != 1:
                return None  # 0 or >1 pending → 模糊，不响应
            p = pending[0]

        if p is None:
            return None

        p.decision = decision
        if self._loop is None:
            p.event.set()
        else:
            self._loop.call_soon_threadsafe(p.event.set)
        return (p.request_id, decision)

    # ─── lark callback (在 worker 线程里) ───────────────────────────────────

    def handle_card_action(self, event):
        """注册到 lark.EventDispatcherHandler 的 P2CardActionTrigger 回调。

        签名：P2CardActionTrigger -> P2CardActionTriggerResponse | dict | None
        返回 dict 形如 {"toast": {...}, "card": {...}} 让飞书替换原卡片+弹 toast。
        """
        try:
            action = event.event.action
            value = action.value or {}
            req_id = value.get("request_id")
            decision = value.get("action")  # 'allow' | 'deny' | 'more' | ...
            operator_open_id = (
                event.event.operator.open_id
                if event.event.operator
                else None
            )
        except Exception as e:
            return {"toast": {"type": "error", "content": f"事件解析失败: {e}"}}

        # 不是权限卡片（譬如 morning_report 的 All-in/Watch/Kill）→ 暂直接 toast
        if not req_id:
            return self._handle_non_permission_action(decision, value, operator_open_id)

        # 安全校验：权限卡片也只允许白名单用户操作
        if operator_open_id and operator_open_id not in self.ALLOWED_OPEN_IDS:
            return {"toast": {"type": "error", "content": f"无权限操作（open_id: {operator_open_id[:8]}…）"}}

        p = self._pending.get(req_id)
        if p is None:
            return {
                "toast": {
                    "type": "warning",
                    "content": f"该请求已过期或已处理（{req_id[:8]}…）",
                }
            }

        # See more：暂不消耗 pending，只 toast 详情
        if decision == "more":
            return {
                "toast": {
                    "type": "info",
                    "content": f"工具: {p.tool_name}\nrequest_id: {p.request_id}",
                }
            }

        if decision not in ("allow", "deny"):
            return {
                "toast": {
                    "type": "warning",
                    "content": f"未知操作: {decision}",
                }
            }

        # 派发到 SDK 事件循环（lark 回调在另一线程）
        p.decision = decision
        if self._loop is None:
            # 兜底：直接 set，可能在错误线程
            p.event.set()
        else:
            self._loop.call_soon_threadsafe(p.event.set)

        # 同步返回替换卡片
        return {
            "toast": {
                "type": "success" if decision == "allow" else "warning",
                "content": "已批准" if decision == "allow" else "已拒绝",
            },
            "card": {
                "type": "raw",
                "data": build_permission_resolved_card(
                    tool_name=p.tool_name,
                    decision=decision,
                    request_id=p.request_id,
                ),
            },
        }

    ALLOWED_OPEN_IDS = os.environ.get(
        "FEISHU_ALLOWED_OPEN_IDS", "ou_59a5d4b0cc115a66295961a1aec66a9e"
    ).split(",")

    def _handle_non_permission_action(self, action: str, value: dict, operator_open_id):
        """晨报卡片上的 All-in/Watch/Kill 按钮。

        校验操作者 open_id 白名单，调用 feishu_sync.update_project_status 写回
        registry.json，然后返回 toast + 替换卡片显示决策结果。
        """
        from feishu_cards import build_morning_report_card

        # 安全校验：只允许白名单用户操作
        if operator_open_id and operator_open_id not in self.ALLOWED_OPEN_IDS:
            return {"toast": {"type": "error", "content": f"无权限操作（open_id: {operator_open_id[:8]}…）"}}

        project = value.get("project", "?")
        if action not in ("all_in", "watch", "kill"):
            return {"toast": {"type": "warning", "content": f"未知操作: {action}"}}

        # 写回 registry
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent))
            from feishu_sync import ProjectSyncEngine
            engine = ProjectSyncEngine()
            result = engine.update_project_status(project, action)
            if not result.get("ok"):
                return {"toast": {"type": "error", "content": f"写回失败: {result.get('error', '?')}"}}
            new_status = result.get("status", "?")
        except Exception as e:
            return {"toast": {"type": "error", "content": f"写回异常: {e}"}}

        # 返回替换卡片
        label = {"all_in": "🚀 All-in", "watch": "👀 Watch", "kill": "🪦 Kill"}[action]
        template = {"all_in": "green", "watch": "yellow", "kill": "red"}[action]

        resolved_card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"{label}: {project}"},
                "template": template,
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"状态已更新为 **{new_status}**"},
                },
            ],
        }
        return {
            "toast": {"type": "success", "content": f"{label}: {project} → {new_status}"},
            "card": {"type": "raw", "data": resolved_card},
        }


# 模块级单例（导入即用）
router = PermissionRouter()
