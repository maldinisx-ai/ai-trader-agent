# -*- coding: utf-8 -*-
"""
股票数据下载脚本 - 使用 finshare

基于 finshare 的免费多数据源下载器，自动切换数据源。
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

try:
    import finshare as fs
    import pandas as pd
except ImportError as e:
    print("错误: 需要安装 finshare 和 pandas")
    print("安装命令: pip install finshare pandas")
    sys.exit(1)


class StockDownloader:
    """股票数据下载器 - 基于 finshare"""

    def __init__(self, output_dir: str = "data/stocks", quotes_dir: str = "data/quotes"):
        self.output_dir = Path(output_dir)
        self.quotes_dir = Path(quotes_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.quotes_dir.mkdir(parents=True, exist_ok=True)

        # 进度文件
        self.progress_file = self.output_dir.parent / "download_progress.json"
        self.progress = self._load_progress()

        # 统计
        self.success_count = 0
        self.fail_count = 0
        self.skip_count = 0

    def _load_progress(self) -> dict:
        """加载下载进度"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "last_update": None,
            "downloaded_stocks": [],
            "failed_stocks": []
        }

    def _save_progress(self):
        """保存下载进度"""
        self.progress["last_update"] = datetime.now().isoformat()
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(self.progress, f, indent=2, ensure_ascii=False)

    def download_stock_klines(
        self,
        symbol: str,
        days: int = 365,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        下载单只股票K线数据

        Args:
            symbol: 股票代码 (格式: 000001.SZ 或 600000.SH)
            days: 天数
            start_date: 开始日期 (YYYY-MM-DD)，优先于 days
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            K线数据
        """
        try:
            # 设置日期范围
            if end_date is None:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            # 使用 finshare 下载
            df = fs.get_historical_data(symbol, start=start_date, end=end_date)

            if df is None or df.empty:
                return None

            return df

        except Exception as e:
            print(f"[WARN] {symbol}: {e}")
            return None

    def download_stock_quote(self, symbol: str) -> Optional[dict]:
        """
        下载单只股票实时行情

        Args:
            symbol: 股票代码

        Returns:
            行情字典
        """
        try:
            # 获取最新一天数据作为"实时"行情
            df = fs.get_historical_data(
                symbol,
                start=(datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'),
                end=datetime.now().strftime('%Y-%m-%d')
            )

            if df is None or df.empty:
                return None

            latest = df.iloc[-1]

            return {
                "symbol": str(latest.get('code', symbol)),
                "name": str(latest.get('name', '')),
                "price": float(latest.get('close', 0)),
                "change": 0.0,  # 需要计算涨跌幅
                "volume": int(latest.get('volume', 0)),
                "amount": float(latest.get('amount', 0)),
                "high": float(latest.get('high', 0)),
                "low": float(latest.get('low', 0)),
                "open": float(latest.get('open', 0)),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return None

    def download_all(
        self,
        symbols: List[str],
        download_klines: bool = True,
        download_quotes: bool = True,
        days: int = 365,
        batch_size: int = 10
    ):
        """
        批量下载

        Args:
            symbols: 股票代码列表
            download_klines: 是否下载K线
            download_quotes: 是否下载实时行情
            days: 天数
            batch_size: 批次大小
        """
        total = len(symbols)
        print(f"[INFO] 开始下载 {total} 只股票数据...")
        print(f"[INFO] 数据范围: 最近 {days} 天")

        quotes_data = {}

        for i, symbol in enumerate(symbols, 1):
            # 检查是否已下载
            if download_klines:
                filename = symbol.replace('.', '_') + '.csv'
                kline_file = self.output_dir / filename
                if kline_file.exists() and symbol in self.progress.get("downloaded_stocks", []):
                    self.skip_count += 1
                    if i % 5 == 0:
                        print(f"[{i}/{total}] 跳过 {symbol} (已存在)")
                    continue

            # 下载K线
            if download_klines:
                df = self.download_stock_klines(symbol, days=days)
                if df is not None:
                    filename = symbol.replace('.', '_') + '.csv'
                    output_file = self.output_dir / filename
                    df.to_csv(output_file, index=False, encoding='utf-8-sig')
                    self.success_count += 1
                    print(f"[{i}/{total}] [OK] {symbol}: {len(df)} 条记录")

                    if symbol not in self.progress.get("downloaded_stocks", []):
                        self.progress.setdefault("downloaded_stocks", []).append(symbol)
                else:
                    self.fail_count += 1
                    print(f"[{i}/{total}] [FAIL] {symbol}")

            # 下载行情
            if download_quotes:
                quote = self.download_stock_quote(symbol)
                if quote:
                    quotes_data[symbol] = quote

            # 保存进度
            if i % batch_size == 0:
                self._save_progress()

            # 延迟避免请求过快
            time.sleep(0.2)

        # 保存行情数据
        if download_quotes and quotes_data:
            quotes_file = self.quotes_dir / f"quotes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(quotes_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "update_time": datetime.now().isoformat(),
                    "count": len(quotes_data),
                    "data": quotes_data
                }, f, ensure_ascii=False, indent=2)
            print(f"[INFO] 行情数据已保存: {quotes_file}")

        # 更新索引
        with open(self.output_dir.parent / "latest.json", 'w', encoding='utf-8') as f:
            json.dump({
                "update_time": datetime.now().isoformat(),
                "stock_count": len(self.progress.get("downloaded_stocks", [])),
                "quotes_file": str(quotes_file.name) if download_quotes and quotes_data else None,
                "data_source": "finshare"
            }, f, indent=2, ensure_ascii=False)

        self._save_progress()
        print(f"\n[SUCCESS] 下载完成!")
        print(f"  成功: {self.success_count}")
        print(f"  跳过: {self.skip_count}")
        print(f"  失败: {self.fail_count}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="下载股票数据 - 基于 finshare")
    parser.add_argument("--limit", type=int, default=None,
                        help="限制下载数量（默认全部）")
    parser.add_argument("--symbols", type=str, nargs="+",
                        help="指定股票代码列表 (格式: 000001.SZ 600000.SH)")
    parser.add_argument("--days", type=int, default=365,
                        help="下载天数（默认365天）")
    parser.add_argument("--klines", action="store_true", default=True,
                        help="下载K线数据")
    parser.add_argument("--quotes", action="store_true", default=False,
                        help="下载实时行情")
    parser.add_argument("--output", type=str, default="data/stocks",
                        help="K线输出目录")
    parser.add_argument("--quotes-dir", type=str, default="data/quotes",
                        help="行情输出目录")

    args = parser.parse_args()

    downloader = StockDownloader(
        output_dir=args.output,
        quotes_dir=args.quotes_dir
    )

    # 确定下载列表
    if args.symbols:
        symbols = args.symbols
    else:
        # 使用热门股票列表作为示例
        symbols = [
            '000001.SZ', '000002.SZ', '000063.SZ', '000333.SZ',
            '000568.SZ', '000651.SZ', '000725.SZ', '000768.SZ',
            '000858.SZ', '002008.SZ', '002049.SZ', '002142.SZ',
            '002271.SZ', '002304.SZ', '002415.SZ', '002475.SZ',
            '002594.SZ', '002601.SZ', '002607.SZ', '002821.SZ',
            '002841.SZ', '600000.SH', '600016.SH', '600030.SH',
            '600036.SH', '600050.SH', '600089.SH', '600104.SH',
            '600276.SH', '600305.SH', '600438.SH', '600519.SH',
            '600566.SH', '600570.SH', '600582.SH', '600585.SH',
            '600594.SH', '600660.SH', '600741.SH', '600761.SH',
            '600783.SH', '600789.SH', '600809.SH', '600820.SH',
            '600869.SH', '600875.SH', '600880.SH', '600887.SH',
            '600900.SH', '600903.SH', '600919.SH', '600958.SH',
            '600963.SH', '600976.SH', '600985.SH', '600998.SH',
            '601000.SH', '601012.SH', '601015.SH', '601066.SH',
            '601077.SH', '601088.SH', '601098.SH', '601117.SH',
            '601127.SH', '601138.SH', '601155.SH', '601163.SH',
            '601166.SH', '601198.SH', '601211.SH', '601218.SH',
            '601225.SH', '601231.SH', '601233.SH', '601288.SH',
            '601318.SH', '601319.SH', '601328.SH', '601333.SH',
            '601369.SH', '601388.SH', '601390.SH', '601398.SH',
            '601515.SH', '601555.SH', '601566.SH', '601577.SH',
            '601588.SH', '601598.SH', '601600.SH', '601601.SH',
            '601606.SH', '601608.SH', '601611.SH', '601615.SH',
            '601618.SH', '601628.SH', '601633.SH', '601658.SH',
            '601666.SH', '601668.SH', '601669.SH', '601678.SH',
            '601688.SH', '601696.SH', '601699.SH', '601700.SH',
            '601717.SH', '601718.SH', '601727.SH', '601766.SH',
            '601777.SH', '601788.SH', '601798.SH', '601800.SH',
            '601801.SH', '601808.SH', '601816.SH', '601818.SH',
            '601828.SH', '601838.SH', '601857.SH', '601865.SH',
            '601868.SH', '601869.SH', '601872.SH', '601877.SH',
            '601878.SH', '601880.SH', '601881.SH', '601886.SH',
            '601888.SH', '601890.SH', '601898.SH', '601899.SH',
            '601901.SH', '601919.SH', '601928.SH', '601933.SH',
            '601939.SH', '601949.SH', '601958.SH', '601963.SH',
            '601969.SH', '601985.SH', '601988.SH', '601989.SH',
            '601995.SH', '601997.SH', '601998.SH', '603259.SH',
            '603658.SH', '603707.SH', '603899.SH', '603919.SH',
            '688111.SH', '688599.SH', '688981.SH'
        ]
        if args.limit:
            symbols = symbols[:args.limit]

    if not symbols:
        print("[ERROR] 没有需要下载的股票")
        return 1

    # 开始下载
    downloader.download_all(
        symbols=symbols,
        download_klines=args.klines,
        download_quotes=args.quotes,
        days=args.days
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())