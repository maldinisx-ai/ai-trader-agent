#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新智谱 API Key
"""
import os
import sys

def update_zhipu_api_key():
    print("=" * 60)
    print("智谱 API Key 配置工具")
    print("=" * 60)

    print("\n当前配置:")
    print("-" * 40)

    # 读取当前 .env 文件
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            if line.startswith('ZHIPU_API_KEY='):
                current_key = line.split('=', 1)[1].strip()
                if current_key and current_key != 'xxx' and len(current_key) > 20:
                    print(f"ZHIPU_API_KEY: {current_key[:20]}...{current_key[-10:]}")
                    print(f"长度: {len(current_key)} 字符")
                else:
                    print("ZHIPU_API_KEY: 未设置或占位符")
                break
    except Exception as e:
        print(f"无法读取配置: {e}")
        return

    print("\n" + "=" * 60)
    print("请访问智谱 AI 开放平台获取 API Key:")
    print("https://open.bigmodel.cn/")
    print("=" * 60)

    print("\n步骤:")
    print("1. 访问 https://open.bigmodel.cn/")
    print("2. 注册/登录账号")
    print("3. 进入 'API Key' 页面")
    print("4. 创建新的 API Key")
    print("5. 复制 API Key")

    print("\n" + "=" * 60)
    new_key = input("请粘贴您的智谱 API Key: ").strip()

    if not new_key or len(new_key) < 20:
        print("\n无效的 API Key（太短）")
        return

    # 更新 .env 文件
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        updated = False
        for i, line in enumerate(lines):
            if line.startswith('ZHIPU_API_KEY='):
                lines[i] = f'ZHIPU_API_KEY={new_key}\n'
                updated = True
                break

        if updated:
            with open(env_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            print("\n" + "=" * 60)
            print("API Key 更新成功!")
            print("=" * 60)
            print(f"\n新 Key: {new_key[:20]}...{new_key[-10:]}")
            print(f"长度: {len(new_key)} 字符")
        else:
            print("\n未找到 ZHIPU_API_KEY 配置行")
    except Exception as e:
        print(f"\n更新失败: {e}")

if __name__ == "__main__":
    update_zhipu_api_key()
