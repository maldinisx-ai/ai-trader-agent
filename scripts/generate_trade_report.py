# -*- coding: utf-8 -*-
"""
交易决策分析报告 - 输出到文件
"""

import json
from pathlib import Path
from collections import defaultdict

# 读取回测结果
result_file = Path('D:/projects/ai-trader-agent/data/backtest_results.json')
with open(result_file, 'r', encoding='utf-8') as f:
    result = json.load(f)

trades = result['trades']

# 输出到文件
output_file = Path('D:/projects/ai-trader-agent/data/trade_analysis_report.txt')
with open(output_file, 'w', encoding='utf-8') as f:
    f.write("=" * 100 + "\n")
    f.write(" " * 35 + "交易决策详情报告\n")
    f.write("=" * 100 + "\n\n")

    # 按股票分组统计
    stock_trades = defaultdict(list)
    for trade in trades:
        stock_trades[trade['symbol']].append(trade)

    f.write(f"总交易次数: {len(trades)}\n")
    f.write(f"涉及股票数: {len(stock_trades)}\n\n")

    # 显示每只股票的交易决策
    f.write("=" * 100 + "\n")
    f.write("按股票查看交易决策 (显示前15只股票)\n")
    f.write("=" * 100 + "\n\n")

    for symbol in sorted(stock_trades.keys())[:15]:
        f.write(f"\n{'=' * 100}\n")
        f.write(f"股票代码: {symbol}\n")
        f.write(f"交易次数: {len(stock_trades[symbol])}\n")
        f.write(f"{'=' * 100}\n")

        for i, trade in enumerate(stock_trades[symbol], 1):
            action_mark = "[买入]" if trade['action'] == 'buy' else "[卖出]"
            f.write(f"\n  [{i}] {trade['date']} {action_mark} {trade['action'].upper()}\n")
            f.write(f"      数量: {trade['quantity']} 股\n")
            f.write(f"      价格: {trade['price']:.2f} 元\n")
            f.write(f"      决策: {trade['reasoning']}\n")

    # 统计决策类型
    f.write("\n\n" + "=" * 100 + "\n")
    f.write("决策模式分析\n")
    f.write("=" * 100 + "\n\n")

    decision_patterns = {
        '金叉买入': 0,
        '死叉卖出': 0,
    }

    for trade in trades:
        if '金叉' in trade['reasoning']:
            decision_patterns['金叉买入'] += 1
        elif '死叉' in trade['reasoning']:
            decision_patterns['死叉卖出'] += 1

    f.write("决策类型统计:\n")
    for pattern, count in decision_patterns.items():
        f.write(f"  {pattern}: {count} 次\n")

    # 分析每只股票的盈亏
    f.write("\n\n" + "=" * 100 + "\n")
    f.write("按股票盈亏分析\n")
    f.write("=" * 100 + "\n\n")

    stock_profit = {}
    for symbol in stock_trades.keys():
        symbol_trades = stock_trades[symbol]
        profit = 0.0
        i = 0
        while i < len(symbol_trades):
            buy_trade = symbol_trades[i]
            if buy_trade['action'] == 'buy':
                if i + 1 < len(symbol_trades) and symbol_trades[i + 1]['action'] == 'sell':
                    sell_trade = symbol_trades[i + 1]
                    # 计算盈亏
                    buy_cost = buy_trade['quantity'] * buy_trade['price']
                    sell_revenue = sell_trade['quantity'] * sell_trade['price']
                    trade_profit = sell_revenue - buy_cost
                    profit += trade_profit
                    i += 2
                else:
                    # 买入后未卖出
                    i += 1
            else:
                i += 1
        stock_profit[symbol] = profit

    # 按盈亏排序
    sorted_stocks = sorted(stock_profit.items(), key=lambda x: x[1], reverse=True)

    f.write("股票盈亏排名 (前20名):\n")
    for symbol, profit in sorted_stocks[:20]:
        status = "盈利" if profit > 0 else "亏损"
        f.write(f"  {symbol}: {profit:+.2f} 元 ({status})\n")

    f.write("\n\n" + "=" * 100 + "\n")
    f.write("典型交易案例\n")
    f.write("=" * 100 + "\n\n")

    # 找出一些典型交易案例
    f.write("【案例1: 盈利最多的股票】\n")
    if sorted_stocks:
        best_symbol, best_profit = sorted_stocks[0]
        f.write(f"\n  股票: {best_symbol}\n")
        f.write(f"  总盈亏: {best_profit:+.2f} 元\n")
        for trade in stock_trades[best_symbol][:6]:
            f.write(f"    {trade['date']} {trade['action'].upper()} {trade['quantity']}股 @ {trade['price']:.2f}元\n")

    f.write("\n【案例2: 交易最频繁的股票】\n")
    most_traded = max(stock_trades.items(), key=lambda x: len(x[1]))
    symbol, trades_list = most_traded
    f.write(f"\n  股票: {symbol}\n")
    f.write(f"  交易次数: {len(trades_list)}\n")
    for trade in trades_list[:8]:
        f.write(f"    {trade['date']} {trade['action'].upper()} {trade['quantity']}股 @ {trade['price']:.2f}元\n")
        f.write(f"      理由: {trade['reasoning']}\n")

print(f"分析报告已保存到: {output_file}")
