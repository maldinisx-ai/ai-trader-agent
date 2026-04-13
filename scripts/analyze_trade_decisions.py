# -*- coding: utf-8 -*-
"""
交易决策分析报告
"""

import json
from pathlib import Path
from collections import defaultdict

# 读取回测结果
result_file = Path('D:/projects/ai-trader-agent/data/backtest_results.json')
with open(result_file, 'r', encoding='utf-8') as f:
    result = json.load(f)

trades = result['trades']

print("=" * 100)
print(" " * 35 + "交易决策详情")
print("=" * 100)
print()

# 按股票分组统计
stock_trades = defaultdict(list)
for trade in trades:
    stock_trades[trade['symbol']].append(trade)

# 显示每只股票的交易决策
print("=" * 100)
print(" " * 35 + "按股票查看交易决策")
print("=" * 100)
print()

for symbol in sorted(stock_trades.keys())[:10]:  # 显示前10只股票
    print(f"\n{'=' * 100}")
    print(f"  股票代码: {symbol}")
    print(f"  交易次数: {len(stock_trades[symbol])}")
    print(f"{'=' * 100}")

    for i, trade in enumerate(stock_trades[symbol], 1):
        action_mark = "[买入]" if trade['action'] == 'buy' else "[卖出]"
        print(f"\n  [{i}] {trade['date']} {action_mark} {trade['action'].upper()}")
        print(f"      数量: {trade['quantity']} 股")
        print(f"      价格: {trade['price']:.2f} 元")
        print(f"      决策: {trade['reasoning']}")

print("\n" + "=" * 100)
print(" " * 35 + "决策模式分析")
print("=" * 100)
print()

# 统计决策类型
decision_patterns = {
    '金叉买入': 0,
    '死叉卖出': 0,
}

for trade in trades:
    if '金叉' in trade['reasoning']:
        decision_patterns['金叉买入'] += 1
    elif '死叉' in trade['reasoning']:
        decision_patterns['死叉卖出'] += 1

print("决策类型统计:")
for pattern, count in decision_patterns.items():
    print(f"  {pattern}: {count} 次")

print("\n" + "=" * 100)
print(" " * 35 + "典型交易案例")
print("=" * 100)
print()

# 找出一些典型交易案例
print("\n【案例1: 完整买卖周期】")
for symbol in ['600519', '000333', '300760', '002594']:
    if symbol in stock_trades:
        symbol_trades = stock_trades[symbol]
        if len(symbol_trades) >= 2:
            print(f"\n  股票: {symbol}")
            for i, trade in enumerate(symbol_trades[:4]):  # 显示前4笔
                print(f"    {trade['date']} {trade['action'].upper()} {trade['quantity']}股 @ ¥{trade['price']:.2f}")
                print(f"      理由: {trade['reasoning']}")
            break

print("\n" + "=" * 100)
