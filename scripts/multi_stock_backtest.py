# -*- coding: utf-8 -*-
"""
多股票策略回测

使用68只股票的历史数据测试MA交叉策略
"""

import os
import sys
import io
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
import pandas as pd

# 设置UTF-8编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.schemas import QuoteData, Decision, Order, OrderSide, OrderType
from simulation.account import Account
from simulation.matcher import Matcher
from core.policy_engine import PolicyEngine
from src.indicators import QuoteDataAnalyzer
import logging

# 配置日志
logging.basicConfig(level=logging.WARNING)


class BacktestMatcher(Matcher):
    """回测专用撮合引擎 - 禁用 T+1 规则"""
    def _check_t1_rule(self, order: Order) -> None:
        return None


def load_stock_data(symbol: str) -> List[QuoteData]:
    """加载单只股票数据"""
    data_path = PROJECT_ROOT / f"data/stocks/stock_{symbol}.csv"
    if not data_path.exists():
        return None

    df = pd.read_csv(data_path)
    df['date'] = pd.to_datetime(df['date'])

    quotes = []
    for i, row in df.iterrows():
        change = 0.0
        if i > 0:
            prev_close = quotes[-1].price
            if prev_close > 0:
                change = ((row['close'] - prev_close) / prev_close) * 100
                # 限制涨跌幅在-11%到11%之间（符合A股涨跌停限制）
                change = max(-11, min(11, change))

        quotes.append(QuoteData(
            symbol=symbol,
            name=f"股票{symbol}",
            price=float(row['close']),
            change=change,
            volume=int(row['volume']),
            amount=float(row['amount']),
            high=float(row['high']),
            low=float(row['low']),
            open=float(row['open']),
            timestamp=row['date'],
        ))

    return quotes


