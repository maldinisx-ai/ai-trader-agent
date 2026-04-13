#!/usr/bin/env python3
"""
AI Trader Agent 启动脚本

用法:
    python run.py              # 启动完整服务 (API + Web)
    python run.py --api-only   # 仅启动 API
    python run.py --web-only   # 仅启动 Web 前端
    python run.py --download   # 运行数据下载
"""
import sys
import argparse
import subprocess
import threading
import time
from pathlib import Path


def start_api(host='0.0.0.0', port=8000):
    """启动 API 服务"""
    import uvicorn
    uvicorn.run(
        "api.app:app",
        host=host,
        port=port,
        reload=True,
    )


def start_web():
    """启动 Web 前端"""
    web_dir = Path(__file__).parent / "web"
    subprocess.run(
        ["npm", "run", "dev"],
        cwd=web_dir,
        shell=True
    )


def main():
    parser = argparse.ArgumentParser(description='AI Trader Agent')
    parser.add_argument('--api-only', action='store_true', help='仅启动 API 服务')
    parser.add_argument('--web-only', action='store_true', help='仅启动 Web 前端')
    parser.add_argument('--download', action='store_true', help='运行数据下载')
    parser.add_argument('--port', type=int, default=8000, help='API 服务端口')
    parser.add_argument('--host', default='127.0.0.1', help='API 服务地址')

    args = parser.parse_args()

    if args.download:
        # 运行数据下载
        print("📥 启动数据下载...")
        # TODO: 调用下载脚本
        return

    if args.web_only:
        # 仅启动前端
        print("🌐 启动 Web 前端...")
        print("📱 访问: http://localhost:3000")
        start_web()
        return

    if args.api_only:
        # 仅启动 API
        print("🚀 启动 API 服务...")
        print(f"📊 API: http://{args.host}:{args.port}")
        print(f"📚 文档: http://{args.host}:{args.port}/docs")
        start_api(host=args.host, port=args.port)
        return

    # 启动完整服务（API + Web）
    print("=" * 60)
    print("🚀 启动 AI Trader Agent")
    print("=" * 60)
    print(f"📊 API:  http://{args.host}:{args.port}")
    print(f"📚 文档: http://{args.host}:{args.port}/docs")
    print(f"🌐 Web:  http://localhost:3000")
    print("=" * 60)
    print("")
    print("按 Ctrl+C 停止服务")
    print("")

    # 在单独线程中启动 API
    api_thread = threading.Thread(
        target=start_api,
        kwargs={'host': args.host, 'port': args.port},
        daemon=True
    )
    api_thread.start()

    # 等待 API 启动
    time.sleep(2)

    # 启动 Web 前端（阻塞）
    try:
        start_web()
    except KeyboardInterrupt:
        print("\n👋 服务已停止")


if __name__ == '__main__':
    sys.exit(main() or 0)
