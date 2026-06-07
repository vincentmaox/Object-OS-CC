"""
真机渲染测试：把三种卡片各发一张到飞书。

用法：python card_render_test.py

接收人默认 ou_59a5d4b0cc115a66295961a1aec66a9e（茅弘毅）。
也可改为 chat_id（自调试群）。

成功标准：飞书上能看到三张卡片，按钮可见但点击暂无响应
（按钮回调将由 sdk_bot_server.py 监听，本测试不验证回调）。
"""
import json
import uuid

# Import feishu_sync first — it sets up its own UTF-8 stdout/stderr wrappers.
from feishu_sync import FeishuClient
from feishu_cards import (
    build_permission_card,
    build_morning_report_card,
    build_status_card,
    truncate_preview,
)

TARGET_USER = "ou_59a5d4b0cc115a66295961a1aec66a9e"


def main():
    fc = FeishuClient()

    print("=" * 60)
    print("飞书卡片真机渲染测试")
    print("=" * 60)
    print(f"目标用户: {TARGET_USER}")
    print()

    # 1) 权限卡片
    req_id = f"req_{uuid.uuid4().hex[:8]}"
    perm_card = build_permission_card(
        tool_name="Bash",
        input_preview=truncate_preview('echo "hello from card render test" > D:/tmp_card_test.txt', 200),
        request_id=req_id,
        description="测试卡片：本次点击不会触发任何动作（router 尚未接入）",
    )
    print(f"[1/3] 发送权限卡片 request_id={req_id}")
    r1 = fc.send_interactive_card(TARGET_USER, perm_card)
    print(f"      result: {json.dumps(r1, ensure_ascii=False)[:200]}")

    # 2) 晨报卡片
    morn_card = build_morning_report_card(
        project_name="ProjectOS（自测）",
        status="active",
        mva_day=3,
        last_active="2026-06-07",
        summary="Day3 进行中：卡片模板已建好，正在做真机渲染验证。",
        blockers=["待接入 card.action.trigger 路由"],
    )
    print(f"[2/3] 发送晨报卡片")
    r2 = fc.send_interactive_card(TARGET_USER, morn_card)
    print(f"      result: {json.dumps(r2, ensure_ascii=False)[:200]}")

    # 3) 状态卡片
    status_card = build_status_card(
        title="🛠 SDK 执行中…",
        body="**步骤 1/3：** 解析任务\n**步骤 2/3：** 调用工具（等待权限）\n**步骤 3/3：** 总结",
        template="blue",
        footer="cost: $0.000 · turns: 0",
    )
    print(f"[3/3] 发送状态卡片")
    r3 = fc.send_interactive_card(TARGET_USER, status_card)
    print(f"      result: {json.dumps(r3, ensure_ascii=False)[:200]}")

    print()
    print("=" * 60)
    print("完成。请打开飞书查看三张卡片，确认按钮渲染正常。")
    print("=" * 60)


if __name__ == "__main__":
    main()
