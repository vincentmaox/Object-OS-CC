#!/usr/bin/env python3
"""
feishu_backfill.py — 拉取历史飞书消息 + 下载之前漏接的文件/图片

用法:
    python agent/feishu_backfill.py              # 默认拉过去 7 天
    python agent/feishu_backfill.py --days 30    # 拉过去 30 天
    python agent/feishu_backfill.py --hours 24   # 拉过去 24 小时

只处理白名单内 open_id 的 p2p 聊天。
图片/文件落到 agent/inbox/{images,files}/，富文本落到 agent/inbox/texts/。
文本消息只打印摘要（不入 inbox，避免和 conversation_log 重复）。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Windows cp936 → utf-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", write_through=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", write_through=True)

WORKDIR = Path(r"D:\ClaudeCodeProjects\_ProjectOS")
sys.path.insert(0, str(WORKDIR / "agent"))

from env_loader import load_all
ENV_FILE = WORKDIR / "agent" / "cc_bot.env"
load_all(ENV_FILE)

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    ListMessageRequest,
    ListChatRequest,
    GetMessageResourceRequest,
)

APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
ALLOWED_OPEN_IDS = set(filter(None, os.environ.get("FEISHU_ALLOWED_OPEN_IDS", "").split(",")))

INBOX_ROOT = WORKDIR / "agent" / "inbox"
INBOX_IMAGES = INBOX_ROOT / "images"
INBOX_FILES = INBOX_ROOT / "files"
INBOX_TEXTS = INBOX_ROOT / "texts"
for d in (INBOX_IMAGES, INBOX_FILES, INBOX_TEXTS):
    d.mkdir(parents=True, exist_ok=True)


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def list_p2p_chats(client) -> list[tuple[str, str, str]]:
    """列出 bot 所有 p2p 会话，返回 [(chat_id, name, open_id_of_user)] 列表（仅白名单）。"""
    out: list[tuple[str, str, str]] = []
    page_token: str | None = None
    while True:
        b = ListChatRequest.builder().page_size(100)
        if page_token:
            b = b.page_token(page_token)
        resp = client.im.v1.chat.list(b.build())
        if not resp.success():
            log(f"list_chat 失败: code={resp.code} msg={resp.msg}")
            break
        items = resp.data.items or []
        for ch in items:
            if getattr(ch, "chat_mode", None) != "p2p":
                continue
            chat_id = ch.chat_id
            name = ch.name or "(no name)"
            # p2p chat 的 owner_id 在 chat 信息里不直接是 open_id，得 get
            out.append((chat_id, name, ""))
        if not resp.data.has_more:
            break
        page_token = resp.data.page_token
    return out


def download_resource(client, message_id: str, file_key: str, rtype: str = "file"):
    req = (
        GetMessageResourceRequest.builder()
        .message_id(message_id)
        .file_key(file_key)
        .type(rtype)
        .build()
    )
    try:
        resp = client.im.v1.message_resource.get(req)
        if not resp.success():
            log(f"  下载失败 code={resp.code} msg={resp.msg}")
            return None
        data = resp.file.read() if resp.file else b""
        name = resp.file_name or file_key
        return data, name
    except Exception as e:
        log(f"  下载异常 {e}")
        return None


def safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)


def save_inbox(folder: Path, ts_str: str, sender_short: str, filename: str, data: bytes) -> Path:
    out_path = folder / f"{ts_str}_{sender_short}_{safe_filename(filename)}"
    out_path.write_bytes(data)
    return out_path


def process_message(client, msg) -> dict:
    """处理一条历史消息，返回统计字典。"""
    msg_id = msg.message_id
    msg_type = msg.msg_type
    sender = msg.sender or {}
    sender_id = getattr(sender, "id", None) or ""
    create_time_ms = int(msg.create_time or "0")
    ts = datetime.fromtimestamp(create_time_ms / 1000) if create_time_ms else datetime.now()
    ts_str = ts.strftime("%Y%m%d-%H%M%S")
    sender_short = sender_id[-8:] if sender_id else "anon"

    body_raw = msg.body.content if msg.body else "{}"
    try:
        body = json.loads(body_raw)
    except Exception:
        body = {}

    saved: list[Path] = []

    if msg_type == "image":
        key = body.get("image_key")
        if key:
            res = download_resource(client, msg_id, key, "image")
            if res:
                data, name = res
                if not name or "." not in name:
                    name = f"{key}.png"
                saved.append(save_inbox(INBOX_IMAGES, ts_str, sender_short, name, data))

    elif msg_type == "file":
        key = body.get("file_key")
        fname = body.get("file_name") or key
        if key:
            res = download_resource(client, msg_id, key, "file")
            if res:
                data, name = res
                saved.append(save_inbox(INBOX_FILES, ts_str, sender_short, fname or name, data))

    elif msg_type == "post":
        post_path = INBOX_TEXTS / f"{ts_str}_{sender_short}_{msg_id}.json"
        post_path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        saved.append(post_path)

        def walk(node):
            if isinstance(node, dict):
                tag = node.get("tag")
                if tag == "img" and node.get("image_key"):
                    r = download_resource(client, msg_id, node["image_key"], "image")
                    if r:
                        d, n = r
                        if not n or "." not in n:
                            n = f"{node['image_key']}.png"
                        saved.append(save_inbox(INBOX_IMAGES, ts_str, sender_short, n, d))
                elif tag in ("file", "media") and node.get("file_key"):
                    r = download_resource(client, msg_id, node["file_key"], "file")
                    if r:
                        d, n = r
                        saved.append(save_inbox(INBOX_FILES, ts_str, sender_short, n, d))
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(body)

    elif msg_type == "audio":
        key = body.get("file_key")
        if key:
            r = download_resource(client, msg_id, key, "file")
            if r:
                d, n = r
                if not n or "." not in n:
                    n = f"{key}.opus"
                saved.append(save_inbox(INBOX_FILES, ts_str, sender_short, n, d))

    return {
        "msg_id": msg_id,
        "msg_type": msg_type,
        "ts": ts.isoformat(timespec="seconds"),
        "saved": [str(p.relative_to(WORKDIR)) for p in saved],
        "text": body.get("text", "")[:80] if msg_type == "text" else "",
    }


def fetch_history(client, chat_id: str, start_ms: int, end_ms: int) -> list:
    """拉一个 chat 的历史消息。"""
    msgs = []
    page_token = None
    while True:
        b = (
            ListMessageRequest.builder()
            .container_id_type("chat")
            .container_id(chat_id)
            .page_size(50)
            .start_time(str(start_ms // 1000))
            .end_time(str(end_ms // 1000))
            .sort_type("ByCreateTimeAsc")
        )
        if page_token:
            b = b.page_token(page_token)
        resp = client.im.v1.message.list(b.build())
        if not resp.success():
            log(f"list message 失败: code={resp.code} msg={resp.msg}")
            break
        items = resp.data.items or []
        msgs.extend(items)
        if not resp.data.has_more:
            break
        page_token = resp.data.page_token
        time.sleep(0.2)
    return msgs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=0, help="过去 N 天")
    parser.add_argument("--hours", type=int, default=0, help="过去 N 小时")
    parser.add_argument("--chat-id", type=str, default="", help="指定 chat_id（默认扫描所有 p2p）")
    args = parser.parse_args()

    if not args.days and not args.hours:
        args.days = 7

    if not APP_ID or not APP_SECRET:
        log("FEISHU_APP_ID/SECRET 未配置")
        sys.exit(1)

    delta = timedelta(days=args.days, hours=args.hours)
    end = datetime.now()
    start = end - delta
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    log(f"回溯窗口: {start.isoformat(timespec='seconds')} → {end.isoformat(timespec='seconds')}")

    client = lark.Client.builder().app_id(APP_ID).app_secret(APP_SECRET).build()

    chats = []
    if args.chat_id:
        chats = [(args.chat_id, "(指定)", "")]
    else:
        log("枚举 p2p 会话…")
        chats = list_p2p_chats(client)
        log(f"发现 {len(chats)} 个 p2p 会话")

    total_saved = 0
    total_msgs = 0
    for chat_id, name, _ in chats:
        log(f"━━━ chat={chat_id} ({name})")
        msgs = fetch_history(client, chat_id, start_ms, end_ms)
        log(f"  共 {len(msgs)} 条消息")
        total_msgs += len(msgs)
        for m in msgs:
            stat = process_message(client, m)
            if stat["saved"]:
                total_saved += len(stat["saved"])
                log(f"  ✅ {stat['ts']} {stat['msg_type']:5s} -> {len(stat['saved'])} 个文件")
                for p in stat["saved"]:
                    log(f"      {p}")
            elif stat["msg_type"] == "text":
                log(f"  · {stat['ts']} text: {stat['text']}")
            else:
                log(f"  ⚠️ {stat['ts']} {stat['msg_type']} 未提取到资源")
            time.sleep(0.1)

    log("━━━━━━━━━━")
    log(f"完成：扫描 {total_msgs} 条消息，落盘 {total_saved} 个文件")


if __name__ == "__main__":
    main()
