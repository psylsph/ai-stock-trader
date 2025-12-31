"""Test streaming functionality with LM Studio."""

import asyncio
import pytest
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionToolParam


@pytest.mark.asyncio
async def test_streaming():
    """Test LM Studio connection with streaming."""

    client = AsyncOpenAI(
        base_url='http://localhost:1234/v1',
        api_key='lm-studio'
    )

    print("=" * 60)
    print("Testing Streaming with LM Studio")
    print("=" * 60)

    # Test 1: Simple text streaming
    print("\n1. Testing simple text streaming...")
    stream = await client.chat.completions.create(
        model='zai-org/GLM-4.6V-Flash',
        messages=[{'role': 'user', 'content': 'Count from 1 to 10'}],
        stream=True
    )

    full_text = ""
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end='', flush=True)
            full_text += chunk.choices[0].delta.content

    print()
    print(f"Full response: {full_text}")
    print(" Simple streaming: PASSED")

    # Test 2: JSON response streaming
    print("\n2. Testing JSON response streaming...")
    stream = await client.chat.completions.create(
        model='zai-org/GLM-4.6V-Flash',
        messages=[{
            'role': 'system',
            'content': 'You are a helpful assistant. Respond in valid JSON format.'
        }, {
            'role': 'user',
            'content': 'Respond with {"status": "ok", "message": "working"}'
        }],
        stream=True
    )

    full_json = ""
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end='', flush=True)
            full_json += chunk.choices[0].delta.content

    print()
    print(f"Full JSON: {full_json}")
    print(" JSON streaming: PASSED")

    # Test 3: Tool call streaming
    print("\n3. Testing tool call streaming...")
    tools: list[ChatCompletionToolParam] = [{
        'type': 'function',
        'function': {
            'name': 'get_current_time',
            'description': 'Get the current time',
            'parameters': {
                'type': 'object',
                'properties': {}
            }
        }
    }]

    stream = await client.chat.completions.create(
        model='zai-org/GLM-4.6V-Flash',
        messages=[{'role': 'user', 'content': 'What time is it?'}],
        tools=tools,
        stream=True
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            print(delta.content, end='', flush=True)
        if delta.tool_calls:
            print(f"\n[Tool Call Detected: {delta.tool_calls}]")

    print()
    print(" Tool call streaming: PASSED")

    print("\n" + "=" * 60)
    print("All streaming tests complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_streaming())
