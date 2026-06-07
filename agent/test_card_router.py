"""
router 单元测试（无需真机点击）

模拟：
1. 注册一个 pending permission
2. 在另一个线程里"伪造"一个 P2CardActionTrigger 事件并调 handle_card_action
3. 验证 await_decision 能拿到正确结果
"""
import asyncio
import threading
import time
from feishu_card_router import PermissionRouter


class FakeOperator:
    def __init__(self, oid):
        self.open_id = oid
        self.user_id = None
        self.union_id = None
        self.tenant_key = None


class FakeAction:
    def __init__(self, value):
        self.value = value
        self.tag = "button"


class FakeEventData:
    def __init__(self, action, operator):
        self.action = action
        self.operator = operator
        self.token = "fake_token"
        self.context = None


class FakeEvent:
    def __init__(self, action_value, operator_open_id):
        self.event = FakeEventData(
            action=FakeAction(action_value),
            operator=FakeOperator(operator_open_id),
        )


async def test_allow_flow():
    print("--- test 1: allow ---")
    router = PermissionRouter()
    loop = asyncio.get_running_loop()
    router.bind_loop(loop)

    req_id = "req_test_allow"
    router.register(req_id, "Bash", "ou_test", message_id=None)

    # 1 秒后从另一个线程派发"allow"
    def click_after_delay():
        time.sleep(1.0)
        fake = FakeEvent({"action": "allow", "request_id": req_id}, "ou_test")
        resp = router.handle_card_action(fake)
        print(f"  router returned: toast={resp.get('toast', {}).get('content')}")

    threading.Thread(target=click_after_delay, daemon=True).start()

    t0 = time.time()
    decision = await router.await_decision(req_id, timeout=5)
    elapsed = time.time() - t0
    print(f"  decision={decision} elapsed={elapsed:.2f}s")
    assert decision == "allow", f"expected allow, got {decision}"
    router.cleanup(req_id)
    print("  ✅ pass")


async def test_deny_flow():
    print("\n--- test 2: deny ---")
    router = PermissionRouter()
    router.bind_loop(asyncio.get_running_loop())
    req_id = "req_test_deny"
    router.register(req_id, "Write", "ou_test", message_id=None)

    def click():
        time.sleep(0.5)
        fake = FakeEvent({"action": "deny", "request_id": req_id}, "ou_test")
        router.handle_card_action(fake)

    threading.Thread(target=click, daemon=True).start()
    decision = await router.await_decision(req_id, timeout=5)
    print(f"  decision={decision}")
    assert decision == "deny"
    router.cleanup(req_id)
    print("  ✅ pass")


async def test_timeout_flow():
    print("\n--- test 3: timeout ---")
    router = PermissionRouter()
    router.bind_loop(asyncio.get_running_loop())
    req_id = "req_test_timeout"
    router.register(req_id, "Bash", "ou_test", message_id=None)
    # 不派发任何点击
    t0 = time.time()
    decision = await router.await_decision(req_id, timeout=1.5)
    elapsed = time.time() - t0
    print(f"  decision={decision} elapsed={elapsed:.2f}s")
    assert decision == "timeout"
    router.cleanup(req_id)
    print("  ✅ pass")


async def test_more_button_does_not_resolve():
    print("\n--- test 4: 'See more' 不消耗 pending ---")
    router = PermissionRouter()
    router.bind_loop(asyncio.get_running_loop())
    req_id = "req_test_more"
    router.register(req_id, "Bash", "ou_test", message_id=None)

    fake_more = FakeEvent({"action": "more", "request_id": req_id}, "ou_test")
    resp = router.handle_card_action(fake_more)
    print(f"  more toast: {resp.get('toast', {}).get('content', '')[:80]}")
    assert "card" not in resp, "more 不应替换卡片"

    # pending 仍然在
    assert req_id in router._pending
    # 后续 allow 仍能解
    def click():
        time.sleep(0.3)
        router.handle_card_action(
            FakeEvent({"action": "allow", "request_id": req_id}, "ou_test")
        )

    threading.Thread(target=click, daemon=True).start()
    decision = await router.await_decision(req_id, timeout=3)
    assert decision == "allow"
    router.cleanup(req_id)
    print("  ✅ pass")


async def test_unknown_request_id():
    print("\n--- test 5: 过期 request_id ---")
    router = PermissionRouter()
    router.bind_loop(asyncio.get_running_loop())
    fake = FakeEvent({"action": "allow", "request_id": "req_ghost"}, "ou_test")
    resp = router.handle_card_action(fake)
    print(f"  toast: {resp.get('toast', {}).get('content', '')}")
    assert "过期" in resp["toast"]["content"] or "已处理" in resp["toast"]["content"]
    print("  ✅ pass")


async def test_non_permission_button():
    print("\n--- test 6: 晨报卡片 All-in 按钮 ---")
    router = PermissionRouter()
    router.bind_loop(asyncio.get_running_loop())
    fake = FakeEvent({"action": "all_in", "project": "NuclearPowerAI"}, "ou_test")
    resp = router.handle_card_action(fake)
    print(f"  toast: {resp.get('toast', {}).get('content', '')}")
    assert "NuclearPowerAI" in resp["toast"]["content"]
    print("  ✅ pass")


async def main():
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", write_through=True)
    print("=" * 60)
    print("PermissionRouter 单元测试")
    print("=" * 60)
    await test_allow_flow()
    await test_deny_flow()
    await test_timeout_flow()
    await test_more_button_does_not_resolve()
    await test_unknown_request_id()
    await test_non_permission_button()
    print("\n" + "=" * 60)
    print("✅ ✅ ✅ 所有测试通过")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
