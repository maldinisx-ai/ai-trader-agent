#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 API Key 配置"""
import os
from dotenv import load_dotenv

load_dotenv()

anthropic_key = os.getenv('ANTHROPIC_API_KEY')
zhipu_key = os.getenv('ZHIPU_API_KEY')

print('=' * 60)
print('API Key 配置检查')
print('=' * 60)

print(f'\nANTHROPIC_API_KEY:')
if anthropic_key:
    print(f'  长度: {len(anthropic_key)} 字符')
    print(f'  值: {anthropic_key}')
    if 'xxx' in anthropic_key.lower() or anthropic_key == 'sk-ant-xxx':
        print(f'  状态: ❌ 占位符，不是真实 key')
    elif len(anthropic_key) > 30:
        print(f'  状态: ✓ 看起来是真实 key')
else:
    print('  状态: 未设置')

print(f'\nZHIPU_API_KEY:')
if zhipu_key:
    print(f'  长度: {len(zhipu_key)} 字符')
    print(f'  值: {zhipu_key[:10]}...{zhipu_key[-10:]}')
else:
    print('  状态: 未设置')

print('\n' + '=' * 60)
print('结论')
print('=' * 60)
print('\n您当前没有设置有效的 Claude API key。')
print('\n选项:')
print('1. 使用本地模型（需要先下载 Ollama 模型）')
print('2. 设置真实的 ANTHROPIC_API_KEY')
print('3. 使用智谱 GLM API（需要有效的密钥）')
