#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证智谱 GLM 模型"""
import asyncio
import os
from dotenv import load_dotenv
from anthropic import AsyncAnthropic

load_dotenv()

async def test_glm():
    print("=" * 60)
    print("智谱 GLM 模型验证")
    print("=" * 60)

    print("\n配置信息:")
    print(f"  ANTHROPIC_BASE_URL: {os.getenv('ANTHROPIC_BASE_URL')}")
    print(f"  ZHIPU_API_KEY: {os.getenv('ZHIPU_API_KEY')[:20]}...")
    print(f"  ANTHROPIC_API_KEY: {os.getenv('ANTHROPIC_API_KEY')}")

    client = AsyncAnthropic(
        api_key=os.getenv('ANTHROPIC_API_KEY'),
        base_url=os.getenv('ANTHROPIC_BASE_URL')
    )

    print(f"\n实际调用:")
    print(f"  URL: {client.base_url}")

    try:
        response = await client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=100,
            messages=[{'role': 'user', 'content': '你好，请用一句话介绍你自己，并说明你是哪个公司的模型'}]
        )

        print(f"\n状态: 成功")
        print(f"\n模型回复:")
        print(f"  {response.content[0].text}")

        return True

    except Exception as e:
        print(f"\n状态: 失败")
        print(f"错误: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_glm())
    print("\n" + "=" * 60)
    if result:
        print("结论: 智谱 GLM 模型正常工作")
    else:
        print("结论: 智谱 GLM 模型调用失败")
    print("=" * 60)
