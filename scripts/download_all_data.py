# -*- coding: utf-8 -*-
"""
批量下载所有股票完整数据
"""

import json
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.download_comprehensive import ComprehensiveDataDownloader


def main():
    # 读取已下载股票列表
    progress_file = project_root / "data" / "download_progress.json"
    if not progress_file.exists():
        print("[ERROR] 进度文件不存在")
        return 1

    with open(progress_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    stocks = data.get("downloaded_stocks", [])
    if not stocks:
        print("[ERROR] 没有找到已下载的股票列表")
        return 1

    print(f"[INFO] 找到 {len(stocks)} 只股票")
    print(f"[INFO] 开始下载完整数据...\n")

    downloader = ComprehensiveDataDownloader(base_dir="data")

    # 下载每只股票的完整数据（K线已存在，跳过）
    for i, symbol in enumerate(stocks, 1):
        print(f"\n[{i}/{len(stocks)}] 下载 {symbol}...")
        # 不下载K线（已有），只下载财务和资金数据
        downloader.download_all_for_stock(symbol, download_klines=False)

    # 下载市场概览数据
    print(f"\n{'='*60}")
    print("下载市场概览数据")
    print(f"{'='*60}")
    downloader.download_market_overview()

    # 打印摘要
    downloader.print_summary()

    return 0


if __name__ == "__main__":
    sys.exit(main())