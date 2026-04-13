# -*- coding: utf-8 -*-
"""
下载所有A股历史K线数据 - 使用 akshare
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

# 设置 NO_PROXY
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

# 禁用 requests 的代理
import requests
requests.Session.trust_env = False

import akshare as ak
import pandas as pd


def get_all_stocks():
    """获取所有A股股票列表 - 使用 akshare"""
    print("正在获取A股股票列表...")

    try:
        # 使用 akshare 获取A股列表
        df = ak.stock_zh_a_spot_em()

        if df.empty:
            print("未获取到股票数据")
            return []

        print(f"DEBUG: API返回 {len(df)} 只股票")
        # 显示前5只股票
        for i in range(min(5, len(df))):
            print(f"DEBUG: 股票{i+1} 代码={df.iloc[i]['代码']}, 名称={df.iloc[i]['名称']}")

        stocks = []
        for _, row in df.iterrows():
            code = str(row['代码'])
            name = row['名称']

            # 过滤真正的A股代码
            # 上海: 600xxx, 601xxx, 603xxx, 605xxx, 688xxx(科创板)
            # 深圳: 000xxx, 001xxx, 002xxx, 300xxx(创业板)
            is_sh_a = (code.startswith('60') and not code.startswith('609'))
            is_sz_a = (code.startswith('00') or code.startswith('30'))
            is_star = code.startswith('688')

            if is_sh_a or is_sz_a or is_star:
                stocks.append({
                    'code': code,
                    'name': name,
                })

        print(f"成功获取 {len(stocks)} 只A股股票")
        return stocks

    except Exception as e:
        print(f"获取股票列表失败: {e}")
        import traceback
        traceback.print_exc()

        return []


def download_stock_kline(code, name, data_dir, days=365):
    """下载单只股票K线数据 - 使用 akshare"""
    try:
        # 计算日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # 使用 akshare 获取历史数据
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust="qfq"  # 前复权
        )

        if df.empty:
            return {'success': False, 'error': '无数据'}

        # 重命名列
        df = df.rename(columns={
            '日期': 'date',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume',
            '成交额': 'amount'
        })

        # 选择需要的列
        df = df[['date', 'open', 'high', 'low', 'close', 'volume', 'amount']]

        # 转换日期类型
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # 只保留最近N天
        df = df.tail(days)

        # 保存
        output_file = data_dir / f'stock_{code}.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')

        return {
            'success': True,
            'count': len(df),
            'start': df['date'].min(),
            'end': df['date'].max()
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


def main():
    """主函数"""
    print("=" * 60)
    print("A股全市场数据下载工具")
    print("=" * 60)
    print()

    # 配置
    DAYS = 365  # 下载最近1年数据
    BATCH_SIZE = 50  # 每批处理50只
    DELAY = 0.5  # 请求间隔（秒）- 增加延迟避免连接被关闭

    # 创建数据目录
    data_dir = PROJECT_ROOT / 'data' / 'stocks'
    data_dir.mkdir(parents=True, exist_ok=True)

    # 获取股票列表
    stocks = get_all_stocks()
    if not stocks:
        print("无法获取股票列表，退出")
        return

    print(f"\n准备下载 {len(stocks)} 只股票的K线数据")
    print(f"数据保存目录: {data_dir}")
    print(f"时间范围: 最近 {DAYS} 天")
    print(f"预计总大小: ~{len(stocks) * 20 / 1024:.1f} MB")
    print()
    print("开始下载...")

    # 统计
    success_count = 0
    fail_count = 0
    errors = {}

    # 批量下载
    total_batches = (len(stocks) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(total_batches):
        start_idx = batch_idx * BATCH_SIZE
        end_idx = min((batch_idx + 1) * BATCH_SIZE, len(stocks))
        batch = stocks[start_idx:end_idx]

        print(f"\n--- 批次 {batch_idx + 1}/{total_batches} (股票 {start_idx + 1}-{end_idx}) ---")

        for i, stock in enumerate(batch):
            code = stock['code']
            name = stock['name']
            idx = start_idx + i + 1

            # 显示进度
            print(f"[{idx}/{len(stocks)}] {code} {name}...", end=' ', flush=True)

            result = download_stock_kline(code, name, data_dir, DAYS)

            if result['success']:
                print(f"OK ({result['count']}条)")
                success_count += 1
            else:
                print(f"FAIL ({result['error']})")
                fail_count += 1
                errors[code] = result['error']

            # 延迟，避免请求过快
            time.sleep(DELAY)

        # 每批完成后显示统计
        print(f"\n进度: {end_idx}/{len(stocks)} ({end_idx/len(stocks)*100:.1f}%)")
        print(f"成功: {success_count}, 失败: {fail_count}")

    # 最终统计
    print("\n" + "=" * 60)
    print("下载完成！")
    print("=" * 60)
    print(f"总股票数: {len(stocks)}")
    print(f"成功: {success_count}")
    print(f"失败: {fail_count}")
    print(f"成功率: {success_count/len(stocks)*100:.1f}%")

    if fail_count > 0:
        print(f"\n失败股票示例 (前10只):")
        for i, (code, error) in enumerate(list(errors.items())[:10]):
            print(f"  {code}: {error}")

    # 显示目录大小
    final_size = sum(f.stat().st_size for f in data_dir.glob('stock_*.csv'))
    print(f"\n数据目录大小: {final_size / 1024 / 1024:.2f} MB")


if __name__ == '__main__':
    main()
