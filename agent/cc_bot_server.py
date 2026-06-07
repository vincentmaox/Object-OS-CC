"""CC小助手 - 飞书 Bot 服务（WebSocket长连接）

架构：
  飞书消息 → WebSocket推到本机 → 解析文本 → 立即回ACK
                                          ↓
                              线程池跑 claude CLI（cwd=ProjectOS）
                                          ↓
                                  结果推回飞书私聊
"""
import sys
import io
import json
import os
import subprocess
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", write_through=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", write_through=True)

WORKDIR = Path(r"D:\ClaudeCodeProjects\_ProjectOS")
ENV_FILE = WORKDIR / "agent" / "cc_bot.env"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if value.strip():
            os.environ.setdefault(key.strip(), value.strip())


load_env_file(ENV_FILE)

APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
ALLOWED_OPEN_IDS = set(filter(None, os.environ.get("FEISHU_ALLOWED_OPEN_IDS", "").split(",")))
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
CLAUDE_TIMEOUT = 300
LOG_FILE = WORKDIR / "agent" / "cc_bot.log"
CONTEXT_FILE = WORKDIR / "agent" / "cc_bot_context.json"
PROCESSED_IDS: set[str] = set()
CHAT_CONTEXTS: dict[str, deque[dict[str, str]]] = defaultdict(lambda: deque(maxlen=16))
CONTEXT_LOCK = threading.Lock()

_lark_client = None


def log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_contexts() -> None:
    if not CONTEXT_FILE.exists():
        return
    try:
        data = json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
        with CONTEXT_LOCK:
            for chat_id, turns in data.items():
                CHAT_CONTEXTS[chat_id] = deque(turns[-16:], maxlen=16)
        log(f"[上下文] 已加载 {len(data)} 个会话")
    except Exception as e:
        log(f"[上下文] 加载失败: {e}")


def save_contexts() -> None:
    try:
        with CONTEXT_LOCK:
            data = {chat_id: list(turns) for chat_id, turns in CHAT_CONTEXTS.items()}
        CONTEXT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log(f"[上下文] 保存失败: {e}")


def add_context(chat_id: str, role: str, content: str) -> None:
    with CONTEXT_LOCK:
        CHAT_CONTEXTS[chat_id].append({"role": role, "content": content[-4000:]})
    save_contexts()


