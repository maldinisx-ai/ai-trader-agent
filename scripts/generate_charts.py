# -*- coding: utf-8 -*-
"""
回测结果可视化分析
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import numpy as np

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

# 读取回测结果
result_file = Path('D:/projects/ai-trader-agent/data/backtest_results.json')
with open(result_file, 'r', encoding='utf-8') as f:
    result = json.load(f)

trades = result['trades']
daily_values = result['daily_values']

# 创建输出目录
output_dir = Path('D:/projects/ai-trader-agent/data/charts')
output_dir.mkdir(exist_ok=True)

print("=" * 80)
print(" " * 25 + "回测结果可视化分析")
print("=" * 80)
print()

# ============================================
# 图1: 总资产收益曲线
# ============================================
print("生成图1: 总资产收益曲线...")

df_daily = pd.DataFrame(daily_values)
df_daily['date'] = pd.to_datetime(df_daily['date'])
df_daily['return_pct'] = (df_daily['total_value'] / 500000 - 1) * 100

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

# 子图1: 资产曲线
ax1.plot(df_daily['date'], df_daily['total_value'], linewidth=2, color='#2E86AB', label='总资产')
ax1.axhline(y=500000, color='gray', linestyle='--', alpha=0.5, label='初始资金')
ax1.fill_between(df_daily['date'], 500000, df_daily['total_value'], alpha=0.3, color='#2E86AB')
ax1.set_xlabel('日期', fontsize=12)
ax1.set_ylabel('资产(元)', fontsize=12)
ax1.set_title('总资产收益曲线', fontsize=14, fontweight='bold')
ax1.legend(loc='upper left', fontsize=10)
ax1.grid(True, alpha=0.3)
ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'¥{x:,.0f}'))

# 子图2: 收益率
colors = ['green' if x >= 0 else 'red' for x in df_daily['return_pct']]
ax2.bar(df_daily['date'], df_daily['return_pct'], color=colors, alpha=0.6)
ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
ax2.set_xlabel('日期', fontsize=12)
ax2.set_ylabel('收益率(%)', fontsize=12)
ax2.set_title('每日收益率', fontsize=14, fontweight='bold')
ax2.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig(output_dir / '01_return_curve.png', dpi=150, bbox_inches='tight')
print(f"  已保存: {output_dir / '01_return_curve.png'}")
plt.close()

# ============================================
# 图2: 按股票盈亏分析
# ============================================
print("生成图2: 按股票盈亏分析...")

# 计算每只股票的盈亏
stock_profit = {}
stock_trades = defaultdict(list)
for trade in trades:
    stock_trades[trade['symbol']].append(trade)

for symbol in stock_trades.keys():
    symbol_trades = stock_trades[symbol]
    profit = 0.0
    i = 0
    while i < len(symbol_trades):
        buy_trade = symbol_trades[i]
        if buy_trade['action'] == 'buy':
            if i + 1 < len(symbol_trades) and symbol_trades[i + 1]['action'] == 'sell':
                sell_trade = symbol_trades[i + 1]
                buy_cost = buy_trade['quantity'] * buy_trade['price']
                sell_revenue = sell_trade['quantity'] * sell_trade['price']
                trade_profit = sell_revenue - buy_cost
                profit += trade_profit
                i += 2
            else:
                # 买入后未卖出，按最后价格计算
                i += 1
        else:
            i += 1
    stock_profit[symbol] = profit

# 排序
sorted_stocks = sorted(stock_profit.items(), key=lambda x: x[1], reverse=True)
top_20 = sorted_stocks[:20]
bottom_20 = sorted_stocks[-20:]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

# 盈利TOP20
stocks = [s[0] for s in top_20]
profits = [s[1] for s in top_20]
colors = ['#2ECC71' if p > 0 else '#E74C3C' for p in profits]

ax1.barh(stocks, profits, color=colors, alpha=0.7)
ax1.axvline(x=0, color='black', linewidth=0.5)
ax1.set_xlabel('盈亏(元)', fontsize=12)
ax1.set_title('盈利TOP20', fontsize=14, fontweight='bold')
ax1.grid(True, alpha=0.3, axis='x')

# 亏损TOP20 (取最后20个)
stocks_loss = [s[0] for s in bottom_20]
profits_loss = [s[1] for s in bottom_20]
colors_loss = ['#2ECC71' if p > 0 else '#E74C3C' for p in profits_loss]

ax2.barh(stocks_loss, profits_loss, color=colors_loss, alpha=0.7)
ax2.axvline(x=0, color='black', linewidth=0.5)
ax2.set_xlabel('盈亏(元)', fontsize=12)
ax2.set_title('亏损TOP20', fontsize=14, fontweight='bold')
ax2.grid(True, alpha=0.3, axis='x')

plt.tight_layout()
plt.savefig(output_dir / '02_stock_profit.png', dpi=150, bbox_inches='tight')
print(f"  已保存: {output_dir / '02_stock_profit.png'}")
plt.close()

# ============================================
# 图3: 交易频率分析
# ============================================
print("生成图3: 交易频率分析...")

trade_counts = {}
for symbol in stock_trades.keys():
    trade_counts[symbol] = len(stock_trades[symbol])

sorted_trade_counts = sorted(trade_counts.items(), key=lambda x: x[1], reverse=True)
top_15 = sorted_trade_counts[:15]

fig, ax = plt.subplots(figsize=(12, 8))
stocks = [s[0] for s in top_15]
counts = [s[1] for s in top_15]

colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(stocks)))
bars = ax.barh(stocks, counts, color=colors, alpha=0.8)

# 添加数值标签
for i, (stock, count) in enumerate(zip(stocks, counts)):
    ax.text(count, i, f' {count}', va='center', fontsize=10)

ax.set_xlabel('交易次数', fontsize=12)
ax.set_title('交易频率TOP15', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3, axis='x')
ax.invert_yaxis()

plt.tight_layout()
plt.savefig(output_dir / '03_trade_frequency.png', dpi=150, bbox_inches='tight')
print(f"  已保存: {output_dir / '03_trade_frequency.png'}")
plt.close()

# ============================================
# 图4: 资金配置分析
# ============================================
print("生成图4: 资金配置分析...")

df_daily['cash_ratio'] = df_daily['cash'] / df_daily['total_value'] * 100
df_daily['position_ratio'] = df_daily['position_value'] / df_daily['total_value'] * 100

fig, ax = plt.subplots(figsize=(14, 6))
ax.stackplot(df_daily['date'],
               [df_daily['cash_ratio'], df_daily['position_ratio']],
               labels=['现金', '持仓'],
               colors=['#3498DB', '#E74C3C'],
               alpha=0.7)

ax.set_xlabel('日期', fontsize=12)
ax.set_ylabel('资金占比(%)', fontsize=12)
ax.set_title('资金配置变化', fontsize=14, fontweight='bold')
ax.legend(loc='upper right', fontsize=11)
ax.grid(True, alpha=0.3)
ax.set_ylim(0, 100)

plt.tight_layout()
plt.savefig(output_dir / '04_capital_allocation.png', dpi=150, bbox_inches='tight')
print(f"  已保存: {output_dir / '04_capital_allocation.png'}")
plt.close()

# ============================================
# 图5: 月度收益分析
# ============================================
print("生成图5: 月度收益分析...")

df_daily['month'] = df_daily['date'].dt.to_period('M')
monthly_returns = df_daily.groupby('month')['total_value'].last()
monthly_returns.index = monthly_returns.index.to_timestamp()

monthly_profit = monthly_returns.diff()
monthly_profit_pct = (monthly_profit / monthly_returns.shift(1) * 100)

fig, ax = plt.subplots(figsize=(12, 6))
bars = ax.bar(monthly_profit_pct.index, monthly_profit_pct.values,
                  color=['green' if x >= 0 else 'red' for x in monthly_profit_pct.values],
                  alpha=0.6)

ax.axhline(y=0, color='black', linewidth=0.5)
ax.set_xlabel('月份', fontsize=12)
ax.set_ylabel('月收益率(%)', fontsize=12)
ax.set_title('月度收益分析', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3, axis='y')

# 添加数值标签
for i, (date, value) in enumerate(zip(monthly_profit_pct.index, monthly_profit_pct.values)):
    if not np.isnan(value):
        ax.text(i, value + (1 if value >= 0 else -1), f'{value:.1f}%',
                ha='center', fontsize=8)

plt.tight_layout()
plt.savefig(output_dir / '05_monthly_returns.png', dpi=150, bbox_inches='tight')
print(f"  已保存: {output_dir / '05_monthly_returns.png'}")
plt.close()

# ============================================
# 图6: 盈亏分布直方图
# ============================================
print("生成图6: 盈亏分布直方图...")

all_profits = [p for p in stock_profit.values() if p != 0]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

# 盈亏分布
bins = [-50000, -20000, -10000, -5000, -2000, -1000, 0, 1000, 2000, 5000, 10000, 20000, 50000]
ax1.hist(all_profits, bins=bins, color='skyblue', edgecolor='black', alpha=0.7)
ax1.axvline(x=0, color='red', linestyle='--', linewidth=2)
ax1.set_xlabel('盈亏(元)', fontsize=12)
ax1.set_ylabel('股票数量', fontsize=12)
ax1.set_title('盈亏分布', fontsize=14, fontweight='bold')
ax1.grid(True, alpha=0.3)

# 盈亏占比
profit_count = sum(1 for p in all_profits if p > 0)
loss_count = sum(1 for p in all_profits if p < 0)
total_count = len(all_profits)

ax2.pie([profit_count, loss_count],
           labels=[f'盈利股票 ({profit_count}只)', f'亏损股票 ({loss_count}只)'],
           colors=['#2ECC71', '#E74C3C'],
           autopct='%1.1f%%',
           startangle=90)
ax2.set_title('盈亏股票占比', fontsize=14, fontweight='bold')

plt.tight_layout()
plt.savefig(output_dir / '06_profit_distribution.png', dpi=150, bbox_inches='tight')
print(f"  已保存: {output_dir / '06_profit_distribution.png'}")
plt.close()

# ============================================
# 图7: 关键指标仪表盘
# ============================================
print("生成图7: 关键指标仪表盘...")

# 计算关键指标
final_value = result['final_value']
total_return = result['total_return']
total_trades = len(trades)
profit_stocks = sum(1 for p in stock_profit.values() if p > 0)
loss_stocks = sum(1 for p in stock_profit.values() if p < 0)
avg_profit = np.mean([p for p in stock_profit.values() if p > 0]) if profit_stocks > 0 else 0

fig = plt.figure(figsize=(14, 8))

# 创建子图
gs = fig.add_gridspec(2, 3, hspace=0.3, wspace=0.3)

# 1. 总收益率
ax1 = fig.add_subplot(gs[0, 0])
ax1.axis('off')
total_return_color = '#2ECC71' if total_return > 0 else '#E74C3C'
ax1.text(0.5, 0.5, f'{total_return:+.2f}%',
        ha='center', va='center', fontsize=32, fontweight='bold', color=total_return_color)
ax1.set_title('总收益率', fontsize=12, pad=20)

# 2. 总交易次数
ax2 = fig.add_subplot(gs[0, 1])
ax2.axis('off')
ax2.text(0.5, 0.5, f'{total_trades}',
        ha='center', va='center', fontsize=32, fontweight='bold', color='#3498DB')
ax2.set_title('总交易次数', fontsize=12, pad=20)

# 3. 盈利股票占比
ax3 = fig.add_subplot(gs[0, 2])
ax3.axis('off')
profit_ratio = profit_stocks / total_count * 100 if total_count > 0 else 0
ax3.text(0.5, 0.5, f'{profit_ratio:.1f}%',
        ha='center', va='center', fontsize=32, fontweight='bold', color='#2ECC71')
ax3.set_title('盈利股票占比', fontsize=12, pad=20)

# 4. 平均盈利
ax4 = fig.add_subplot(gs[1, 0])
ax4.axis('off')
ax4.text(0.5, 0.5, f'{avg_profit:.0f} 元',
        ha='center', va='center', fontsize=28, fontweight='bold', color='#2ECC71')
ax4.set_title('平均盈利(盈利股票)', fontsize=12, pad=20)

# 5. 盈利股票数
ax5 = fig.add_subplot(gs[1, 1])
ax5.axis('off')
ax5.text(0.5, 0.5, f'{profit_stocks} 只',
        ha='center', va='center', fontsize=28, fontweight='bold', color='#2ECC71')
ax5.set_title('盈利股票数', fontsize=12, pad=20)

# 6. 亏损股票数
ax6 = fig.add_subplot(gs[1, 2])
ax6.axis('off')
ax6.text(0.5, 0.5, f'{loss_stocks} 只',
        ha='center', va='center', fontsize=28, fontweight='bold', color='#E74C3C')
ax6.set_title('亏损股票数', fontsize=12, pad=20)

fig.suptitle('关键指标仪表盘', fontsize=16, fontweight='bold', y=0.95)
plt.savefig(output_dir / '07_key_metrics.png', dpi=150, bbox_inches='tight')
print(f"  已保存: {output_dir / '07_key_metrics.png'}")
plt.close()

# ============================================
# 图8: 胜景收益率曲线
# ============================================
print("生成图8: 背景收益率对比...")

# 获取上证指数数据作为基准
try:
    index_file = Path('D:/projects/ai-trader-agent/data/index_000001.csv')
    if index_file.exists():
        df_index = pd.read_csv(index_file)
        df_index['date'] = pd.to_datetime(df_index['date'])
        df_index['close'] = df_index['close'].astype(float)

        # 计算指数收益率
        df_index = df_index.sort_values('date')
        df_index['return_pct'] = (df_index['close'] / df_index['close'].iloc[0] - 1) * 100

        # 对齐日期范围
        start_date = df_daily['date'].min()
        end_date = df_daily['date'].max()
        df_index = df_index[(df_index['date'] >= start_date) & (df_index['date'] <= end_date)]

        # 找到与策略日期匹配的指数数据
        matched_index_returns = []
        for date in df_daily['date']:
            idx_row = df_index[df_index['date'] == date]
            if not idx_row.empty:
                matched_index_returns.append(idx_row['return_pct'].values[0])
            else:
                matched_index_returns.append(np.nan)

        # 填充到策略数据长度
        while len(matched_index_returns) < len(df_daily):
            matched_index_returns.append(np.nan)

        df_daily['index_return'] = matched_index_returns[:len(df_daily)]

        # 绘制对比图
        fig, ax = plt.subplots(figsize=(14, 6))

        # 策略收益率
        ax.plot(df_daily['date'], df_daily['return_pct'],
                linewidth=2, color='#2E86AB', label='策略收益率')

        # 上证指数收益率
        ax.plot(df_daily['date'], df_daily['index_return'],
                linewidth=2, color='#95A5A6', label='上证指数', linestyle='--')

        ax.axhline(y=0, color='black', linewidth=0.5)
        ax.fill_between(df_daily['date'], 0, df_daily['return_pct'],
                        where=[x >= 0 for x in df_daily['return_pct']],
                        color='green', alpha=0.3, label='策略盈利区间')
        ax.fill_between(df_daily['date'], 0, df_daily['return_pct'],
                        where=[x >= 0 for x in df_daily['return_pct']],
                        color='red', alpha=0.3)

        ax.set_xlabel('日期', fontsize=12)
        ax.set_ylabel('累计收益率(%)', fontsize=12)
        ax.set_title('策略 vs 上证指数收益率对比', fontsize=14, fontweight='bold')
        ax.legend(loc='upper left', fontsize=11)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_dir / '08_vs_index.png', dpi=150, bbox_inches='tight')
        print(f"  已保存: {output_dir / '08_vs_index.png'}")
except Exception as e:
    print(f"  跳过基准对比: {e}")

plt.close()

print("\n" + "=" * 80)
print(" " * 30 + "图表生成完成！")
print("=" * 80)
print()
print(f"图表保存目录: {output_dir}")
print()
print("生成的图表:")
print("  1. 01_return_curve.png    - 总资产收益曲线")
print("  2. 02_stock_profit.png      - 按股票盈亏分析")
print("  3. 03_trade_frequency.png  - 交易频率分析")
print("  4. 04_capital_allocation.png - 资金配置变化")
print("  5. 05_monthly_returns.png   - 月度收益分析")
print("  6. 06_profit_distribution.png - 盈亏分布")
print("  7. 07_key_metrics.png       - 关键指标仪表盘")
print("  8. 08_vs_index.png          - vs上证指数对比")
print()

# 显示统计摘要
print("=" * 80)
print(" " * 30 + "关键指标摘要")
print("=" * 80)
print(f"总收益率:        {total_return:+.2f}%")
print(f"总交易次数:        {total_trades}")
print(f"盈利股票:        {profit_stocks} 只")
print(f"亏损股票:        {loss_stocks} 只")
print(f"胜率:            {profit_stocks/total_count*100:.1f}%")
print(f"平均盈利:        {avg_profit:.2f} 元")
print(f"最大单只盈利:    {max(stock_profit.values()):,.2f} 元")
print(f"最大单只亏损:    {min(stock_profit.values()):,.2f} 元")
print("=" * 80)
