# -*- coding: utf-8 -*-
"""
AkShare 数据下载器（使用可用接口）

使用 stock_zh_a_daily 接口，连接更稳定。
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class AkshareDownloader:
    """AkShare 数据下载器"""

    def __init__(self, output_dir: str = "data/stocks", progress_file: str = "data/akshare_progress.json"):
        """
        初始化下载器

        Args:
            output_dir: 数据输出目录
            progress_file: 进度文件路径
        """
        try:
            import akshare as ak
            self.ak = ak
        except ImportError:
            raise RuntimeError("akshare 未安装，请运行: pip install akshare")

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file = Path(progress_file)
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)

        # 加载进度
        self.progress = self._load_progress()

    def _load_progress(self) -> dict:
        """加载下载进度"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return {
                        "downloaded": set(data.get("downloaded", [])),
                        "failed": set(data.get("failed", [])),
                        "last_update": data.get("last_update"),
                    }
            except Exception as e:
                logger.warning(f"加载进度文件失败: {e}")

        return {
            "downloaded": set(),
            "failed": set(),
            "last_update": None,
        }

    def _save_progress(self):
        """保存下载进度"""
        progress_data = {
            "downloaded": sorted(list(self.progress["downloaded"])),
            "failed": sorted(list(self.progress["failed"])),
            "last_update": datetime.now().isoformat(),
        }

        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, indent=2, ensure_ascii=False)

    def _convert_symbol(self, symbol: str) -> str:
        """
        转换股票代码格式

        AkShare stock_zh_a_daily 需要 'sz' 或 'sh' 前缀
        """
        code = symbol.strip()

        # 去除已有前缀
        code = code.replace('SZ', '').replace('SH', '')
        code = code.replace('sz', '').replace('sh', '')
        code = code.replace('.SZ', '').replace('.SH', '')
        code = code.replace('.sz', '').replace('.sh', '')

        # 添加前缀
        if code.startswith(('60', '68', '51')):
            return f'sh{code}'  # 上海
        else:
            return f'sz{code}'  # 深圳

    def download_klines(
        self,
        symbol: str,
        days: int = 365,
        retry: int = 3
    ) -> Optional[pd.DataFrame]:
        """
        下载K线数据（使用 stock_zh_a_daily）

        Args:
            symbol: 股票代码
            days: 天数
            retry: 重试次数

        Returns:
            DataFrame
        """
        ak_symbol = self._convert_symbol(symbol)

        for attempt in range(retry):
            try:
                # 使用可用的接口
                df = self.ak.stock_zh_a_daily(
                    symbol=ak_symbol,
                    adjust="qfq"
                )

                if df is None or df.empty:
                    if attempt < retry - 1:
                        time.sleep(1)
                        continue
                    return None

                # 重命名列（中文列名转英文）
                column_map = {
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

                # 过滤日期范围（保留最近 days 天）
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                    cutoff_date = datetime.now() - timedelta(days=days)
                    df = df[df['date'] >= cutoff_date]

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
        skip_downloaded: bool = True
    ):
        """批量下载"""
        to_download = []
        skipped = 0

        for symbol in symbols:
            if skip_downloaded and symbol in self.progress["downloaded"]:
                skipped += 1
                continue
            to_download.append(symbol)

        if not to_download:
            print(f"没有需要下载的股票（跳过 {skipped} 只已下载）")
            return 0, 0

        print(f"准备下载 {len(to_download)} 只股票（跳过 {skipped} 只）")
        print("=" * 60)

        success = 0
        failed = 0

        for i, symbol in enumerate(to_download, 1):
            # 检查文件
            output_file = self.output_dir / f"stock_{symbol}.csv"
            if output_file.exists() and skip_downloaded:
                if i % 50 == 0:
                    print(f"[{i}/{len(to_download)}] 跳过 {symbol}")
                continue

            # 下载
            df = self.download_klines(symbol, days)

            if df is not None and not df.empty:
                df.to_csv(output_file, index=False, encoding='utf-8-sig')
                self.progress["downloaded"].add(symbol)
                if symbol in self.progress["failed"]:
                    self.progress["failed"].remove(symbol)
                success += 1

                if i % 10 == 0 or i == len(to_download):
                    print(f"[{i}/{len(to_download)}] {symbol}: OK {len(df)} 行")
                else:
                    print(f"[{i}/{len(to_download)}] {symbol}: OK {len(df)} 行")
            else:
                self.progress["failed"].add(symbol)
                failed += 1
                print(f"[{i}/{len(to_download)}] {symbol}: FAIL")

            # 延迟
            if i < len(to_download):
                time.sleep(0.2)

            # 定期保存
            if i % 20 == 0:
                self._save_progress()

        self._save_progress()

        print("\n" + "=" * 60)
        print(f"完成! 成功: {success}, 失败: {failed}")
        print(f"总计: 已下载 {len(self.progress['downloaded'])}, "
              f"失败 {len(self.progress['failed'])}")

        return success, failed

    def show_status(self):
        """显示状态"""
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

        print("=" * 60)


if __name__ == "__main__":
    import sys

    downloader = AkshareDownloader()

    if len(sys.argv) > 1:
        # 下载单只
        symbol = sys.argv[1]
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 365

        df = downloader.download_klines(symbol, days)
        if df is not None:
            print(f"\n{symbol}: {len(df)} 行")
            print(df.tail())

            output_path = downloader.output_dir / f"stock_{symbol}.csv"
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"已保存: {output_path}")
        else:
            print("下载失败")
    else:
        # 批量下载
        import json
        with open('data/stock_list.json', 'r', encoding='utf-8') as f:
            stocks = json.load(f)

        symbols = [s['code'] for s in stocks if s.get('code')]
        print(f"股票列表: {len(symbols)} 只")

        downloader.show_status()
        downloader.download_batch(symbols, days=365)
        downloader.show_status()
