# -*- coding: utf-8 -*-
"""
数据更新脚本 - 修复版（绕过代理问题）

用法:
    python scripts/update_data_fixed.py              # 获取昨日数据（前100只）
    python scripts/update_data_fixed.py --count 300 # 获取指定数量
    python scripts/update_data_fixed.py --symbols 600519,000001  # 指定股票
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

try:
    import akshare as ak
except ImportError:
    print("错误: 需要安装 akshare")
    print("安装命令: pip install akshare")
    sys.exit(1)


def fetch_stock_data_direct(symbols: list[str]) -> dict:
    """
    直接获取股票数据（绕过代理问题）

    Args:
        symbols: 股票代码列表

    Returns:
        dict: {symbol: data}
    """
    from curl_cffi import requests as curl_requests

    data = {}

    # 获取实时行情接口
    url = "https://82.push2.eastmoney.com/api/qt/clist/get"
    params = {
        'pn': 1,
        'pz': 1000,  # 每页数量
        'po': 1,
        'np': 1,
        'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
        'fltt': 2,
        'invt': 2,
        'fid': 'f12',
        'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048',
        'fields': 'f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152'
    }

    print(f"[INFO] 正在获取股票数据...")

    try:
        session = curl_requests.Session()
        resp = session.get(url, params=params, timeout=30, proxies={}, impersonate='chrome')

        if resp.status_code == 200:
            import json
            result = resp.json()

            if result.get('rc') == 0 and 'data' in result:
                items = result['data']['diff']

                for item in items:
                    symbol = item.get('f12')  # 股票代码
                    name = item.get('f14')     # 股票名称

                    # 如果指定了股票列表，只获取这些股票
                    if symbols and symbol not in symbols:
                        continue

                    data[symbol] = {
                        'symbol': symbol,
                        'name': name,
                        'price': item.get('f2', 0),      # 最新价
                        'change': item.get('f3', 0),     # 涨跌幅
                        'change_amount': item.get('f4', 0),  # 涨跌额
                        'volume': item.get('f5', 0),     # 成交量
                        'amount': item.get('f6', 0),     # 成交额
                        'high': item.get('f15', 0),      # 最高
                        'low': item.get('f16', 0),       # 最低
                        'open': item.get('f17', 0),      # 今开
                        'close': item.get('f18', 0),     # 昨收
                        'timestamp': datetime.now()
                    }

                print(f"[INFO] 成功获取 {len(data)} 只股票数据")
                return data
        else:
            print(f"[ERROR] HTTP 状态码: {resp.status_code}")

    except Exception as e:
        print(f"[ERROR] 获取数据失败: {e}")

    return data


def save_to_json(data: dict, output_dir: Path):
    """
    保存数据到JSON文件

    Args:
        data: 股票数据字典
        output_dir: 输出目录
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if not data:
        print("[WARN] 没有数据可保存")
        return False

    # 保存到文件
    import json
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"quotes_{timestamp}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'update_time': datetime.now().isoformat(),
            'count': len(data),
            'data': data
        }, f, indent=2, ensure_ascii=False, default=str)

    print(f"[INFO] 数据已保存到: {output_file}")

    # 更新索引文件
    index_file = output_dir.parent / "latest.json"
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump({
            "latest_file": str(output_file.relative_to(output_dir.parent)),
            "update_time": datetime.now().isoformat(),
            "count": len(data)
        }, f, indent=2, ensure_ascii=False)
    print(f"[INFO] 索引文件已更新: {index_file}")

    return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="更新股票数据（修复版）")
    parser.add_argument("--symbols", type=str, help="股票代码列表，逗号分隔 (如 600519,000001)")
    parser.add_argument("--count", type=int, default=100, help="获取数量（默认100）")
    parser.add_argument("--output", type=str, default="data/quotes", help="输出目录")

    args = parser.parse_args()

    # 解析股票列表
    symbols = None
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(',')]
        print(f"[INFO] 指定股票: {', '.join(symbols)}")
    else:
        print(f"[INFO] 获取前 {args.count} 只股票数据")

    # 获取数据
    data = fetch_stock_data_direct(symbols)

    # 限制数量
    if data and args.count and len(data) > args.count:
        import itertools
        data = dict(itertools.islice(data.items(), args.count))
        print(f"[INFO] 限制为前 {args.count} 只股票")

    # 保存数据
    output_dir = Path(args.output)
    success = save_to_json(data, output_dir)

    if success:
        print("[SUCCESS] 数据更新完成")
        return 0
    else:
        print("[ERROR] 数据更新失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
