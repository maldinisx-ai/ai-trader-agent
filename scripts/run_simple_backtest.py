# -*- coding: utf-8 -*-
"""
简化版回测脚本 - 使用真实K线数据（增强版，带详细判断依据）

直接使用回测引擎的默认策略，避免复杂的策略系统。
"""

import sys
import os
import io
from pathlib import Path

# 设置控制台输出编码为UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from core.schemas import QuoteData, Decision, Order, OrderSide, OrderType
from simulation.account import Account
from simulation.matcher import Matcher
from core.policy_engine import PolicyEngine
from core.survival_rules import SurvivalRules
from src.indicators import QuoteDataAnalyzer
import logging


class BacktestMatcher(Matcher):
    """回测专用撮合引擎 - 禁用 T+1 规则"""

    def _check_t1_rule(self, order: Order) -> Optional[str]:
        """
        回测中禁用 T+1 规则检查

        Args:
            order: 订单对象

        Returns:
            None（总是通过）
        """
        return None  # 回测中不需要 T+1 限制


# 配置日志
logging.basicConfig(
    level=logging.WARNING,  # 只显示WARNING及以上，减少日志噪音
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_kline_data(symbol: str) -> list:
    """加载K线数据"""
    data_path = PROJECT_ROOT / f"data/klines_{symbol}.csv"
    df = pd.read_csv(data_path)
    df['date'] = pd.to_datetime(df['date'])

    quotes = []
    for i, row in df.iterrows():
        change = 0.0
        if i > 0:
            prev_close = quotes[-1].price
            if prev_close > 0:
                change = ((row['close'] - prev_close) / prev_close) * 100

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


def simple_ma_strategy(analyzer, account, symbol, debug=False):
    """简单均线策略 - 带详细判断依据"""
    if len(analyzer.quotes) < 30:
        return None

    # 使用MA10和MA30
    ma_short = analyzer.get_sma(10)
    ma_long = analyzer.get_sma(30)

    if ma_short[-1] is None or ma_long[-1] is None:
        return None
    if len(ma_short) < 2 or len(ma_long) < 2:
        return None

    # 获取最新行情
    latest = analyzer.quotes[-1]
    prev = analyzer.quotes[-2]

    # 检查金叉/死叉
    golden_cross = ma_short[-2] <= ma_long[-2] and ma_short[-1] > ma_long[-1]
    death_cross = ma_short[-2] >= ma_long[-2] and ma_short[-1] < ma_long[-1]

    # 获取持仓信息
    positions = account.get_positions()
    has_position = any(p.symbol == symbol for p in positions)
    position = next((p for p in positions if p.symbol == symbol), None)

    # 计算各种指标
    ma_diff = ma_short[-1] - ma_long[-1]
    ma_diff_prev = ma_short[-2] - ma_long[-2]
    ma_diff_change = ma_diff - ma_diff_prev

    price_change = latest.price - prev.price
    price_change_pct = (price_change / prev.price) * 100

    price_vs_ma10 = ((latest.price - ma_short[-1]) / ma_short[-1]) * 100
    price_vs_ma30 = ((latest.price - ma_long[-1]) / ma_long[-1]) * 100

    # 生成详细的判断依据
    def build_reasoning(action, cross_type):
        """构建详细的交易理由"""
        lines = []

        # 标题
        if cross_type == "golden":
            lines.append("════════════════════════════════════════")
            lines.append(f"📈 买入信号 - MA金叉")
            lines.append("════════════════════════════════════════")
        elif cross_type == "death":
            lines.append("════════════════════════════════════════")
            lines.append(f"📉 卖出信号 - MA死叉")
            lines.append("════════════════════════════════════════")

        # 1. 交叉信号详情
        lines.append("【交叉信号分析】")
        if cross_type == "golden":
            lines.append(f"  ✅ MA10({ma_short[-1]:.2f}) 上穿 MA30({ma_long[-1]:.2f})")
            lines.append(f"  均线差值变化: {ma_diff_prev:.2f} → {ma_diff:.2f} (变化 {ma_diff_change:+.2f})")
        elif cross_type == "death":
            lines.append(f"  ✅ MA10({ma_short[-1]:.2f}) 下穿 MA30({ma_long[-1]:.2f})")
            lines.append(f"  均线差值变化: {ma_diff_prev:.2f} → {ma_diff:.2f} (变化 {ma_diff_change:+.2f})")

        # 2. 当前市场数据
        lines.append("\n【市场数据】")
        lines.append(f"  当前价格: ¥{latest.price:.2f}")
        lines.append(f"  今日涨跌: {price_change:+.2f} 元 ({price_change_pct:+.2f}%)")
        lines.append(f"  价格相对MA10: {price_vs_ma10:+.2f}% ({'高于' if price_vs_ma10 > 0 else '低于'}均线)")
        lines.append(f"  价格相对MA30: {price_vs_ma30:+.2f}% ({'高于' if price_vs_ma30 > 0 else '低于'}均线)")

        # 3. 均线状态
        lines.append("\n【均线状态】")
        ma10_trend = "上升 ↑" if ma_short[-1] > ma_short[-2] else "下降 ↓" if ma_short[-1] < ma_short[-2] else "平盘 →"
        ma30_trend = "上升 ↑" if ma_long[-1] > ma_long[-2] else "下降 ↓" if ma_long[-1] < ma_long[-2] else "平盘 →"
        lines.append(f"  MA10(10日均线): {ma_short[-1]:.2f} ({ma10_trend}, 前值 {ma_short[-2]:.2f})")
        lines.append(f"  MA30(30日均线): {ma_long[-1]:.2f} ({ma30_trend}, 前值 {ma_long[-2]:.2f})")

        # 4. 操作详情
        lines.append("\n【操作详情】")
        if action == "buy":
            account_info = account.get_account_info()
            cash = account_info.get('cash', 0)
            max_invest = cash * 0.30
            quantity = (int(max_invest / latest.price) // 100) * 100
            lines.append(f"  操作: 买入 {quantity} 股")
            lines.append(f"  可用资金: ¥{cash:,.2f}")
            lines.append(f"  使用资金: ¥{max_invest:,.2f} (30%仓位)")
            lines.append(f"  预计成本: ¥{quantity * latest.price:,.2f}")
        elif action == "sell" and position:
            profit_loss = (latest.price - position.avg_cost) * position.shares
            profit_pct = (latest.price / position.avg_cost - 1) * 100
            lines.append(f"  操作: 卖出 {position.shares} 股")
            lines.append(f"  持仓成本: ¥{position.avg_cost:.2f}")
            lines.append(f"  当前市值: ¥{position.shares * latest.price:,.2f}")
            lines.append(f"  盈亏: {profit_loss:+,.2f} 元 ({profit_pct:+.2f}%)")

        # 5. 交易逻辑说明
        lines.append("\n【交易逻辑】")
        if cross_type == "golden":
            lines.append(f"  短期均线上穿长期均线，表明短期趋势转强")
            lines.append(f"  这是典型的看涨信号，建议建立多头仓位")
        elif cross_type == "death":
            lines.append(f"  短期均线下穿长期均线，表明短期趋势转弱")
            lines.append(f"  这是典型的看跌信号，建议平仓止损")

        lines.append("════════════════════════════════════════")
        return "\n".join(lines)

    # 调试输出（简化版）
    if debug:
        logger.info(f"Day {len(analyzer.quotes)}: MA10={ma_short[-1]:.2f}, MA30={ma_long[-1]:.2f}, "
                   f"Golden={golden_cross}, Death={death_cross}")

    if golden_cross and not has_position:
        # 买入 - 使用可用资金的30%
        account_info = account.get_account_info()
        cash = account_info.get('cash', 0)
        price = latest.price
        max_invest = cash * 0.30
        quantity = (int(max_invest / price) // 100) * 100  # 整手

        if quantity >= 100:
            reasoning = build_reasoning("buy", "golden")
            return Decision(
                action="buy",
                symbol=symbol,
                quantity=quantity,
                price=price,
                reasoning=reasoning,
                confidence=0.7,
            )

    elif death_cross and has_position:
        # 卖出
        reasoning = build_reasoning("sell", "death")
        return Decision(
            action="sell",
            symbol=symbol,
            quantity=position.shares,
            price=latest.price,
            reasoning=reasoning,
            confidence=0.7,
        )

    return None


def run_backtest(symbol, initial_cash=500000):
    """运行回测"""
    print("=" * 60)
    print("回测配置")
    print("=" * 60)
    print(f"股票代码: {symbol}")
    print(f"初始资金: ¥{initial_cash:,.2f}")
    print(f"策略: MA10/MA30 金叉死叉（带详细判断依据）")
    print("=" * 60)

    # 加载数据
    quotes = load_kline_data(symbol)
    print(f"\n数据范围: {quotes[0].timestamp.strftime('%Y-%m-%d')} 至 {quotes[-1].timestamp.strftime('%Y-%m-%d')}")
    print(f"数据数量: {len(quotes)} 条K线\n")

    # 先检测所有交叉日期
    ma10_list = []
    ma30_list = []
    golden_cross_days = []
    death_cross_days = []

    for i in range(30, len(quotes)):
        analyzer = QuoteDataAnalyzer(quotes[:i+1])
        ma10 = analyzer.get_sma(10)
        ma30 = analyzer.get_sma(30)
        if ma10 and ma30 and ma10[-1] and ma30[-1]:
            ma10_list.append(ma10[-1])
            ma30_list.append(ma30[-1])

            if len(ma10_list) >= 2:
                golden = ma10_list[-2] <= ma30_list[-2] and ma10_list[-1] > ma30_list[-1]
                death = ma10_list[-2] >= ma30_list[-2] and ma10_list[-1] < ma30_list[-1]
                if golden:
                    golden_cross_days.append(i)
                if death:
                    death_cross_days.append(i)

    print(f"检测到 {len(golden_cross_days)} 次金叉，{len(death_cross_days)} 次死叉\n")

    # 初始化组件
    account = Account(initial_cash=initial_cash, db_path=":memory:")
    matcher = BacktestMatcher()  # 使用回测专用撮合引擎
    policy_engine = PolicyEngine(cash=initial_cash, max_position_ratio=0.30)

    # 交易记录
    trades = []

    print("开始回测...\n")

    # 逐日回测
    for i in range(30, len(quotes)):
        current_quote = quotes[i]
        matcher.update_quote(current_quote)

        # 获取历史数据
        historical = quotes[:i+1]
        analyzer = QuoteDataAnalyzer(historical)

        # 生成决策（只在交叉日输出）
        debug = (i in golden_cross_days) or (i in death_cross_days)
        decision = simple_ma_strategy(analyzer, account, symbol, debug=debug)

        if decision:
            # 创建订单
            order = Order(
                order_id=f"BT_{i}_{symbol}",
                symbol=symbol,
                side=OrderSide.BUY if decision.action == "buy" else OrderSide.SELL,
                quantity=decision.quantity or 100,
                price=decision.price or 0.0,
                order_type=OrderType.MARKET,
            )

            # 风控检查
            check = policy_engine.validate_order(order, current_quote)
            if not check.allowed:
                logger.info(f"  -> 风控拒绝: {check.reason}")
                continue

            # 撮合
            import asyncio
            result = asyncio.run(matcher.match(order))

            if result.filled_quantity > 0:
                account.update_from_trade(result)
                trades.append({
                    "date": current_quote.timestamp.strftime("%Y-%m-%d"),
                    "action": decision.action,
                    "quantity": result.filled_quantity,
                    "price": result.filled_price,
                    "reasoning": decision.reasoning,
                })
                # 输出交易和判断依据
                print(f"\n{'='*60}")
                print(f"📅 {current_quote.timestamp.strftime('%Y-%m-%d')}")
                print(decision.reasoning)
                print(f"✅ 交易成功: {decision.action.upper()} {result.filled_quantity}股 @ ¥{result.filled_price:.2f}")
                print(f"{'='*60}\n")

        # 每50天输出进度
        if (i + 1) % 50 == 0:
            info = account.get_account_info()
            print(f"--- 第 {i + 1} 天 --- 总资产: ¥{info['total_value']:,.2f}")

    # 计算最终结果
    print("\n" + "=" * 60)
    print("回测完成")
    print("=" * 60)

    final_info = account.get_account_info()
    initial_value = initial_cash
    final_value = final_info['total_value']
    total_return = (final_value - initial_value) / initial_value * 100

    print(f"\n初始资金: ¥{initial_value:,.2f}")
    print(f"最终资产: ¥{final_value:,.2f}")
    print(f"总收益: ¥{final_value - initial_value:+,.2f}")
    print(f"总收益率: {total_return:+.2f}%")
    print(f"交易次数: {len(trades)}")

    if len(trades) > 0:
        print(f"\n交易汇总:")
        print(f"  买入次数: {sum(1 for t in trades if t['action'] == 'buy')}")
        print(f"  卖出次数: {sum(1 for t in trades if t['action'] == 'sell')}")

    return {
        "initial_cash": initial_value,
        "final_value": final_value,
        "total_return": total_return,
        "trades": trades,
    }


if __name__ == "__main__":
    symbol = "600519"
    result = run_backtest(symbol, initial_cash=500000)