def build_prompt(chat_id: str, text: str) -> str:
    with CONTEXT_LOCK:
        turns = list(CHAT_CONTEXTS[chat_id])
    lines = [
        "你是用户通过飞书联系的本机 Claude Code 助手。",
        "你在 D:\\ClaudeCodeProjects\\_ProjectOS 工作目录中运行。",
        "下面是最近几轮飞书对话上下文；回答当前用户消息时要参考这些上下文，尤其要知道自己上一轮回复了什么。",
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


def send_text(open_id: str, text: str) -> bool:
    """飞书最大单条 30k 字符；长内容自动分片"""
    if _lark_client is None:
        log("[send 失败] lark client 未初始化")
        return False
    CHUNK = 4000
    chunks = [text[i : i + CHUNK] for i in range(0, len(text), CHUNK)] or [""]
    ok_all = True
    for i, chunk in enumerate(chunks):
        prefix = f"[{i+1}/{len(chunks)}]\n" if len(chunks) > 1 else ""
        req = (
            CreateMessageRequest.builder()
            .receive_id_type("open_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(open_id)
                .msg_type("text")
                .content(json.dumps({"text": prefix + chunk}))
                .build()
            )
            .build()
        )
        try:
            resp = _lark_client.im.v1.message.create(req)
            if not resp.success():
                log(f"[send 失败] code={resp.code} msg={resp.msg}")
                ok_all = False
        except Exception as e:
            log(f"[send 异常] {e}")
            ok_all = False
    return ok_all


def run_claude(prompt: str) -> tuple[bool, str]:
    """同步调 claude -p。返回 (success, output)"""
    try:
        env = os.environ.copy()
        claude_dir = str(Path(CLAUDE_BIN).parent) if Path(CLAUDE_BIN).is_absolute() else ""
        env.update({
            "USERPROFILE": r"C:\Users\maoxu",
            "HOMEDRIVE": "C:",
            "HOMEPATH": r"\Users\maoxu",
            "APPDATA": r"C:\Users\maoxu\AppData\Roaming",
            "LOCALAPPDATA": r"C:\Users\maoxu\AppData\Local",
            "PATH": f"{claude_dir};D:\\miniconda3;D:\\miniconda3\\Scripts;" + env.get("PATH", ""),
        })
        proc = subprocess.run(
            [CLAUDE_BIN, "-p", prompt],
            cwd=str(WORKDIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CLAUDE_TIMEOUT,
            shell=False,
            env=env,
        )
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        if proc.returncode != 0:
            return False, f"[claude 退出码={proc.returncode}]\n{err or out or '(空输出)'}"
        return True, out or "(claude 无输出)"
    except subprocess.TimeoutExpired:
        return False, f"[超时] claude 执行超过 {CLAUDE_TIMEOUT}s 未返回"
    except FileNotFoundError:
        return False, f"[找不到 claude] 请确认 `{CLAUDE_BIN}` 在 PATH"
    except Exception as e:
        return False, f"[异常] {type(e).__name__}: {e}"


def handle_async(open_id: str, chat_id: str, prompt: str, msg_id: str) -> None:
    log(f"[worker 启动] msg={msg_id} prompt={prompt[:80]}")
    t0 = time.time()
    ok, out = run_claude(build_prompt(chat_id, prompt))
    cost = time.time() - t0
    header = f"✅ 完成（{cost:.1f}s）\n\n" if ok else f"❌ 失败（{cost:.1f}s）\n\n"
    add_context(chat_id, "assistant", out)
    send_text(open_id, header + out)
    log(f"[worker 结束] msg={msg_id} ok={ok} cost={cost:.1f}s outlen={len(out)}")


def on_message(data) -> None:
    try:
        msg = data.event.message
        sender = data.event.sender
        msg_id = msg.message_id
        chat_id = msg.chat_id
        open_id = sender.sender_id.open_id if sender and sender.sender_id else None
        chat_type = msg.chat_type
        msg_type = msg.message_type
        content_raw = msg.content
    except Exception as e:
        log(f"[解析事件失败] {e}")
        return

    if msg_id in PROCESSED_IDS:
        log(f"[去重] msg={msg_id} 已处理")
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
        send_text(open_id, f"暂只支持文本消息（你发的是 {msg_type}）")
        return

    try:
        text = json.loads(content_raw).get("text", "").strip()
    except Exception:
        text = ""
    if not text:
        send_text(open_id, "消息为空，请发文本指令")
        return

    log(f"[收到] msg={msg_id} chat={chat_id} from={open_id} text={text[:120]}")
    add_context(chat_id, "user", text)
    send_text(open_id, f"📥 收到，处理中…\n> {text[:100]}")

    threading.Thread(
        target=handle_async, args=(open_id, chat_id, text, msg_id), daemon=True
    ).start()


def main() -> None:
    global _lark_client
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not APP_ID or not APP_SECRET:
        raise RuntimeError(f"FEISHU_APP_ID / FEISHU_APP_SECRET 未配置，请检查 {ENV_FILE}")
    if not ALLOWED_OPEN_IDS:
        raise RuntimeError(f"FEISHU_ALLOWED_OPEN_IDS 未配置，请检查 {ENV_FILE}")
    _lark_client = lark.Client.builder().app_id(APP_ID).app_secret(APP_SECRET).build()
    load_contexts()
    handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(on_message)
        .build()
    )
    cli = lark.ws.Client(
        APP_ID,
        APP_SECRET,
        event_handler=handler,
        log_level=lark.LogLevel.INFO,
    )
    log(f"[启动] CC小助手 Bot 服务")
    log(f"[启动] APP_ID={APP_ID}")
    log(f"[启动] WORKDIR={WORKDIR}")
    log(f"[启动] 白名单={ALLOWED_OPEN_IDS}")
    log(f"[启动] 等待飞书消息...")
    cli.start()


if __name__ == "__main__":
    main()
