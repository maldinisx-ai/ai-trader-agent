#!/usr/bin/env python3
"""使用 akshare 下载全市场股票数据"""

import akshare as ak
import pandas as pd
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class AkshareDownloader:
    def __init__(self, data_dir='data'):
        self.data_dir = Path(data_dir)
        self.stocks_dir = self.data_dir / 'stocks'
        self.financial_dir = self.data_dir / 'financial'
        self.fundamentals_dir = self.data_dir / 'fundamentals'
        self.money_flow_dir = self.data_dir / 'money_flow'

        for d in [self.stocks_dir, self.financial_dir,
                  self.fundamentals_dir, self.money_flow_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.progress_file = self.data_dir / 'akshare_progress.json'
        self.load_progress()

    def load_progress(self):
        if self.progress_file.exists():
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                self.progress = json.load(f)
        else:
            self.progress = {
                'downloaded': [],
                'failed': [],
                'last_update': None
            }

    def save_progress(self):
        self.progress['last_update'] = datetime.now().isoformat()
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(self.progress, f, indent=2, ensure_ascii=False)

    def download_stock_history(self, symbol: str, retry=3) -> bool:
        """下载K线数据"""
        code = symbol.split('.')[0]
        filename = self.stocks_dir / f'{symbol.replace(".", "_")}.csv'

        if filename.exists():
            return True

        for i in range(retry):
            try:
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date="20240326",
                    end_date=datetime.now().strftime("%Y%m%d"),
                    adjust="qfq"
                )
                if df is not None and not df.empty:
                    df.to_csv(filename, index=False, encoding='utf-8')
                    return True
            except Exception as e:
                logger.warning(f'  重试 {i+1}/{retry}: {e}')
                time.sleep(2)
        return False

    def download_stock_money_flow(self, symbol: str, retry=2) -> bool:
        """下载资金流向数据"""
        code = symbol.split('.')[0]
        filename = self.money_flow_dir / f'{symbol.replace(".", "_")}.csv'

        if filename.exists():
            return True

        for i in range(retry):
            try:
                df = ak.stock_individual_fund_flow(
                    stock=code,
                    market="sh" if symbol.endswith('.SH') else "sz"
                )
                if df is not None and not df.empty:
                    df.to_csv(filename, index=False, encoding='utf-8')
                    return True
            except Exception as e:
                logger.warning(f'  资金流重试 {i+1}/{retry}: {e}')
                time.sleep(1)
        return False

    def download_stock_financial(self, symbol: str, retry=2) -> bool:
        """下载财务指标"""
        code = symbol.split('.')[0]
        filename = self.fundamentals_dir / f'{symbol.replace(".", "_")}_indicators.csv'

        if filename.exists():
            return True

        for i in range(retry):
            try:
                df = ak.stock_financial_analysis_indicator(symbol=code)
                if df is not None and not df.empty:
                    df.to_csv(filename, index=False, encoding='utf-8')
                    return True
            except Exception as e:
                logger.warning(f'  财务指标重试 {i+1}/{retry}: {e}')
                time.sleep(1)
        return False

    def download_stock(self, symbol: str) -> dict:
        """下载单只股票所有数据"""
        results = {'kline': False, 'money_flow': False, 'financial': False}

        # K线
        if self.download_stock_history(symbol):
            results['kline'] = True
        else:
            logger.warning(f'  K线失败: {symbol}')

        time.sleep(0.5)

        # 资金流向
        if self.download_stock_money_flow(symbol):
            results['money_flow'] = True
        time.sleep(0.3)

        # 财务指标
        if self.download_stock_financial(symbol):
            results['financial'] = True

        return results

    def download_all(self, symbols: list, limit=None):
        """下载所有股票"""
        total = len(symbols) if limit is None else min(limit, len(symbols))
        logger.info(f'开始下载 {total} 只股票数据')

        success = 0
        failed = 0

        for i, symbol in enumerate(symbols[:total] if limit else symbols, 1):
            if symbol in self.progress['downloaded']:
                continue

            logger.info(f'[{i}/{total}] 处理 {symbol}...')

            results = self.download_stock(symbol)

            if any(results.values()):
                self.progress['downloaded'].append(symbol)
                success += 1
            else:
                self.progress['failed'].append(symbol)
                failed += 1

            # 每100只保存一次进度
            if i % 100 == 0:
                self.save_progress()
                logger.info(f'进度: 成功 {success}, 失败 {failed}')

            time.sleep(0.5)  # 避免请求过快

        self.save_progress()
        logger.info(f'\\n完成! 成功: {success}, 失败: {failed}')


def main():
    # 加载股票列表
    with open('data/all_stocks.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    symbols = data['codes']

    print(f'总计 {len(symbols)} 只股票')

    # 可以设置 limit 限制下载数量
    limit = None  # 或设置数字如 500

    downloader = AkshareDownloader()
    downloader.download_all(symbols, limit=limit)


if __name__ == '__main__':
    main()