def simple_ma_strategy(analyzer, account, symbol):
    """简单MA交叉策略"""
    if len(analyzer.quotes) < 30:
        return None

    ma_short = analyzer.get_sma(10)
    ma_long = analyzer.get_sma(30)

    # 检查MA值是否有效
    if len(ma_short) < 2 or len(ma_long) < 2:
        return None

    if ma_short[-1] is None or ma_long[-1] is None:
        return None
    if ma_short[-2] is None or ma_long[-2] is None:
        return None

    # 金叉/死叉
    golden_cross = ma_short[-2] <= ma_long[-2] and ma_short[-1] > ma_long[-1]
    death_cross = ma_short[-2] >= ma_long[-2] and ma_short[-1] < ma_long[-1]

    latest = analyzer.quotes[-1]
    positions = account.get_positions()
    has_position = any(p.symbol == symbol for p in positions)
    position = next((p for p in positions if p.symbol == symbol), None)

    if golden_cross and not has_position:
        account_info = account.get_account_info()
        cash = account_info.get('cash', 0)
        price = latest.price
        max_invest = cash * 0.30  # 30%仓位
        quantity = (int(max_invest / price) // 100) * 100

        if quantity >= 100:
            return Decision(
                action="buy",
                symbol=symbol,
                quantity=quantity,
                price=price,
                reasoning=f"MA10({ma_short[-1]:.2f})上穿MA30({ma_long[-1]:.2f})，金叉买入",
                confidence=0.7,
            )

    elif death_cross and has_position:
        return Decision(
            action="sell",
            symbol=symbol,
            quantity=position.shares,
            price=latest.price,
            reasoning=f"MA10({ma_short[-1]:.2f})下穿MA30({ma_long[-1]:.2f})，死叉卖出",
            confidence=0.7,
        )

    return None


def run_multi_stock_backtest(symbols: List[str], initial_cash: float = 500000):
    """运行多股票回测"""
    print("=" * 80)
    print(" " * 25 + "多股票策略回测")
    print("=" * 80)
    print(f"初始资金: ¥{initial_cash:,.2f}")
    print(f"股票数量: {len(symbols)}")
    print(f"策略: MA10/MA30 金叉死叉")
    print(f"单股最大仓位: 30%")
    print("=" * 80)
    print()

    # 加载所有股票数据
    print("正在加载股票数据...")
    all_quotes = {}
    valid_symbols = []

    for symbol in symbols:
        quotes = load_stock_data(symbol)
        if quotes and len(quotes) >= 30:
            all_quotes[symbol] = quotes
            valid_symbols.append(symbol)
            print(f"  ✓ {symbol}: {len(quotes)} 条数据")
        else:
            print(f"  ✗ {symbol}: 数据不足或不存在")

    print(f"\n有效股票: {len(valid_symbols)}")
    print()

    if len(valid_symbols) == 0:
        print("没有有效的股票数据")
        return None

    # 确定回测日期范围
    all_dates = set()
    for quotes in all_quotes.values():
        all_dates.update(q.timestamp for q in quotes)
    date_range = sorted(all_dates)

    print(f"回测日期范围: {date_range[0].strftime('%Y-%m-%d')} 至 {date_range[-1].strftime('%Y-%m-%d')}")
    print(f"总交易日: {len(date_range)}")
    print()

    # 初始化组件
    account = Account(initial_cash=initial_cash, db_path=":memory:")
    matcher = BacktestMatcher()
    policy_engine = PolicyEngine(cash=initial_cash, max_position_ratio=0.30)

    # 统计
    all_trades = []
    daily_values = []
    cross_stats = {'golden': 0, 'death': 0}

    print("开始回测...")
    print()

    # 按日期回测
    for idx, current_date in enumerate(date_range):
        # 更新所有股票的当前行情
        for symbol in valid_symbols:
            # 找到该日期的行情
            quotes = all_quotes[symbol]
            for quote in quotes:
                if quote.timestamp == current_date:
                    matcher.update_quote(quote)
                    break

        # 为每只股票生成交易决策
        for symbol in valid_symbols:
            # 获取该日期及之前的历史数据
            historical = []
            for quote in all_quotes[symbol]:
                if quote.timestamp <= current_date:
                    historical.append(quote)

            if len(historical) < 30:
                continue

            analyzer = QuoteDataAnalyzer(historical)
            decision = simple_ma_strategy(analyzer, account, symbol)

            if decision:
                # 检查交叉信号用于统计
                if "金叉" in decision.reasoning:
                    cross_stats['golden'] += 1
                elif "死叉" in decision.reasoning:
                    cross_stats['death'] += 1

                # 创建订单
                order = Order(
                    order_id=f"BT_{idx}_{symbol}",
                    symbol=symbol,
                    side=OrderSide.BUY if decision.action == "buy" else OrderSide.SELL,
                    quantity=decision.quantity or 100,
                    price=decision.price or 0.0,
                    order_type=OrderType.MARKET,
                )

                # 风控检查
                check = policy_engine.validate_order(order, historical[-1])
                if not check.allowed:
                    continue

                # 撮合
                import asyncio
                result = asyncio.run(matcher.match(order))

                if result.filled_quantity > 0:
                    account.update_from_trade(result)
                    all_trades.append({
                        "date": current_date.strftime("%Y-%m-%d"),
                        "symbol": symbol,
                        "action": decision.action,
                        "quantity": result.filled_quantity,
                        "price": result.filled_price,
                        "reasoning": decision.reasoning,
                    })

        # 记录每日资产
        daily_info = account.get_account_info()
        daily_values.append({
            "date": current_date,
            "total_value": daily_info['total_value'],
            "cash": daily_info['cash'],
            "position_value": daily_info['position_value'],
        })

        # 每50天输出进度
        if (idx + 1) % 50 == 0:
            print(f"第 {idx + 1}/{len(date_range)} 天 - 总资产: ¥{daily_info['total_value']:,.2f}")

    # 计算最终结果
    final_info = account.get_account_info()
    initial_value = initial_cash
    final_value = final_info['total_value']
    total_return = (final_value - initial_value) / initial_value * 100

    print("\n" + "=" * 80)
    print(" " * 30 + "回测结果汇总")
    print("=" * 80)
    print()

    # 总体表现
    print("【总体表现】")
    print(f"  初始资金:      ¥{initial_value:,.2f}")
    print(f"  最终资产:      ¥{final_value:,.2f}")
    print(f"  总收益:        ¥{final_value - initial_value:+,.2f}")
    print(f"  总收益率:      {total_return:+.2f}%")
    print()

    # 交易统计
    print("【交易统计】")
    print(f"  总交易次数:    {len(all_trades)}")
    buy_count = sum(1 for t in all_trades if t['action'] == 'buy')
    sell_count = sum(1 for t in all_trades if t['action'] == 'sell')
    print(f"  买入次数:      {buy_count}")
    print(f"  卖出次数:      {sell_count}")
    print(f"  金叉信号:      {cross_stats['golden']}")
    print(f"  死叉信号:      {cross_stats['death']}")
    print()

    # 持仓统计
    positions = final_info.get('positions', [])
    print("【最终持仓】")
    if positions:
        for pos in positions:
            profit_loss = (pos['current_price'] - pos['avg_cost']) * pos['shares']
            profit_pct = (pos['current_price'] / pos['avg_cost'] - 1) * 100
            print(f"  {pos['symbol']}: {pos['shares']}股, "
                  f"成本¥{pos['avg_cost']:.2f}, "
                  f"现价¥{pos['current_price']:.2f}, "
                  f"盈亏{profit_loss:+,.2f} ({profit_pct:+.2f}%)")
    else:
        print("  无持仓")
    print()

    # 按股票统计
    print("【按股票统计】")
    stock_trades = {}
    for trade in all_trades:
        symbol = trade['symbol']
        if symbol not in stock_trades:
            stock_trades[symbol] = {'buy': 0, 'sell': 0}
        stock_trades[symbol][trade['action']] += 1

    for symbol in sorted(stock_trades.keys()):
        trades = stock_trades[symbol]
        print(f"  {symbol}: 买入{trades['buy']}次, 卖出{trades['sell']}次")
    print()

    # 最近交易
    print("【最近10笔交易】")
    for trade in all_trades[-10:]:
        print(f"  {trade['date']} {trade['symbol']} "
              f"{trade['action'].upper()} {trade['quantity']}股 @ ¥{trade['price']:.2f}")
    print()

    # 收益曲线
    print("【收益曲线】")
    if len(daily_values) > 0:
        # 显示首尾和中间的几个点
        points = len(daily_values)
        show_points = [0, points//4, points//2, points*3//4, points-1]
        for i in show_points:
            dv = daily_values[i]
            pct = (dv['total_value'] / initial_value - 1) * 100
            print(f"  {dv['date'].strftime('%Y-%m-%d')}: "
                  f"¥{dv['total_value']:,.2f} ({pct:+.2f}%)")

    print("\n" + "=" * 80)

    return {
        "initial_cash": initial_value,
        "final_value": final_value,
        "total_return": total_return,
        "trades": all_trades,
        "daily_values": daily_values,
        "cross_stats": cross_stats,
    }


def main():
    """主函数"""
    # 获取所有已下载的股票
    stocks_dir = PROJECT_ROOT / 'data' / 'stocks'
    stock_files = list(stocks_dir.glob('stock_*.csv'))

    if not stock_files:
        print("未找到股票数据文件")
        return

    # 提取股票代码
    symbols = []
    for f in stock_files:
        code = f.stem.replace('stock_', '')
        symbols.append(code)

    print(f"找到 {len(symbols)} 只股票的数据")
    print()

    # 运行回测
    result = run_multi_stock_backtest(symbols, initial_cash=500000)

    if result:
        # 保存结果
        output_file = PROJECT_ROOT / 'data' / 'backtest_results.json'
        import json
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n回测结果已保存到: {output_file}")


if __name__ == '__main__':
    main()
