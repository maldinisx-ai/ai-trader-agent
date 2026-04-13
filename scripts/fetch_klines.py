# -*- coding: utf-8 -*-
"""
获取历史K线数据 - 修复版

用法:
    python scripts/fetch_klines.py 600519              # 获取贵州茅台
    python scripts/fetch_klines.py 600519 --days 365   # 获取最近365天
    python scripts/fetch_klines.py 600519 --output custom.csv
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# 禁用所有代理
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

# 猴子补丁：禁用 curl_cffi 的代理
import curl_cffi.requests as curl_requests

_original_request = curl_requests.Session.request

def _patched_request(self, method, url, **kwargs):
    # 强制禁用代理
    kwargs['proxies'] = {}
    return _original_request(self, method, url, **kwargs)

curl_requests.Session.request = _patched_request

try:
    import akshare as ak
    import pandas as pd
except ImportError:
    print("错误: 需要安装 akshare 和 pandas")
    print("安装命令: pip install akshare pandas")
    sys.exit(1)


def fetch_kline_data(symbol: str, days: int = 365) -> pd.DataFrame:
    """
    获取历史K线数据

    Args:
        symbol: 股票代码 (如 '600519')
        days: 获取天数

    Returns:
        pd.DataFrame: K线数据
    """
    print(f"[INFO] 正在获取 {symbol} 的历史K线数据（最近{days}天）...")

    try:
        # 计算日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # 使用 akshare 获取历史数据
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust="qfq"  # 前复权
        )

        if df.empty:
            print(f"[WARN] 未获取到数据，请检查股票代码: {symbol}")
            return None

        # 重命名列
        df = df.rename(columns={
            '日期': 'date',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume',
            '成交额': 'amount',
            '涨跌幅': 'change_pct',
            '涨跌额': 'change_amount',
            '换手率': 'turnover'
        })

        # 选择需要的列
        columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']
        if 'change_pct' in df.columns:
            columns.append('change_pct')
        if 'change_amount' in df.columns:
            columns.append('change_amount')
        if 'turnover' in df.columns:
            columns.append('turnover')

        df = df[columns]

        # 转换日期类型
        df['date'] = pd.to_datetime(df['date'])

        print(f"[SUCCESS] 成功获取 {len(df)} 条K线数据")
        print(f"[INFO] 时间范围: {df['date'].min()} 到 {df['date'].max()}")

        return df

    except Exception as e:
        print(f"[ERROR] 获取数据失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def save_kline_data(df: pd.DataFrame, symbol: str, output_file: Path = None):
    """
    保存K线数据

    Args:
        df: K线数据
        symbol: 股票代码
        output_file: 输出文件路径
    """
    if df is None or df.empty:
        print("[WARN] 没有数据可保存")
        return False

    if output_file is None:
        output_dir = Path("data")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"klines_{symbol}.csv"

    # 保存到CSV
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"[INFO] 数据已保存到: {output_file}")

    return True


def display_summary(df: pd.DataFrame, count: int = 5):
    """
    显示数据摘要

    Args:
        df: K线数据
        count: 显示行数
    """
    if df is None or df.empty:
        return

    print(f"\n{'='*60}")
    print(f"数据摘要 (最近{count}天)")
    print(f"{'='*60}")

    display_df = df.tail(count).copy()
    for col in ['open', 'high', 'low', 'close']:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f'{x:.2f}')

    print(display_df.to_string(index=False))

    # 统计信息
    print(f"\n{'='*60}")
    print("统计信息")
    print(f"{'='*60}")
    print(f"最高价: {df['high'].max():.2f}")
    print(f"最低价: {df['low'].min():.2f}")
    print(f"平均成交量: {df['volume'].mean():.0f}")
    if 'change_pct' in df.columns:
        print(f"最大涨幅: {df['change_pct'].max():.2f}%")
        print(f"最大跌幅: {df['change_pct'].min():.2f}%")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="获取历史K线数据")
    parser.add_argument("symbol", type=str, help="股票代码 (如 600519)")
    parser.add_argument("--days", type=int, default=365, help="获取天数（默认365）")
    parser.add_argument("--output", type=str, help="输出文件路径")

    args = parser.parse_args()

    # 获取数据
    df = fetch_kline_data(args.symbol, args.days)

    if df is not None:
        # 显示摘要
        display_summary(df)

        # 保存数据
        output_file = Path(args.output) if args.output else None
        save_kline_data(df, args.symbol, output_file)

        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
