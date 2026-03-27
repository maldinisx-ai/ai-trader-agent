# -*- coding: utf-8 -*-
"""
下载所有主要大盘指数数据（增强版）
"""

import os
import sys
import io
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 禁用代理
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

from curl_cffi import requests as curl_requests
import pandas as pd


def download_index(code, name, secid_pattern):
    """下载单个指数数据"""
    try:
        url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
        params = {
            'secid': secid_pattern,
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58',
            'klt': '101',
            'fqt': '1',
            'beg': '0',
            'end': '20500101',
            'lmt': '1000'
        }

        session = curl_requests.Session()
        resp = session.get(url, params=params, timeout=30, proxies={}, impersonate='chrome')

        if resp.status_code == 200:
            result = resp.json()
            if result.get('rc') == 0 and 'data' in result:
                items = result['data']['klines']

                klines = []
                for item in items:
                    parts = item.split(',')
                    klines.append({
                        'date': parts[0],
                        'open': float(parts[1]),
                        'close': float(parts[2]),
                        'high': float(parts[3]),
                        'low': float(parts[4]),
                        'volume': int(parts[5]),
                        'amount': float(parts[6])
                    })

                df = pd.DataFrame(klines)
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date')
                df = df.tail(365)  # 最近1年

                # 保存
                data_dir = PROJECT_ROOT / 'data'
                data_dir.mkdir(exist_ok=True)
                output_file = data_dir / f'index_{code}.csv'
                df.to_csv(output_file, index=False, encoding='utf-8-sig')

                return {
                    'success': True,
                    'count': len(df),
                    'start': df['date'].min(),
                    'end': df['date'].max(),
                    'close': df['close'].iloc[-1]
                }
            else:
                return {'success': False, 'error': 'API返回错误'}
        else:
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def main():
    """主函数"""
    # 主要大盘指数配置
    indices = [
        ('000001', '上证指数', '0.000001'),
        ('000016', '上证50', '0.000016'),
        ('399001', '深证成指', '1.399001'),
        ('399006', '创业板指', '1.399006'),
        ('000300', '沪深300', '0.000300'),
        ('399303', '国证2000', '1.399303'),
        ('000905', '中证500', '0.000905'),
        ('000852', '中证1000', '0.000852'),
    ]

    print('=' * 60)
    print('下载大盘指数数据（8个主要指数）')
    print('=' * 60)
    print()

    results = {}
    for code, name, secid in indices:
        result = download_index(code, name, secid)
        results[code] = (name, result)

        if result['success']:
            print(f'[OK] {name}({code})')
            print(f'     数据: {result["count"]} 条')
            print(f'     范围: {result["start"]} 至 {result["end"]}')
            print(f'     最新: {result["close"]:.2f}')
        else:
            print(f'[FAIL] {name}({code}): {result["error"]}')
        print()

    # 汇总
    print('=' * 60)
    success_count = sum(1 for _, (_, r) in results.items() if r['success'])
    print(f'下载完成: {success_count}/{len(indices)} 成功')
    print('=' * 60)

    # 显示已下载的文件
    print('\n已下载的指数数据文件:')
    data_dir = PROJECT_ROOT / 'data'
    for f in sorted(data_dir.glob('index_*.csv')):
        df = pd.read_csv(f)
        print(f'  - {f.name}: {len(df)} 条, {df["date"].min()} 至 {df["date"].max()}')


if __name__ == '__main__':
    main()
