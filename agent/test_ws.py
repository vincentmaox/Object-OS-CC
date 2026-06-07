"""WebSocket长连接测试v2 - 完整日志+原始事件打印"""
import sys
import io
import json
import os
from pathlib import Path
import lark_oapi as lark
from lark_oapi.api.im.v1 import *

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', write_through=True)

def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_env_file(Path(__file__).with_name("cc_bot.env"))
APP_ID = os.environ["FEISHU_APP_ID"]
APP_SECRET = os.environ["FEISHU_APP_SECRET"]


def on_message(data) -> None:
    """收到消息事件"""
    print(f"\n{'='*60}")
    print(f"[收到消息事件!]")
    try:
        event = data.event
        msg = event.message
        sender = event.sender
        chat_id = msg.chat_id if msg else "N/A"
        msg_type = msg.message_type if msg else "N/A"
        content = msg.content if msg else "N/A"
        sender_id = sender.sender_id.open_id if sender and sender.sender_id else "N/A"
        msg_id = msg.message_id if msg else "N/A"
        print(f"  msg_id={msg_id}")
        print(f"  chat_id={chat_id}")
        print(f"  sender_id={sender_id}")
        print(f"  msg_type={msg_type}")
        print(f"  content={content}")
    except Exception as e:
        print(f"  [解析错误] {e}")
    print(f"{'='*60}\n")

    # 立即回复确认
    try:
        client = lark.Client.builder().app_id(APP_ID).app_secret(APP_SECRET).build()
        req = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(sender_id)
                .msg_type("text")
                .content(json.dumps({"text": "[CC小助手] WebSocket连接测试成功！收到你的消息了 ✅"}))
                .build()) \
            .build()
        resp = client.im.v1.message.create(req)
        print(f"  [回复] ok={resp.success()}")
    except Exception as e:
        print(f"  [回复失败] {e}")


def on_raw_event(client, event):
    """原始事件兜底"""
    print(f"\n[原始事件] header={event.header.event_type if event.header else 'N/A'}")


event_handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_im_message_receive_v1(on_message)
    .build()
)

cli = lark.ws.Client(
    APP_ID,
    APP_SECRET,
    event_handler=event_handler,
    log_level=lark.LogLevel.DEBUG,
)

print(f"[启动] APP_ID={APP_ID}")
print(f"[启动] 等待飞书消息事件...")
print(f"[启动] 请在飞书给 CC小助手 发一条消息")
print(f"[启动] 按 Ctrl+C 退出\n")

cli.start()
