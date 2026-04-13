#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证 AI Trader Agent 模型配置
"""
import asyncio
import os
from dotenv import load_dotenv
from anthropic import AsyncAnthropic

load_dotenv()

async def verify_config():
    print("=" * 60)
    print("AI Trader Agent 模型配置验证")
    print("=" * 60)

    # 1. 环境变量检查
    print("\n[1] 环境变量配置")
    print("-" * 40)

    base_url = os.getenv('ANTHROPIC_BASE_URL')
    api_key = os.getenv('ANTHROPIC_API_KEY')
    zhipu_key = os.getenv('ZHIPU_API_KEY')

    print(f"ANTHROPIC_BASE_URL: {base_url}")
    print(f"ANTHROPIC_API_KEY: {api_key} ({len(api_key)} 字符)")
    print(f"ZHIPU_API_KEY: {zhipu_key[:20]}...{zhipu_key[-10:]} ({len(zhipu_key)} 字符)")

    # 2. 测试 API 调用
    print("\n[2] 测试 API 调用")
    print("-" * 40)

    client = AsyncAnthropic(
        api_key=api_key,
        base_url=base_url
    )

    try:
        response = await client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=50,
            messages=[{'role': 'user', 'content': '请用一句话介绍你自己'}]
        )

        print("状态: 成功")
        print(f"模型回复: {response.content[0].text[:50]}...")
        print(f"使用模型: {response.model if hasattr(response, 'model') else '未知'}")

        # Token 统计
        if hasattr(response, 'usage') and response.usage:
            print(f"Token 使用: {response.usage.input_tokens + response.usage.output_tokens}")

        return True

    except Exception as e:
        print(f"状态: 失败")
        print(f"错误: {type(e).__name__}: {str(e)[:100]}")
        return False

async def main():
    success = await verify_config()

    print("\n" + "=" * 60)
    print("[3] 配置总结")
    print("=" * 60)

    print("\n实际使用的配置:")
    print(f"  API 提供商: 智谱 AI (Zhipu AI)")
    print(f"  模型: GLM-4-Flash")
    print(f"  接口: Anthropic 兼容接口")
    print(f"  Base URL: {base_url}")
    print(f"  状态: {'正常工作' if success else '需要检查'}")

    print("\n配置说明:")
    print("  - 通过 ANTHROPIC_BASE_URL 重定向到智谱 AI")
    print("  - 使用 anthropic 库调用智谱 GLM 模型")
    print("  - ZHIPU_API_KEY 用于认证")

    print("\n" + "=" * 60)
    if success:
        print("结论: 模型配置正常，可以正常使用")
    else:
        print("结论: 模型配置异常，请检查网络或 API Key")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
