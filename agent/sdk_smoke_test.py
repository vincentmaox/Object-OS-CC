"""
SDK smoke test - 验证三件事：
1. claude-agent-sdk 能否通过本地 claude CLI 跑通（自动继承 ~/.claude/settings.json 的火山方舟配置）
2. 火山方舟代理是否透传 tool_use（关键风险点）
3. can_use_tool 回调能否被触发，且能异步等待后返回 Allow/Deny

如果通过，方案D（SDK+现Bot）成立。
如果 can_use_tool 不触发但 Claude 正常回复 → 代理剥了tool_use，降级 Hooks 方案。
如果整个调用就报错 → 调研失败，原路返回。
"""
import asyncio
import sys
import io
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    PermissionResultAllow,
    PermissionResultDeny,
    AssistantMessage,
    UserMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
)

# Windows UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', write_through=True)

# 记录 can_use_tool 是否被触发
PERMISSION_LOG = []


async def my_can_use_tool(tool_name: str, input_args: dict, context):
    """模拟飞书round-trip：打个时间戳，假装等用户1秒，自动批准"""
    import time
    t0 = time.time()
    PERMISSION_LOG.append({"tool": tool_name, "input": input_args, "ts": t0})
    print(f"\n  [✅ can_use_tool TRIGGERED] tool={tool_name} input_keys={list(input_args.keys())}")
    # 模拟异步等待（飞书round-trip）
    await asyncio.sleep(1)
    elapsed = time.time() - t0
    print(f"  [↩️  返回 Allow] 等待{elapsed:.1f}s")
    return PermissionResultAllow()


async def main():
    print("=" * 60)
    print("SDK Smoke Test")
    print("=" * 60)
    print("配置来源: ~/.claude/settings.json (火山方舟 GLM-5.1)")
    print("拦截器: my_can_use_tool (异步等1秒后Allow)")
    print()

    options = ClaudeAgentOptions(
        # 走默认 claude CLI（会读 ~/.claude/settings.json）
        can_use_tool=my_can_use_tool,
        permission_mode='default',  # 必须 default 才会触发 can_use_tool
        setting_sources=[],  # 不继承 user/project 配置，避免被本地allowlist短路
        # 不预先allow，让can_use_tool来裁决
        max_turns=3,
        cwd='D:/ClaudeCodeProjects/_ProjectOS',
    )

    prompt = "请用 Bash 工具运行命令 `echo SDK_TEST_OK > D:/temp_sdk_test.txt` 然后告诉我执行结果。"

    msg_count = 0
    tool_use_count = 0
    text_chunks = []

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for message in client.receive_response():
            msg_count += 1
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_chunks.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        tool_use_count += 1
                        print(f"  [Claude决定调用] {block.name}({list(block.input.keys())})")
            elif isinstance(message, ResultMessage):
                print(f"\n  [完成] turns={message.num_turns} cost=${message.total_cost_usd or 0:.4f}")
                if message.usage:
                    print(f"  [usage] input={message.usage.get('input_tokens',0)} output={message.usage.get('output_tokens',0)}")

    print()
    print("=" * 60)
    print("结果分析")
    print("=" * 60)
    print(f"消息数: {msg_count}")
    print(f"Claude 主动 tool_use 次数: {tool_use_count}")
    print(f"can_use_tool 被触发次数: {len(PERMISSION_LOG)}")
    print(f"最终回复: {''.join(text_chunks)[:300]}")
    print()

    if tool_use_count > 0 and len(PERMISSION_LOG) > 0:
        print("✅ ✅ ✅ 方案D成立！火山方舟透传tool_use + can_use_tool拦截全部正常")
        return 0
    elif tool_use_count > 0 and len(PERMISSION_LOG) == 0:
        print("⚠️ 火山方舟透传tool_use，但can_use_tool未触发 — SDK拦截器问题")
        return 1
    elif tool_use_count == 0 and len(text_chunks) > 0:
        print("❌ 火山方舟未透传tool_use，Claude只能纯文本回答 — 降级Hooks方案")
        return 2
    else:
        print("❌ 调用无任何响应 — 配置/网络问题")
        return 3


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
