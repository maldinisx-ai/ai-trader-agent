# -*- coding: utf-8 -*-
"""
下载主要A股历史K线数据

使用 akshare 下载主要股票的历史K线数据
"""

import os
import sys
import io
import time
from pathlib import Path
from datetime import datetime, timedelta

# 设置UTF-8编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 禁用所有代理
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

import requests
requests.Session.trust_env = False

import akshare as ak
import pandas as pd


# 主要股票列表
MAJOR_STOCKS = [
    # 上证50
    ('600519', '贵州茅台'),
    ('600036', '招商银行'),
    ('601318', '中国平安'),
    ('600900', '长江电力'),
    ('601012', '隆基绿能'),
    ('600030', '中信证券'),
    ('601166', '兴业银行'),
    ('600276', '恒瑞医药'),
    ('600887', '伊利股份'),
    ('601888', '中国中免'),

    # 深圳成指
    ('000001', '平安银行'),
    ('000002', '万科A'),
    ('000333', '美的集团'),
    ('000651', '格力电器'),
    ('000858', '五粮液'),
    ('002594', '比亚迪'),
    ('300059', '东方财富'),
    ('300015', '爱尔眼科'),
    ('300750', '宁德时代'),
    ('002475', '立讯精密'),

    # 科创板
    ('688981', '中芯国际'),
    ('688111', '金山办公'),
    ('688599', '天合光能'),

    # 中证500
    ('600809', '山西汾酒'),
    ('000568', '泸州老窖'),
    ('002304', '洋河股份'),
    ('603259', '药明康德'),
    ('600438', '通威股份'),

    # 中证1000
    ('300760', '迈瑞医疗'),
    ('002841', '视源股份'),
    ('300274', '阳光电源'),
]


def download_stock_kline(code, name, data_dir, days=365, max_retries=3):
    """下载单只股票K线数据 - 带重试"""
    for attempt in range(max_retries):
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq"
            )

            if df.empty:
                return {'success': False, 'error': '无数据'}

            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume',
                '成交额': 'amount'
            })

            df = df[['date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            df = df.tail(days)

            output_file = data_dir / f'stock_{code}.csv'
            df.to_csv(output_file, index=False, encoding='utf-8-sig')

            return {
                'success': True,
                'count': len(df),
                'start': df['date'].min(),
                'end': df['date'].max()
            }

        except Exception as e:
            if attempt < max_retries - 1:
                # 重试前等待更长时间
                time.sleep(2 * (attempt + 1))
                continue
            return {'success': False, 'error': str(e)}


def main():
    """主函数"""
    print("=" * 60)
    print("主要A股数据下载工具")
    print("=" * 60)
    print()

    DAYS = 365
    DELAY = 2  # 延迟2秒避免请求过快

    data_dir = PROJECT_ROOT / 'data' / 'stocks'
    data_dir.mkdir(parents=True, exist_ok=True)

    print(f"准备下载 {len(MAJOR_STOCKS)} 只主要股票的K线数据")
    print(f"数据保存目录: {data_dir}")
    print(f"时间范围: 最近 {DAYS} 天")
    print()

    success_count = 0
    fail_count = 0
    errors = {}

    for i, (code, name) in enumerate(MAJOR_STOCKS):
        print(f"[{i+1}/{len(MAJOR_STOCKS)}] {code} {name}...", end=' ', flush=True)

        result = download_stock_kline(code, name, data_dir, DAYS)

        if result['success']:
            print(f"OK ({result['count']}条)")
            success_count += 1
        else:
            print(f"FAIL ({result['error']})")
            fail_count += 1
            errors[code] = result['error']

        time.sleep(DELAY)

    print("\n" + "=" * 60)
    print("下载完成！")
    print("=" * 60)
    print(f"总股票数: {len(MAJOR_STOCKS)}")
    print(f"成功: {success_count}")
    print(f"失败: {fail_count}")
    print(f"成功率: {success_count/len(MAJOR_STOCKS)*100:.1f}%")

    if fail_count > 0:
        print(f"\n失败股票:")
        for code, error in errors.items():
            print(f"  {code}: {error}")

    final_size = sum(f.stat().st_size for f in data_dir.glob('stock_*.csv'))
    print(f"\n数据目录大小: {final_size / 1024:.1f} KB")


if __name__ == '__main__':
    main()
