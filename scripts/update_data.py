# -*- coding: utf-8 -*-
"""
数据更新脚本 - 获取前一日真实数据

用法:
    python scripts/update_data.py                    # 获取昨日数据
    python scripts/update_data.py --date 2024-03-22  # 获取指定日期
    python scripts/update_data.py --index csi300      # 获取沪深300成分股
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

try:
    import akshare as ak
except ImportError:
    print("错误: 需要安装 akshare")
    print("安装命令: pip install akshare")
    sys.exit(1)


def fetch_stock_data(date: str, symbols: list[str] = None) -> dict:
    """
    获取股票数据

    Args:
        date: 日期 (YYYY-MM-DD)
        symbols: 股票代码列表（None表示全部A股）

    Returns:
        dict: {symbol: data}
    """
    print(f"[INFO] 正在获取 {date} 的股票数据...")

    data = {}

    if symbols:
        # 获取指定股票数据
        for i, symbol in enumerate(symbols, 1):
            try:
                df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=date.replace("-", ""),
                    end_date=date.replace("-", ""),
                    adjust="qfq"
                )
                if not df.empty:
                    data[symbol] = df
                print(f"[INFO] [{i}/{len(symbols)}] {symbol}: {len(df)} 条记录")
            except Exception as e:
                print(f"[WARN] {symbol}: 获取失败 - {e}")
    else:
        # 获取全部A股（实际生产环境需要分批处理）
        print("[INFO] 获取全部A股数据（前100只用于测试）...")
        try:
            # 获取股票列表
            stock_list = ak.stock_zh_a_spot_em()
            symbols = stock_list['代码'].head(100).tolist()

            for i, symbol in enumerate(symbols, 1):
                try:
                    df = ak.stock_zh_a_hist(
                        symbol=symbol,
                        period="daily",
                        start_date=date.replace("-", ""),
                        end_date=date.replace("-", ""),
                        adjust="qfq"
                    )
                    if not df.empty:
                        data[symbol] = df
                    print(f"[INFO] [{i}/{len(symbols)}] {symbol}: {len(df)} 条记录")
                except Exception as e:
                    print(f"[WARN] {symbol}: 获取失败 - {e}")
        except Exception as e:
            print(f"[ERROR] 获取股票列表失败: {e}")

    print(f"[INFO] 成功获取 {len(data)} 只股票数据")
    return data


def save_to_csv(data: dict, output_dir: Path, date: str):
    """
    保存数据到CSV文件

    Args:
        data: 股票数据字典
        output_dir: 输出目录
        date: 日期
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # 合并所有数据到一个CSV
    all_data = []
    for symbol, df in data.items():
        df = df.copy()
        df['symbol'] = symbol
        all_data.append(df)

    if all_data:
        import pandas as pd
        combined_df = pd.concat(all_data, ignore_index=True)

        # 保存到文件
        output_file = output_dir / f"{date}.csv"
        combined_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"[INFO] 数据已保存到: {output_file}")

        # 更新索引文件
        index_file = output_dir.parent / "latest.json"
        import json
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump({
                "latest_date": date,
                "data_file": str(output_file.relative_to(output_dir.parent)),
                "symbols": list(data.keys()),
                "update_time": datetime.now().isoformat(),
            }, f, indent=2, ensure_ascii=False)
        print(f"[INFO] 索引文件已更新: {index_file}")

        return True
    else:
        print("[WARN] 没有数据可保存")
        return False


def get_csi300_symbols() -> list[str]:
    """
    获取沪深300成分股代码

    Returns:
        股票代码列表
    """
    print("[INFO] 获取沪深300成分股...")
    try:
        df = ak.index_stock_cons(symbol="沪深300")
        return df['品种代码'].tolist()
    except Exception as e:
        print(f"[WARN] 获取沪深300成分股失败: {e}")
        return []


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="更新股票数据")
    parser.add_argument("--date", type=str, help="日期 (YYYY-MM-DD)，默认为昨日")
    parser.add_argument("--index", type=str, help="指数代码 (如 csi300)")
    parser.add_argument("--output", type=str, default="data/quotes", help="输出目录")

    args = parser.parse_args()

    # 确定日期
    if args.date:
        target_date = args.date
    else:
        # 获取昨天的日期
        yesterday = datetime.now() - timedelta(days=1)
        # 跳过周末
        while yesterday.weekday() >= 5:
            yesterday -= timedelta(days=1)
        target_date = yesterday.strftime("%Y-%m-%d")

    print(f"[INFO] 目标日期: {target_date}")

    # 确定股票列表
    symbols = None
    if args.index:
        symbols = get_csi300_symbols()
        print(f"[INFO] 使用 {args.index} 成分股，共 {len(symbols)} 只股票")

    # 获取数据
    data = fetch_stock_data(target_date, symbols)

    # 保存数据
    output_dir = Path(args.output)
    success = save_to_csv(data, output_dir, target_date)

    if success:
        print("[SUCCESS] 数据更新完成")
        return 0
    else:
        print("[ERROR] 数据更新失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
