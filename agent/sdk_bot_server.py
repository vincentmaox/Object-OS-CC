#!/usr/bin/env python3
"""
sdk_bot_server.py — 方案D：claude-agent-sdk + 飞书 Bot 混合服务

替换 cc_bot_server.py 的 subprocess claude -p 路线，接入 SDK 异步 session，
并在 can_use_tool 中走飞书交互卡片做权限中继。

架构：
  Main Thread (asyncio loop):
    ClaudeSDKClient.query() → can_use_tool
                                → router.register() + send_interactive_card()
                                → await_decision() → Allow/Deny
    on_message (dispatched via run_coroutine_threadsafe)

  Lark Worker Thread:
    ws.Client.start() — 管 WebSocket 长连
      on_message → run_coroutine_threadsafe(handle_message)
      card.action.trigger → router.handle_card_action()（threadsafe）
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, Optional

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    PatchMessageRequest,
    PatchMessageRequestBody,
    GetMessageResourceRequest,
)
from lark_oapi.event.dispatcher_handler import EventDispatcherHandlerBuilder

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    PermissionResultAllow,
    PermissionResultDeny,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from feishu_sync import FeishuClient
from feishu_cards import (
    build_permission_card,
    truncate_preview,
    build_status_card,
)
from feishu_card_router import router
from permission_rules import evaluate as evaluate_permission

# ─── Config ──────────────────────────────────────────────────────────────────

WORKDIR = Path(r"D:\ClaudeCodeProjects\_ProjectOS")
ENV_FILE = WORKDIR / "agent" / "cc_bot.env"


from env_loader import load_all

load_all(ENV_FILE)

APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
ALLOWED_OPEN_IDS = set(filter(None, os.environ.get("FEISHU_ALLOWED_OPEN_IDS", "").split(",")))
SDK_TIMEOUT = 300  # 单次 SDK 调用最大等待秒数
PERMISSION_TIMEOUT = 120  # 权限卡片等待用户点击超时
LOG_FILE = WORKDIR / "agent" / "cc_bot.log"
CONTEXT_FILE = WORKDIR / "agent" / "cc_bot_context.json"
PROCESSED_IDS: set[str] = set()
CHAT_CONTEXTS: dict[str, deque[dict[str, str]]] = defaultdict(lambda: deque(maxlen=16))

# Inbox 目录（飞书图片/文件/富文本落盘）
INBOX_ROOT = WORKDIR / "agent" / "inbox"
INBOX_IMAGES = INBOX_ROOT / "images"
INBOX_FILES = INBOX_ROOT / "files"
INBOX_TEXTS = INBOX_ROOT / "texts"
for _d in (INBOX_IMAGES, INBOX_FILES, INBOX_TEXTS):
    _d.mkdir(parents=True, exist_ok=True)

# ─── Logging ─────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ─── Context ─────────────────────────────────────────────────────────────────

def load_contexts() -> None:
    if not CONTEXT_FILE.exists():
        return
    try:
        data = json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
        for chat_id, turns in data.items():
            CHAT_CONTEXTS[chat_id] = deque(turns[-16:], maxlen=16)
        log(f"[上下文] 已加载 {len(data)} 个会话")
    except Exception as e:
        log(f"[上下文] 加载失败: {e}")


def save_contexts() -> None:
    try:
        data = {chat_id: list(turns) for chat_id, turns in CHAT_CONTEXTS.items()}
        CONTEXT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log(f"[上下文] 保存失败: {e}")


def add_context(chat_id: str, role: str, content: str) -> None:
    CHAT_CONTEXTS[chat_id].append({"role": role, "content": content[-4000:]})
    save_contexts()


def build_prompt(chat_id: str, text: str) -> str:
    turns = list(CHAT_CONTEXTS[chat_id])
    lines = [
        "你是用户通过飞书联系的本机 Claude Code 助手。",
        "你在 D:\\ClaudeCodeProjects\\_ProjectOS 工作目录中运行。",
        "下面是最近几轮飞书对话上下文；回答当前用户消息时要参考这些上下文，尤其要知道自己上一轮回复了什么。",
        "",
        "# 思考池协议（重要）",
        "用户可能会发\"我有个想法 / 我有个思考 / 我在想 / 突然想到\"等开头的消息，描述对某个项目的新点子。",
        "**这种情况你必须做三件事**：",
        "1. 反问确认项目名（registry 里的真实项目名，模糊匹配后给出候选）",
        "2. 反问是否要记入思考池",
        "3. 用户确认后，**追加一行到 D:\\ClaudeCodeProjects\\_ProjectOS\\thoughts\\inbox.md**，格式：",
        "   `[当前 ISO 时间戳] [项目名] 用户原话浓缩`",
        "   追加位置：在 `<!-- BOT_APPEND_BELOW_THIS_LINE -->` 注释行下面。",
        "已知项目名（从 registry.json）：ai-router-48h, NuclearPowerAI, docreview-ai, disk-manager, obsidian manager, ValveDrawing-Data-Review, TokenChrono(已归档), PhysicsAI-Research(已归档), _ProjectOS",
        "如果用户的项目指代很明确（如\"docreview\"），直接确认；如果模糊（如\"那个评审工具\"），列 2-3 个候选让用户选。",
        "**禁止**：未经用户确认就写文件。",
        "",
    ]
    if turns:
        lines.append("# 最近对话")
        for turn in turns[-12:]:
            role = "用户" if turn["role"] == "user" else "助手"
            lines.append(f"{role}: {turn['content']}")
        lines.append("")
    lines.extend(["# 当前用户消息", text])
    return "\n".join(lines)


# ─── Feishu Send ─────────────────────────────────────────────────────────────

class FeishuSender:
    """轻量封装：文本消息走 lark-oapi SDK，卡片消息走 FeishuClient（node 直调）。"""

    def __init__(self, lark_client):
        self._lark = lark_client
        self._feishu = FeishuClient()

    def send_text(self, open_id: str, text: str) -> bool:
        CHUNK = 4000
        chunks = [text[i : i + CHUNK] for i in range(0, len(text), CHUNK)] or [""]
        ok_all = True
        for i, chunk in enumerate(chunks):
            prefix = f"[{i+1}/{len(chunks)}]\n" if len(chunks) > 1 else ""
            content = json.dumps({"text": prefix + chunk})
            req = (
                CreateMessageRequest.builder()
                .receive_id_type("open_id")
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(open_id)
                    .msg_type("text")
                    .content(content)
                    .build()
                )
                .build()
            )
            try:
                resp = self._lark.im.v1.message.create(req)
                if not resp.success():
                    log(f"[send 失败] code={resp.code} msg={resp.msg}")
                    ok_all = False
            except Exception as e:
                log(f"[send 异常] {e}")
                ok_all = False
        return ok_all

    def send_card(self, open_id: str, card: dict) -> dict:
        """返回 lark-cli 响应（含 message_id）。"""
        return self._feishu.send_interactive_card(open_id, card)

    def send_status(self, open_id: str, title: str, body: str, template: str = "blue") -> dict:
        return self._feishu.send_interactive_card(
            open_id, build_status_card(title, body, template=template)
        )

    def patch_card(self, message_id: str, card: dict) -> bool:
        """更新已发送的交互卡片内容（用于流式进度更新）。"""
        content = json.dumps(card, ensure_ascii=False)
        req = (
            PatchMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                PatchMessageRequestBody.builder()
                .content(content)
                .build()
            )
            .build()
        )
        try:
            resp = self._lark.im.v1.message.patch(req)
            return resp.success()
        except Exception as e:
            log(f"[patch_card 异常] {e}")
            return False

    def download_resource(
        self, message_id: str, file_key: str, resource_type: str = "file"
    ) -> Optional[tuple[bytes, str]]:
        """下载飞书消息中的图片/文件资源。

        resource_type: "image" 或 "file"
        返回 (bytes, file_name) 或 None（失败）。
        """
        req = (
            GetMessageResourceRequest.builder()
            .message_id(message_id)
            .file_key(file_key)
            .type(resource_type)
            .build()
        )
        try:
            resp = self._lark.im.v1.message_resource.get(req)
            if not resp.success():
                log(f"[下载失败] code={resp.code} msg={resp.msg} key={file_key}")
                return None
            # resp.file 是 IO[bytes]，resp.file_name 是文件名
            data = resp.file.read() if resp.file else b""
            name = resp.file_name or file_key
            return (data, name)
        except Exception as e:
            log(f"[下载异常] {e} key={file_key}")
            return None


def save_to_inbox(
    folder: Path, open_id: str, filename: str, data: bytes
) -> Path:
    """落盘到 inbox。文件名加时间戳 + open_id 短哈希前缀避免冲突。"""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    short_id = (open_id or "anon")[-8:]
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    out_path = folder / f"{ts}_{short_id}_{safe_name}"
    out_path.write_bytes(data)
    return out_path


def list_inbox(limit: int = 20) -> str:
    """列出 inbox 最近 N 条。"""
    items: list[tuple[float, Path, str]] = []
    for cat, folder in [("img", INBOX_IMAGES), ("file", INBOX_FILES), ("text", INBOX_TEXTS)]:
        for p in folder.iterdir():
            if p.is_file():
                items.append((p.stat().st_mtime, p, cat))
    items.sort(key=lambda x: -x[0])
    if not items:
        return "📭 Inbox 为空"
    lines = [f"📬 Inbox 最近 {min(limit, len(items))} 条："]
    for mt, p, cat in items[:limit]:
        ts = datetime.fromtimestamp(mt).strftime("%m-%d %H:%M")
        size_kb = p.stat().st_size / 1024
        lines.append(f"  [{cat}] {ts} {p.name} ({size_kb:.1f}KB)")
    return "\n".join(lines)


# ─── SDK Permission Callback ─────────────────────────────────────────────────

def make_permission_callback(
    sender: FeishuSender,
    open_id: str,
) -> Callable[[str, dict, object], Awaitable]:
    """闭包生成 can_use_tool 回调，捕获当前用户 open_id。

    在 SDK 的 can_use_tool 内部:
    1. 注册 pending → 2. 发权限卡片 → 3. await 用户点击 → 4. 返回 Allow/Deny
    """

    async def callback(tool_name: str, input_args: dict, _ctx) -> object:
        # 1. 先过规则白名单/黑名单
        decision, rule = evaluate_permission(tool_name, input_args)
        if decision == "allow":
            cmd_preview = (input_args.get("command") or input_args.get("file_path") or "")[:80]
            log(f"[权限·自动] Allow {tool_name}({cmd_preview!r}) rule={rule}")
            return PermissionResultAllow()
        if decision == "deny":
            cmd_preview = (input_args.get("command") or input_args.get("file_path") or "")[:80]
            log(f"[权限·自动] Deny  {tool_name}({cmd_preview!r}) rule={rule}")
            sender.send_text(
                open_id,
                f"🚫 自动拒绝: {tool_name}\n规则: {rule}\n输入: {cmd_preview}",
            )
            return PermissionResultDeny(message=f"被规则拒绝: {rule}")

        # 2. 需问用户 → 走卡片
        req_id = f"req_{uuid.uuid4().hex[:8]}"
        inp = json.dumps(input_args, ensure_ascii=False, indent=1)
        preview = truncate_preview(inp, 400)

        log(f"[权限·询问] {open_id} tool={tool_name} req={req_id}")

        p = router.register(req_id, tool_name, open_id)
        card = build_permission_card(tool_name, preview, req_id)
        try:
            resp = sender.send_card(open_id, card)
            msg_id = (resp.get("data") or {}).get("message_id")
            if msg_id:
                p.message_id = msg_id
        except Exception as e:
            log(f"[权限] 卡片发送失败: {e}")
            router.cleanup(req_id)
            return PermissionResultDeny()

        decision_str = await router.await_decision(req_id, timeout=PERMISSION_TIMEOUT)
        router.cleanup(req_id)

        if decision_str == "allow":
            log(f"[权限] {req_id} → Allow")
            return PermissionResultAllow()
        else:
            log(f"[权限] {req_id} → {'Deny' if decision_str == 'deny' else 'Timeout'}")
            return PermissionResultDeny()

    return callback


# ─── Message Handler ─────────────────────────────────────────────────────────

STREAM_UPDATE_INTERVAL = 5  # 流式进度卡片更新间隔（秒）

async def handle_message(
    sender: FeishuSender,
    open_id: str,
    chat_id: str,
    text: str,
    msg_id: str,
) -> None:
    """处理一条飞书消息：SDK session → 流式收集 → 回复。"""
    log(f"[SDK 启动] msg={msg_id} text={text[:80]}")

    # 发送"处理中"状态卡片，保存 message_id 用于后续 patch
    status_resp = sender.send_status(
        open_id,
        "🛠 处理中",
        f"**你：** {text[:200]}\n**状态：** 正在启动 SDK 会话…",
        "blue",
    )
    status_msg_id = (status_resp.get("data") or {}).get("message_id")

    prompt = build_prompt(chat_id, text)
    options = ClaudeAgentOptions(
        can_use_tool=make_permission_callback(sender, open_id),
        permission_mode="default",
        setting_sources=[],
        max_turns=20,
        cwd=str(WORKDIR),
        env={
            k: v for k, v in os.environ.items()
            if k.startswith("ANTHROPIC_") or k in ("PATH", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOME", "TEMP", "TMP", "SystemRoot", "ProgramFiles", "ProgramFiles(x86)")
        },
    )

    text_parts: list[str] = []
    tool_count = 0
    t0 = time.time()
    last_update = t0

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            text_parts.append(block.text)
                        elif isinstance(block, ToolUseBlock):
                            tool_count += 1
                            log(f"[SDK 工具] {block.name} input_keys={list(block.input.keys())}")

                    # 流式进度：每 N 秒 patch 一次状态卡片
                    now = time.time()
                    if status_msg_id and (now - last_update) >= STREAM_UPDATE_INTERVAL:
                        elapsed_s = now - t0
                        partial = "".join(text_parts)
                        preview = partial[-500:] if len(partial) > 500 else partial
                        card = build_status_card(
                            "🛠 生成中",
                            f"**耗时：** {elapsed_s:.0f}s | **工具调用：** {tool_count} 次\n\n{preview}…",
                            "turquoise",
                        )
                        sender.patch_card(status_msg_id, card)
                        last_update = now

                elif isinstance(message, ResultMessage):
                    cost_s = f"turns={message.num_turns} cost=${message.total_cost_usd or 0:.4f}"
                    elapsed = time.time() - t0
                    log(f"[SDK 完成] {cost_s} elapsed={elapsed:.1f}s")
    except Exception as e:
        elapsed = time.time() - t0
        log(f"[SDK 异常] {e}")
        # 更新状态卡片为失败
        if status_msg_id:
            sender.patch_card(status_msg_id, build_status_card(
                "❌ 异常", f"SDK 异常（{elapsed:.0f}s）: {e}", "red",
            ))
        reply = f"❌ SDK 异常（{elapsed:.0f}s）: {e}"
        sender.send_text(open_id, reply)
        add_context(chat_id, "assistant", reply)
        return

    reply = "".join(text_parts).strip() or "(SDK 无文本返回)"
    elapsed = time.time() - t0

    # 更新状态卡片为完成
    if status_msg_id:
        sender.patch_card(status_msg_id, build_status_card(
            "✅ 完成",
            f"**耗时：** {elapsed:.1f}s | **工具调用：** {tool_count} 次\n**回复长度：** {len(reply)} 字",
            "green",
        ))

    # 发送回复
    header = f"✅ 完成（{elapsed:.1f}s）\n\n" if elapsed < 300 else f"⚠️ 长耗时（{elapsed:.1f}s）\n\n"
    full = header + reply

    # 分片发送
    sender.send_text(open_id, full)
    add_context(chat_id, "assistant", reply)
    log(f"[回复] msg={msg_id} len={len(full)}")


# ─── Lark Callback ───────────────────────────────────────────────────────────

def on_message(data, sender: FeishuSender, loop: asyncio.AbstractEventLoop) -> None:
    """注册到 lark 的 im.message.receive_v1。工作在 lark worker 线程。"""
    try:
        msg = data.event.message
        sender_obj = data.event.sender
        msg_id = msg.message_id
        chat_id = msg.chat_id
        open_id = sender_obj.sender_id.open_id if sender_obj and sender_obj.sender_id else None
        chat_type = msg.chat_type
        msg_type = msg.message_type
        content_raw = msg.content
    except Exception as e:
        log(f"[解析失败] {e}")
        return

    if msg_id in PROCESSED_IDS:
        log(f"[去重] msg={msg_id}")
        return
    PROCESSED_IDS.add(msg_id)
    if len(PROCESSED_IDS) > 1000:
        for x in list(PROCESSED_IDS)[:500]:
            PROCESSED_IDS.discard(x)

    if open_id not in ALLOWED_OPEN_IDS:
        log(f"[白名单拒绝] sender={open_id}")
        return

    if chat_type != "p2p":
        log(f"[跳过] 非私聊 chat_type={chat_type}")
        return

    if msg_type != "text":
        # 非文本消息：尝试落盘到 inbox（图片/文件/富文本/post）
        try:
            content_obj = json.loads(content_raw or "{}")
        except Exception:
            content_obj = {}
        saved_paths: list[Path] = []

        try:
            if msg_type == "image":
                image_key = content_obj.get("image_key")
                if image_key:
                    res = sender.download_resource(msg_id, image_key, "image")
                    if res:
                        data, name = res
                        # 飞书图片名常为空，自动补 .png
                        if not name or "." not in name:
                            name = f"{image_key}.png"
                        p = save_to_inbox(INBOX_IMAGES, open_id, name, data)
                        saved_paths.append(p)

            elif msg_type == "file":
                file_key = content_obj.get("file_key")
                file_name = content_obj.get("file_name") or (file_key or "unknown")
                if file_key:
                    res = sender.download_resource(msg_id, file_key, "file")
                    if res:
                        data, name = res
                        # 优先用 content 里的 file_name
                        p = save_to_inbox(INBOX_FILES, open_id, file_name or name, data)
                        saved_paths.append(p)

            elif msg_type == "post":
                # 富文本：先把 JSON 落盘，再扫描内嵌的 image_key/file_key
                ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                short_id = (open_id or "anon")[-8:]
                post_path = INBOX_TEXTS / f"{ts}_{short_id}_{msg_id}.json"
                post_path.write_text(
                    json.dumps(content_obj, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                saved_paths.append(post_path)
                # 富文本中可能嵌的 img/file 元素
                def _walk(node):
                    if isinstance(node, dict):
                        tag = node.get("tag")
                        if tag == "img" and node.get("image_key"):
                            res = sender.download_resource(msg_id, node["image_key"], "image")
                            if res:
                                data, name = res
                                if not name or "." not in name:
                                    name = f"{node['image_key']}.png"
                                saved_paths.append(save_to_inbox(INBOX_IMAGES, open_id, name, data))
                        elif tag in ("file", "media") and node.get("file_key"):
                            rtype = "file" if tag == "file" else "file"
                            res = sender.download_resource(msg_id, node["file_key"], rtype)
                            if res:
                                data, name = res
                                saved_paths.append(save_to_inbox(INBOX_FILES, open_id, name, data))
                        for v in node.values():
                            _walk(v)
                    elif isinstance(node, list):
                        for v in node:
                            _walk(v)
                _walk(content_obj)

            elif msg_type in ("audio", "media", "sticker"):
                # 这几类暂统一当 file 试一下
                key = content_obj.get("file_key") or content_obj.get("image_key")
                if key:
                    res = sender.download_resource(msg_id, key, "file")
                    if res:
                        data, name = res
                        if not name or "." not in name:
                            ext = {"audio": ".opus", "media": ".mp4", "sticker": ".png"}.get(msg_type, "")
                            name = f"{key}{ext}"
                        p = save_to_inbox(INBOX_FILES, open_id, name, data)
                        saved_paths.append(p)
        except Exception as e:
            log(f"[资源处理异常] msg_type={msg_type} err={e}")

        if saved_paths:
            lines = [f"📥 已收到 {msg_type}，落盘 {len(saved_paths)} 个文件："]
            for p in saved_paths:
                rel = p.relative_to(WORKDIR)
                lines.append(f"  • {rel}")
            sender.send_text(open_id, "\n".join(lines))
            log(f"[资源落盘] msg={msg_id} type={msg_type} count={len(saved_paths)}")
        else:
            sender.send_text(open_id, f"⚠️ 收到 {msg_type} 但未提取到资源（content={truncate_preview(content_raw or '', 200)}）")
            log(f"[资源落盘失败] msg={msg_id} type={msg_type} content={content_raw[:200] if content_raw else ''}")
        return

    try:
        text = json.loads(content_raw).get("text", "").strip()
    except Exception:
        text = ""
    if not text:
        sender.send_text(open_id, "消息为空，请发文本指令")
        return

    # ─── 内置指令 ────────────────────────────────────────────────
    cmd = text.strip()
    if cmd in ("/reload", "/重载"):
        try:
            from env_loader import load_all
            load_all(ENV_FILE)
            token_present = bool(os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY"))
            base_url = os.environ.get("ANTHROPIC_BASE_URL", "(未设)")
            sender.send_text(
                open_id,
                f"🔄 已重载环境变量\n"
                f"  ANTHROPIC token: {'✅ 已加载' if token_present else '❌ 缺失'}\n"
                f"  ANTHROPIC_BASE_URL: {base_url}\n"
                f"  注意：当前进行中的 SDK session 不受影响，下一条消息生效",
            )
            log(f"[/reload] {open_id} token_present={token_present}")
        except Exception as e:
            sender.send_text(open_id, f"❌ /reload 失败: {e}")
        return

    if cmd in ("/list-inbox", "/inbox", "/收件箱"):
        sender.send_text(open_id, list_inbox(limit=20))
        return

    # 命令通道：y/n 解 pending（卡片之外的双通道）
    hit = router.resolve_by_text(text)
    if hit:
        req_id, decision = hit
        log(f"[命令通道] {open_id} → {decision} for {req_id}")
        sender.send_text(open_id, f"✅ 已{('批准' if decision=='allow' else '拒绝')} {req_id}（命令通道）")
        return

    log(f"[收到] msg={msg_id} chat={chat_id} from={open_id}")
    sender.send_text(open_id, f"📥 收到，正在处理…\n> {text[:100]}")
    add_context(chat_id, "user", text)

    # 派发到 asyncio 主循环
    asyncio.run_coroutine_threadsafe(
        handle_message(sender, open_id, chat_id, text, msg_id),
        loop,
    )


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not APP_ID or not APP_SECRET:
        raise RuntimeError(f"FEISHU_APP_ID / FEISHU_APP_SECRET 未配置，请检查 {ENV_FILE}")
    if not ALLOWED_OPEN_IDS:
        raise RuntimeError(f"FEISHU_ALLOWED_OPEN_IDS 未配置，请检查 {ENV_FILE}")

    load_contexts()

    # 启动 asyncio 事件循环（主线程）
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    router.bind_loop(loop)  # 让 router 的 threadsafe set 定位到正确的 loop

    # 初始化 lark client 和 sender
    _lark_client = lark.Client.builder().app_id(APP_ID).app_secret(APP_SECRET).build()
    sender = FeishuSender(_lark_client)

    # 构建事件处理器 — 用 closures 传 sender/loop
    def make_text_handler(s, l):
        def handler(data):
            on_message(data, s, l)
        return handler

    handler_builder: EventDispatcherHandlerBuilder = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(make_text_handler(sender, loop))
        .register_p2_card_action_trigger(router.handle_card_action)
    )

    ws_client = lark.ws.Client(
        APP_ID,
        APP_SECRET,
        event_handler=handler_builder.build(),
        log_level=lark.LogLevel.INFO,
        auto_reconnect=True,
    )

    log(f"[启动] sdk_bot_server.py (方案D)")
    log(f"[启动] APP_ID={APP_ID}")
    log(f"[启动] WORKDIR={WORKDIR}")
    log(f"[启动] 白名单={ALLOWED_OPEN_IDS}")
    log(f"[启动] 权限超时={PERMISSION_TIMEOUT}s")
    log(f"[启动] 等待飞书消息...")

    # ws.Client.start() 是阻塞的，跑在后台线程
    import threading
    ws_thread = threading.Thread(target=ws_client.start, daemon=True)
    ws_thread.start()

    # 主线程跑 asyncio 循环（SDK session、await_decision）
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        log("[关闭] 收到 Ctrl+C，退出")
    finally:
        loop.close()


if __name__ == "__main__":
    main()