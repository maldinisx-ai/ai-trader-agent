# -*- coding: utf-8 -*-
"""
Pytdx 数据下载器

基于通达信行情服务器的稳定数据源。
特点：免费、无需Token、直连服务器、无代理问题。
"""

import logging
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class PytdxDownloader:
    """通达信数据下载器"""

    # 通达信服务器列表（多服务器自动切换）
    DEFAULT_HOSTS = [
        ("119.147.212.81", 7709),  # 深圳
        ("112.74.214.43", 7727),   # 深圳
        ("221.231.141.60", 7709),  # 上海
        ("101.227.73.20", 7709),   # 上海
        ("101.227.77.254", 7709),  # 上海
        ("14.215.128.18", 7709),   # 广州
        ("59.173.18.140", 7709),   # 武汉
        ("180.153.39.51", 7709),   # 杭州
    ]

    def __init__(self, hosts: Optional[List[Tuple[str, int]]] = None):
        """
        初始化下载器

        Args:
            hosts: 服务器列表，默认使用内置列表
        """
        self._hosts = hosts or self.DEFAULT_HOSTS
        self._api = None
        self._current_host_idx = 0

    def _get_api(self):
        """延迟加载 pytdx"""
        try:
            from pytdx.hq import TdxHq_API
            return TdxHq_API
        except ImportError:
            raise RuntimeError("pytdx 未安装，请运行: pip install pytdx")

    @contextmanager
    def _connect(self):
        """连接上下文管理器（自动重连和断开）"""
        TdxHq_API = self._get_api()
        api = TdxHq_API()
        connected = False

        try:
            # 尝试连接服务器
            for i in range(len(self._hosts)):
                host_idx = (self._current_host_idx + i) % len(self._hosts)
                host, port = self._hosts[host_idx]

                try:
                    if api.connect(host, port, time_out=5):
                        connected = True
                        self._current_host_idx = host_idx
                        logger.debug(f"连接成功: {host}:{port}")
                        break
                except Exception as e:
                    logger.debug(f"连接 {host}:{port} 失败: {e}")
                    continue

            if not connected:
                raise RuntimeError("无法连接任何通达信服务器")

            yield api

        finally:
            try:
                api.disconnect()
            except Exception:
                pass

    def _get_market_code(self, stock_code: str) -> Tuple[int, str]:
        """
        根据代码判断市场

        Returns:
            (market, code) 其中 market=0深圳, 1上海
        """
        code = stock_code.strip()
        code = code.replace('.SH', '').replace('.SZ', '')
        code = code.replace('.sh', '').replace('.sz', '')

        # 上海：60xxxx, 68xxxx
        if code.startswith(('60', '68')):
            return 1, code
        else:
            return 0, code

    def get_stock_list(self, market: int = None) -> List[dict]:
        """
        获取股票列表

        Args:
            market: 市场代码 (0=深圳, 1=上海, None=全部)

        Returns:
            [{'code': '000001', 'name': '平安银行'}, ...]
        """
        stocks = []

        with self._connect() as api:
            markets = [market] if market is not None else [0, 1]

            for m in markets:
                start = 0
                while True:
                    data = api.get_security_list(m, start) or []
                    stocks.extend([
                        {'code': s['code'], 'name': s['name']}
                        for s in data if s.get('code') and s.get('name')
                    ])

                    if len(data) < 1000:  # 每页最多1000条
                        break
                    start += 1000

        return stocks

    def download_klines(
        self,
        symbol: str,
        days: int = 365,
        category: int = 9
    ) -> Optional[pd.DataFrame]:
        """
        下载K线数据

        Args:
            symbol: 股票代码
            days: 天数
            category: K线类型 (9=日线, 0=5分钟, 5=1分钟)

        Returns:
            DataFrame with columns: datetime, open, high, low, close, volume, amount
        """
        market, code = self._get_market_code(symbol)

        # 计算请求数量
        count = min(max(days * 5 // 7 + 20, 100), 800)

        try:
            with self._connect() as api:
                data = api.get_security_bars(
                    category=category,
                    market=market,
                    code=code,
                    start=0,
                    count=count
                )

                if not data:
                    return None

                df = api.to_df(data)
                df['datetime'] = pd.to_datetime(df['datetime'])

                # 过滤日期范围
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
                df = df[df['datetime'] >= start_date]

                # 添加股票代码
                df['symbol'] = symbol

                return df

        except Exception as e:
            logger.error(f"下载 {symbol} 失败: {e}")
            return None

    def download_batch(
        self,
        symbols: List[str],
        output_dir: str = "data/stocks",
        days: int = 365
    ):
        """
        批量下载

        Args:
            symbols: 股票代码列表
            output_dir: 输出目录
            days: 天数
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        success = 0
        failed = 0

        for i, symbol in enumerate(symbols, 1):
            df = self.download_klines(symbol, days)

            if df is not None and not df.empty:
                output_file = output_path / f"stock_{symbol}.csv"
                df.to_csv(output_file, index=False, encoding='utf-8-sig')
                success += 1
                print(f"[{i}/{len(symbols)}] {symbol}: 成功 ({len(df)} 行)")
            else:
                failed += 1
                print(f"[{i}/{len(symbols)}] {symbol}: 失败")

            # 延迟避免请求过快
            if i < len(symbols):
                time.sleep(0.1)

        print(f"\n下载完成! 成功: {success}, 失败: {failed}")

    def get_realtime_quote(self, symbol: str) -> Optional[dict]:
        """
        获取实时行情

        Args:
            symbol: 股票代码

        Returns:
            行情字典
        """
        market, code = self._get_market_code(symbol)

        try:
            with self._connect() as api:
                data = api.get_security_quotes([(market, code)])

                if data and len(data) > 0:
                    quote = data[0]
                    return {
                        'symbol': symbol,
                        'name': quote.get('name', ''),
                        'price': quote.get('price', 0),
                        'open': quote.get('open', 0),
                        'high': quote.get('high', 0),
                        'low': quote.get('low', 0),
                        'pre_close': quote.get('last_close', 0),
                        'volume': quote.get('vol', 0),
                        'amount': quote.get('amount', 0),
                        'timestamp': datetime.now().isoformat()
                    }
        except Exception as e:
            logger.error(f"获取 {symbol} 行情失败: {e}")

        return None


def download_all_stocks(limit: int = None, days: int = 365):
    """
    下载所有A股数据

    Args:
        limit: 限制下载数量（None=全部）
        days: 天数
    """
    downloader = PytdxDownloader()

    print("获取股票列表...")
    all_stocks = downloader.get_stock_list()

    if limit:
        all_stocks = all_stocks[:limit]

    print(f"共 {len(all_stocks)} 只股票，开始下载...")

    symbols = [s['code'] for s in all_stocks]
    downloader.download_batch(symbols, days=days)


if __name__ == "__main__":
    import sys

    # 测试单只股票
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 365

        downloader = PytdxDownloader()
        df = downloader.download_klines(symbol, days)

        if df is not None:
            print(f"\n{symbol} 数据下载成功:")
            print(df.tail())
            print(f"\n保存到: data/stocks/stock_{symbol}.csv")

            output_path = Path("data/stocks")
            output_path.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_path / f"stock_{symbol}.csv", index=False)
        else:
            print(f"下载失败")
    else:
        # 下载前100只
        download_all_stocks(limit=100, days=365)
