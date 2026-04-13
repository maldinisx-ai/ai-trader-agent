"""
将股票K线数据转换为按股票-日期组织的格式

输入：data/stocks/000001_SZ.csv (每只股票一个文件)
输出：data/by_stock/000001_SZ/000001_SZ_2011-04-01.csv (每个股票一个目录，每天一个文件)
"""

import pandas as pd
import os
from pathlib import Path
from datetime import datetime
from tqdm import tqdm


def convert_to_daily_format(
    stocks_dir: str = "data/stocks",
    output_dir: str = "data/by_stock",
    min_stocks_per_day: int = 10
):
    """
    将股票数据转换为按股票-日期组织的格式

    Args:
        stocks_dir: 股票数据目录
        output_dir: 输出目录
        min_stocks_per_day: 每天至少包含的股票数（少于则跳过）- 此参数已废弃
    """
    stocks_path = Path(stocks_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 1. 读取所有K线文件
    print(f"[1/4] 扫描K线文件: {stocks_dir}")
    kline_files = []
    for f in stocks_path.glob("*.csv"):
        # 只处理K线文件（格式：000001_SZ.csv，只有1个下划线）
        if '_' in f.name and f.name.count('_') == 1:
            code = f.name.split('_')[0]
            if len(code) == 6 and code.isdigit():
                kline_files.append(f)

    print(f"找到 {len(kline_files)} 个K线文件")

    if not kline_files:
        print("[ERROR] 没有找到K线文件，请先下载数据")
        return

    # 2. 读取所有数据并按日期分组
    print(f"\n[2/4] 读取数据并按日期分组...")
    date_data = {}  # {date: [df1, df2, ...]}

    for file_path in tqdm(kline_files, desc="读取文件"):
        try:
            df = pd.read_csv(file_path)

            # 标准化列名
            if 'trade_date' in df.columns:
                df = df.rename(columns={'trade_date': 'date'})

            if 'date' not in df.columns:
                continue

            # 确保有code列（股票代码）
            if 'code' not in df.columns:
                # 从文件名提取
                code = file_path.stem.replace('_', '.')
                df['code'] = code

            # 转换日期
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            # 按日期分组
            for date, group in df.groupby('date'):
                if date not in date_data:
                    date_data[date] = []
                date_data[date].append(group)

        except Exception as e:
            print(f"[WARN] 读取失败 {file_path.name}: {e}")
            continue

    print(f"共 {len(date_data)} 个交易日")

    # 3. 按股票和日期组织数据
    print(f"\n[3/4] 按股票和日期组织数据...")
    valid_dates = set()

    # 先收集所有日期
    for date in date_data.keys():
        valid_dates.add(date)

    # 按股票分目录保存
    for file_path in tqdm(kline_files, desc="处理文件"):
        try:
            df = pd.read_csv(file_path)

            # 提取股票代码
            code = file_path.stem  # 如 000001_SZ

            # 创建该股票的目录
            stock_dir = output_path / code
            stock_dir.mkdir(parents=True, exist_ok=True)

            # 标准化列名
            if 'trade_date' in df.columns:
                df = df.rename(columns={'trade_date': 'date'})

            if 'date' not in df.columns:
                continue

            # 确保有code列
            if 'code' not in df.columns:
                df['code'] = code.replace('_', '.')

            # 转换日期
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            # 按日期保存每个文件
            for date, group in df.groupby('date'):
                output_file = stock_dir / f"{code}_{date}.csv"
                group.to_csv(output_file, index=False, encoding='utf-8-sig')

        except Exception as e:
            print(f"[WARN] 处理失败 {file_path.name}: {e}")
            continue

    print(f"处理完成")

    print(f"有效交易日: {len(valid_dates)}")

    # 4. 生成日期索引
    print(f"\n[4/4] 生成日期索引...")
    index_file = output_path / "date_index.json"

    import json
    date_index = {
        "start_date": valid_dates[0] if valid_dates else None,
        "end_date": valid_dates[-1] if valid_dates else None,
        "total_days": len(valid_dates),
        "dates": valid_dates
    }

    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(date_index, f, ensure_ascii=False, indent=2)

    print(f"\n[SUCCESS] 转换完成!")
    print(f"  输出目录: {output_dir}")
    print(f"  日期范围: {date_index['start_date']} 至 {date_index['end_date']}")
    print(f"  交易日数: {date_index['total_days']}")


def load_daily_data(date: str, data_dir: str = "data/by_date") -> pd.DataFrame:
    """
    加载指定日期的数据

    Args:
        date: 日期字符串 (格式: YYYY-MM-DD)
        data_dir: 数据目录

    Returns:
        当天所有股票的数据
    """
    file_path = Path(data_dir) / f"{date}.csv"

    if not file_path.exists():
        raise FileNotFoundError(f"找不到 {date} 的数据文件")

    return pd.read_csv(file_path)


def get_all_dates(data_dir: str = "data/by_date") -> list:
    """
    获取所有可用的交易日期

    Returns:
        排序后的日期列表
    """
    index_file = Path(data_dir) / "date_index.json"

    if index_file.exists():
        import json
        with open(index_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data['dates']
    else:
        # 扫描目录
        dates = []
        for f in Path(data_dir).glob("*.csv"):
            if f.name != "date_index.json":
                dates.append(f.stem)
        return sorted(dates)


if __name__ == "__main__":
    convert_to_daily_format()
