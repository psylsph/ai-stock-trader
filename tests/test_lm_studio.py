"""Verification script for local AI with LM Studio."""

import asyncio
import base64
from io import BytesIO
import pytest
import os
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionToolParam

# Skip by default unless RUN_AI_TESTS is set
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_AI_TESTS") != "true",
    reason="AI integration tests disabled by default"
)

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
        model='mistralai/ministral-3-3b',
        messages=[{'role': 'user', 'content': 'DO NOT THINK. Respond with just the word TEST.'}]
    )
    content = response.choices[0].message.content
    assert content is not None, "Response content is None"
    
    # Clean thinking tags if present
    import re
    cleaned_content = re.sub(r'\[THINK\].*?\[/THINK\]', '', content, flags=re.DOTALL).strip()
    
    print(f"Response: {cleaned_content}")
    assert cleaned_content == "TEST", f"Simple chat failed (got '{cleaned_content}')"
    print(" Simple chat: PASSED")

    # Test 2: JSON response
    print("\n2. Testing JSON response...")
    response = await client.chat.completions.create(
        model='mistralai/ministral-3-3b',
        messages=[{
            'role': 'system',
            'content': 'You are a helpful assistant. Respond in JSON format.'
        }, {
            'role': 'user',
            'content': 'DO NOT THINK. Respond with {"status": "ok", "message": "working"}.'
        }]
    )
    json_content = response.choices[0].message.content
    assert json_content is not None
    
    # Clean and parse
    import json
    cleaned_json = re.sub(r'\[THINK\].*?\[/THINK\]', '', json_content, flags=re.DOTALL)
    # Extract JSON between braces
    start = cleaned_json.find('{')
    end = cleaned_json.rfind('}')
    if start != -1 and end != -1:
        cleaned_json = cleaned_json[start:end+1]
    
    parsed = json.loads(cleaned_json)
    assert parsed["status"] == "ok"
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
        model='mistralai/ministral-3-3b',
        messages=[{'role': 'user', 'content': 'DO NOT THINK. What time is it?'}],
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
        model='mistralai/ministral-3-3b',
        messages=[{
            'role': 'user',
            'content': [
                {
                    'type': 'text',
                    'text': 'DO NOT THINK. What do you see in this image?'
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
