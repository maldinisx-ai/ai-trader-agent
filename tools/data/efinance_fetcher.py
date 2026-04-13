# -*- coding: utf-8 -*-
"""
Efinance 数据下载器（支持断点续传）

基于 efinance 库的稳定数据源（东方财富数据）。
特点：免费、无需Token、API简洁、数据全面、断点续传。
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Set

import pandas as pd

logger = logging.getLogger(__name__)


class EfinanceDownloader:
    """Efinance 数据下载器（支持断点续传）"""

    def __init__(self, output_dir: str = "data/stocks", progress_file: str = "data/download_progress.json"):
        """
        初始化下载器

        Args:
            output_dir: 数据输出目录
            progress_file: 进度文件路径
        """
        try:
            import efinance as ef
            self.ef = ef
        except ImportError:
            raise RuntimeError("efinance 未安装，请运行: pip install efinance")

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file = Path(progress_file)
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)

        # 加载进度
        self.progress = self._load_progress()

        # 统计
        self.session_success = 0
        self.session_failed = 0
        self.session_skipped = 0

    def _load_progress(self) -> dict:
        """加载下载进度"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 转换列表为集合
                    return {
                        "downloaded": set(data.get("downloaded", [])),
                        "failed": set(data.get("failed", [])),
                        "last_update": data.get("last_update"),
                        "total_success": data.get("total_success", 0),
                        "total_failed": data.get("total_failed", 0)
                    }
            except Exception as e:
                logger.warning(f"加载进度文件失败: {e}")

        return {
            "downloaded": set(),      # 已下载的股票
            "failed": set(),          # 失败的股票
            "last_update": None,
            "total_success": 0,
            "total_failed": 0
        }

    def _save_progress(self):
        """保存下载进度"""
        # 转换 set 为 list 以便 JSON 序列化
        progress_data = {
            "downloaded": list(self.progress["downloaded"]),
            "failed": list(self.progress["failed"]),
            "last_update": datetime.now().isoformat(),
            "total_success": self.progress["total_success"],
            "total_failed": self.progress["total_failed"]
        }

        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, indent=2, ensure_ascii=False)

    def _is_downloaded(self, symbol: str) -> bool:
        """检查股票是否已下载"""
        return symbol in self.progress["downloaded"]

    def _mark_downloaded(self, symbol: str):
        """标记股票为已下载"""
        self.progress["downloaded"].add(symbol)
        if symbol in self.progress["failed"]:
            self.progress["failed"].remove(symbol)
        self.progress["total_success"] = len(self.progress["downloaded"])

    def _mark_failed(self, symbol: str):
        """标记股票为下载失败"""
        if symbol not in self.progress["downloaded"]:
            self.progress["failed"].add(symbol)
            self.progress["total_failed"] = len(self.progress["failed"])

    def get_stock_list(self) -> List[dict]:
        """
        获取股票列表

        Returns:
            [{'code': '000001', 'name': '平安银行'}, ...]
        """
        try:
            df = self.ef.stock.get_realtime_quotes()

            if df is None or df.empty:
                return []

            stocks = []
            for _, row in df.iterrows():
                code = str(row.get('股票代码', ''))
                name = str(row.get('股票名称', ''))

                if code and code.isdigit() and len(code) == 6:
                    stocks.append({'code': code, 'name': name})

            return stocks

        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []

    def download_klines(
        self,
        symbol: str,
        days: int = 365,
        retry: int = 3
    ) -> Optional[pd.DataFrame]:
        """
        下载K线数据（带重试）

        Args:
            symbol: 股票代码
            days: 天数
            retry: 重试次数

        Returns:
            DataFrame
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        for attempt in range(retry):
            try:
                df = self.ef.stock.get_quote_history(
                    symbol,
                    beg=start_date.strftime('%Y%m%d'),
                    end=end_date.strftime('%Y%m%d'),
                    klt=101
                )

                if df is None or df.empty:
                    if attempt < retry - 1:
                        time.sleep(1)
                        continue
                    return None

                # 标准化列名
                column_map = {
                    '股票名称': 'name',
                    '股票代码': 'code',
                    '日期': 'date',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount',
                }

                df = df.rename(columns=column_map)
                df['symbol'] = symbol

                # 选择需要的列
                cols = ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']
                available_cols = [c for c in cols if c in df.columns]

                return df[available_cols]

            except Exception as e:
                if attempt < retry - 1:
                    time.sleep(1)
                    continue
                logger.error(f"下载 {symbol} 失败: {e}")
                return None

    def download_batch(
        self,
        symbols: List[str],
        days: int = 365,
        skip_downloaded: bool = True,
        resume_failed: bool = True
    ):
        """
        批量下载（支持断点续传）

        Args:
            symbols: 股票代码列表
            days: 天数
            skip_downloaded: 是否跳过已下载的股票
            resume_failed: 是否重试之前失败的股票
        """
        # 过滤列表
        to_download = []
        skipped = 0

        for symbol in symbols:
            if skip_downloaded and self._is_downloaded(symbol):
                skipped += 1
                continue
            to_download.append(symbol)

        if not to_download:
            print(f"没有需要下载的股票（已跳过 {skipped} 只已下载的股票）")
            return 0, 0

        print(f"准备下载 {len(to_download)} 只股票（跳过 {skipped} 只已下载）")
        print("=" * 60)

        success = 0
        failed = 0

        for i, symbol in enumerate(to_download, 1):
            # 检查文件是否已存在
            output_file = self.output_dir / f"stock_{symbol}.csv"
            if output_file.exists() and skip_downloaded:
                self.session_skipped += 1
                if i % 50 == 0:
                    print(f"[{i}/{len(to_download)}] 跳过 {symbol}")
                continue

            # 下载数据
            df = self.download_klines(symbol, days)

            if df is not None and not df.empty:
                df.to_csv(output_file, index=False, encoding='utf-8-sig')
                self._mark_downloaded(symbol)
                self.session_success += 1
                success += 1

                # 进度显示
                if i % 10 == 0 or i == len(to_download):
                    pct = (i / len(to_download)) * 100
                    print(f"[{i}/{len(to_download)} ({pct:.1f}%)] {symbol}: OK {len(df)} 行")
                else:
                    print(f"[{i}/{len(to_download)}] {symbol}: OK {len(df)} 行")
            else:
                self._mark_failed(symbol)
                self.session_failed += 1
                failed += 1
                print(f"[{i}/{len(to_download)}] {symbol}: FAIL")

            # 延迟
            if i < len(to_download):
                time.sleep(0.15)

            # 定期保存进度
            if i % 20 == 0:
                self._save_progress()

        # 保存最终进度
        self._save_progress()

        print("\n" + "=" * 60)
        print(f"本次下载: 成功 {success}, 跳过 {self.session_skipped}, 失败 {failed}")
        print(f"总计: 已下载 {len(self.progress['downloaded'])}, "
              f"失败 {len(self.progress['failed'])}")

        return success, failed

    def retry_failed(self, max_retries: int = 3):
        """
        重试失败的股票

        Args:
            max_retries: 最大重试次数
        """
        if not self.progress["failed"]:
            print("没有失败的股票需要重试")
            return

        failed_list = list(self.progress["failed"])
        print(f"重试 {len(failed_list)} 只失败的股票...")

        for retry_round in range(1, max_retries + 1):
            print(f"\n第 {retry_round} 轮重试...")

            success, failed = self.download_batch(
                failed_list,
                skip_downloaded=True,
                resume_failed=False
            )

            if failed == 0:
                print(f"\n全部下载完成！")
                break
            else:
                print(f"\n还有 {failed} 只股票失败")
                failed_list = [s for s in failed_list if s in self.progress["failed"]]

    def show_status(self):
        """显示下载状态"""
        downloaded = len(self.progress["downloaded"])
        failed = len(self.progress["failed"])

        print("\n" + "=" * 60)
        print("[下载状态]")
        print("=" * 60)
        print(f"已下载: {downloaded} 只")
        print(f"失败: {failed} 只")
        print(f"最后更新: {self.progress.get('last_update', '从未')}")

        if failed > 0:
            print(f"\n失败的股票: {list(self.progress['failed'])[:10]}...")
            if len(self.progress['failed']) > 10:
                print(f"  (还有 {len(self.progress['failed']) - 10} 只)")

        print("=" * 60)

    def clear_progress(self):
        """清除进度（重新开始）"""
        self.progress = {
            "downloaded": set(),
            "failed": set(),
            "last_update": None,
            "total_success": 0,
            "total_failed": 0
        }
        self._save_progress()
        print("进度已清除")


def download_all_stocks(
    limit: int = None,
    days: int = 365,
    skip_existing: bool = True
):
    """
    下载所有A股数据

    Args:
        limit: 限制下载数量（None=全部）
        days: 天数
        skip_existing: 是否跳过已存在的文件
    """
    downloader = EfinanceDownloader()

    print("获取股票列表...")
    all_stocks = downloader.get_stock_list()

    if not all_stocks:
        print("获取股票列表失败")
        return

    if limit:
        all_stocks = all_stocks[:limit]

    symbols = [s['code'] for s in all_stocks]

    print(f"共 {len(symbols)} 只股票")
    downloader.show_status()

    downloader.download_batch(symbols, days=days, skip_downloaded=skip_existing)

    # 显示最终状态
    downloader.show_status()

    # 询问是否重试失败的
    if downloader.progress["failed"]:
        print("\n是否重试失败的股票？(y/n): ", end="")
        # 简化处理，自动重试一次
        print("自动重试...")
        downloader.retry_failed(max_retries=1)


if __name__ == "__main__":
    import sys

    downloader = EfinanceDownloader()

    # 显示命令帮助
    if len(sys.argv) == 1:
        print("用法:")
        print("  python efinance_fetcher.py                    # 继续下载")
        print("  python efinance_fetcher.py status             # 查看状态")
        print("  python efinance_fetcher.py retry              # 重试失败")
        print("  python efinance_fetcher.py clear              # 清除进度")
        print("  python efinance_fetcher.py <code> [days]      # 下载单只")
        print("\n开始继续下载...")
        downloader.show_status()
        download_all_stocks(limit=500, days=365, skip_existing=True)

    elif sys.argv[1] == "status":
        downloader.show_status()

    elif sys.argv[1] == "retry":
        downloader.retry_failed(max_retries=3)

    elif sys.argv[1] == "clear":
        downloader.clear_progress()

    else:
        # 下载单只股票
        symbol = sys.argv[1]
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 365

        df = downloader.download_klines(symbol, days)

        if df is not None:
            print(f"\n{symbol} 数据下载成功: {len(df)} 行")
            print(df.tail())

            output_path = downloader.output_dir / f"stock_{symbol}.csv"
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"已保存: {output_path}")
        else:
            print(f"下载失败")
