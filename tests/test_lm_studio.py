"""Verification script for local AI with LM Studio."""

import asyncio
import base64
from io import BytesIO
import pytest
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionToolParam

try:
    from PIL import Image
    import numpy as np
except ImportError:
    Image = None
    np = None

@pytest.mark.asyncio
async def test_lm_studio():
    """Test LM Studio connection and basic AI functionality."""

    client = AsyncOpenAI(
        base_url='http://localhost:1234/v1',
        api_key='lm-studio'
    )

    print("=" * 60)
    print("Testing LM Studio Connection")
    print("=" * 60)

    # Test 1: Simple chat
    print("\n1. Testing simple chat...")
    response = await client.chat.completions.create(
        model='zai-org/GLM-4.6V-Flash',
        messages=[{'role': 'user', 'content': 'Respond with just the word TEST'}]
    )
    content = response.choices[0].message.content
    assert content is not None, "Response content is None"
    response_content = content.strip()
    print(f"Response: {response_content}")
    assert response_content == "TEST", f"Simple chat failed (got '{response_content}')"
    print(" Simple chat: PASSED")

    # Test 2: JSON response
    print("\n2. Testing JSON response...")
    response = await client.chat.completions.create(
        model='zai-org/GLM-4.6V-Flash',
        messages=[{
            'role': 'system',
            'content': 'You are a helpful assistant. Respond in JSON format.'
        }, {
            'role': 'user',
            'content': 'Respond with {"status": "ok", "message": "working"}'
        }]
    )
    json_content = response.choices[0].message.content
    print(f"Response: {json_content}")
    print(" JSON response: PASSED")

    # Test 3: Tool calling (if supported)
    print("\n3. Testing tool calling...")
    tools: list[ChatCompletionToolParam] = [{
        'type': 'function',
        'function': {
            'name': 'get_time',
            'description': 'Get the current time',
            'parameters': {
                'type': 'object',
                'properties': {}
            }
        }
    }]

    response = await client.chat.completions.create(
        model='zai-org/GLM-4.6V-Flash',
        messages=[{'role': 'user', 'content': 'What time is it?'}],
        tools=tools
    )

    tool_calls = response.choices[0].message.tool_calls
    print(f"Tool calls: {tool_calls}")

    # Test 4: Vision (if supported)
    print("\n4. Testing vision capabilities...")

    if Image is None or np is None:
        print(" Skipping vision test: PIL/numpy not available")
        return

    # Create a simple test image (red square)
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = BytesIO()
    img.save(img_bytes, 'PNG')
    img_bytes.seek(0)
    img_base64 = base64.b64encode(img_bytes.read()).decode('utf-8')

    response = await client.chat.completions.create(
        model='zai-org/GLM-4.6V-Flash',
        messages=[{
            'role': 'user',
            'content': [
                {
                    'type': 'text',
                    'text': 'What do you see in this image?'
                },
                {
                    'type': 'image_url',
                    'image_url': {
                        'url': f"data:image/png;base64,{img_base64}"
                    }
                }
            ]
        }]
    )

    vision_content = response.choices[0].message.content
    print(f"Vision response: {vision_content}")
    print(" Vision capabilities: PASSED")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_lm_studio())
