# -*- coding: utf-8 -*-
"""
完整交易测试脚本

模拟完整的买入和卖出流程，验证新策略的端到端功能。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from src.strategies.trend_scoring import TrendScoringStrategy
from src.strategies.base import StrategyConfig, StrategySignal
from src.indicators import QuoteDataAnalyzer
from core.schemas import (
    QuoteData,
    Position,
    OrderSide,
    OrderType,
    BuySignal,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def print_separator(char="=", length=70):
    """打印分隔线"""
    print(char * length)


def generate_ascending_quotes(
    days: int = 30,
    base_price: float = 10.0,
    trend: str = "up",
    volatility: float = 0.02,
) -> list[QuoteData]:
    """
    生成模拟行情数据 - 更强的上涨趋势

    Args:
        days: 天数
        base_price: 基准价格
        trend: 趋势方向 (up/down/sideways)
        volatility: 波动率
    """
    quotes = []
    current_price = base_price

    for i in range(days):
        # 更强的上涨趋势
        if trend == "up":
            change = 0.008 if i < 15 else 0.003  # 前期快速上涨
        elif trend == "down":
            change = -0.005
        else:
            change = volatility * (hash(i) % 3 - 1) / 3  # 震荡

        current_price = current_price * (1 + change)

        # 生成成交量
        base_volume = 10000  # 手
        volume_change = 0.5 + (hash(i * 3) % 100) / 100
        volume = int(base_volume * volume_change)

        # 生成OHLC
        open_price = current_price * (1 - (hash(i * 11) % 50) / 1000)
        high_price = max(open_price, current_price) * (1 + abs(hash(i * 13)) / 5000)
        low_price = min(open_price, current_price) * (1 - abs(hash(i * 17)) / 5000)

        quote = QuoteData(
            symbol="600000",
            name="浦发银行",
            price=round(current_price, 2),
            change=round(change * 100, 2),
            volume=volume,
            amount=volume * current_price * 100,  # 手 -> 股
            high=round(high_price, 2),
            low=round(low_price, 2),
            open=round(open_price, 2),
            timestamp=datetime.now() - timedelta(days=days - i),
        )

        quotes.append(quote)

    return quotes


def simulate_buy_signal():
    """模拟买入信号生成"""
    print_separator()
    print("[BUY] 模拟买入信号")
    print_separator()

    # 生成上涨趋势数据（触发买入）
    quotes = generate_ascending_quotes(days=30, base_price=10.0, trend="up")

    # 创建分析器
    analyzer = QuoteDataAnalyzer(quotes)

    # 创建策略
    config = StrategyConfig(
        name="trend_scoring",
        params={
            "max_position_ratio": 0.30,
            "stop_loss_threshold": -0.05,
            "take_profit_threshold": 0.15,
        },
    )

    strategy = TrendScoringStrategy(config)

    # 模拟账户信息
    account_info = {
        "cash": 100000.0,
        "total_value": 100000.0,
        "positions": [],
    }

    # 生成信号
    signal = strategy.generate_signal(analyzer, account_info)

    if signal:
        print(f"[BUY] 信号类型: {signal.signal_type}")
        print(f"[BUY] 股票代码: {signal.symbol}")
        print(f"[BUY] 买入价格: {signal.price:.2f}")
        print(f"[BUY] 买入数量: {signal.quantity}")
        print(f"[BUY] 置信度: {signal.confidence:.2f}")
        print(f"[BUY] 推理: {signal.reasoning}")
        print(f"[BUY] 总评分: {signal.metadata.get('total_score', 'N/A')}")

        # 创建持仓
        position = Position(
            symbol=signal.symbol,
            shares=signal.quantity,
            avg_cost=signal.price,
            current_price=signal.price,
            opened_at=datetime.now(),
        )

        print(f"[BUY] 已创建持仓: {position.shares}股 @ {position.avg_cost:.2f}")

        return position
    else:
        print("[BUY] 未生成买入信号")

    return None


def simulate_sell_signal(position: Position):
    """模拟卖出信号生成"""
    print_separator()
    print("[SELL] 模拟卖出信号")
    print_separator()

    # 生成强力下跌趋势数据（触发卖出）
    # 基价13.0，下跌后约10.5，接近成本价11.79，且趋势向下
    quotes = []
    current_price = 13.0

    for i in range(30):
        # 强力下跌趋势
        change = -0.006  # 每日下跌0.6%
        current_price = current_price * (1 + change)

        # 生成成交量
        base_volume = 10000
        volume_change = 0.5 + (hash(i * 3) % 100) / 100
        volume = int(base_volume * volume_change)

        # 生成OHLC
        open_price = current_price * (1 - (hash(i * 11) % 50) / 1000)
        high_price = max(open_price, current_price) * (1 + abs(hash(i * 13)) / 5000)
        low_price = min(open_price, current_price) * (1 - abs(hash(i * 17)) / 5000)

        quote = QuoteData(
            symbol="600000",
            name="浦发银行",
            price=round(current_price, 2),
            change=round(change * 100, 2),
            volume=volume,
            amount=volume * current_price * 100,
            high=round(high_price, 2),
            low=round(low_price, 2),
            open=round(open_price, 2),
            timestamp=datetime.now() - timedelta(days=30 - i),
        )

        quotes.append(quote)

    # 创建分析器
    analyzer = QuoteDataAnalyzer(quotes)

    # 创建策略
    config = StrategyConfig(
        name="trend_scoring",
        params={
            "max_position_ratio": 0.30,
            "stop_loss_threshold": -0.05,
            "take_profit_threshold": 0.15,
        },
    )

    strategy = TrendScoringStrategy(config)

    # 更新持仓的当前价格
    latest_price = quotes[-1].price
    position.current_price = latest_price
    position.updated_at = datetime.now()

    print(f"[SELL] 当前价格: {position.current_price:.2f}")
    print(f"[SELL] 成本价格: {position.avg_cost:.2f}")
    print(f"[SELL] 盈亏比例: {position.pnl_ratio*100:+.2f}%")
    print(f"[SELL] 浮动盈亏: {position.pnl:+.2f}")

    # 模拟账户信息
    account_info = {
        "cash": 85000.0,
        "total_value": 100000.0,
        "positions": [position],
    }

    # 生成信号
    signal = strategy.generate_signal(analyzer, account_info)

    if signal:
        print(f"[SELL] 信号类型: {signal.signal_type}")
        print(f"[SELL] 股票代码: {signal.symbol}")
        print(f"[SELL] 卖出价格: {signal.price:.2f}")
        print(f"[SELL] 卖出数量: {signal.quantity}")
        print(f"[SELL] 置信度: {signal.confidence:.2f}")
        print(f"[SELL] 推理: {signal.reasoning}")

        if "reason" in signal.metadata:
            reason = signal.metadata["reason"]
            print(f"[SELL] 卖出原因: {reason}")

        return signal
    else:
        print("[SELL] 未生成卖出信号")

    return None


def simulate_stop_loss(position: Position):
    """模拟止损信号"""
    print_separator()
    print("[STOP LOSS] 模拟止损信号")
    print_separator()

    # 生成急剧下跌数据（触发止损）- 低价触发亏损
    quotes = generate_ascending_quotes(days=30, base_price=11.0, trend="down")
    # 更新最后一个价格为低价，触发止损
    last_quote = quotes[-1]
    from core.schemas import QuoteData
    quotes[-1] = QuoteData(
        symbol=last_quote.symbol,
        name=last_quote.name,
        price=11.0,  # 低于成本价11.79
        change=-8.0,
        volume=last_quote.volume,
        amount=11.0 * last_quote.volume * 100,
        high=11.5,
        low=10.8,
        open=last_quote.open,
        timestamp=last_quote.timestamp,
    )

    # 创建分析器
    analyzer = QuoteDataAnalyzer(quotes)

    # 创建策略
    config = StrategyConfig(
        name="trend_scoring",
        params={
            "max_position_ratio": 0.30,
            "stop_loss_threshold": -0.05,
            "take_profit_threshold": 0.15,
        },
    )

    strategy = TrendScoringStrategy(config)

    # 更新持仓（亏损状态）
    position.current_price = quotes[-1].price
    position.updated_at = datetime.now()

    print(f"[STOP LOSS] 当前价格: {position.current_price:.2f}")
    print(f"[STOP LOSS] 成本价格: {position.avg_cost:.2f}")
    print(f"[STOP LOSS] 盈亏比例: {position.pnl_ratio*100:+.2f}%")

    # 模拟账户信息
    account_info = {
        "cash": 85000.0,
        "total_value": 95000.0,
        "positions": [position],
    }

    # 生成信号
    signal = strategy.generate_signal(analyzer, account_info)

    if signal:
        print(f"[STOP LOSS] 信号类型: {signal.signal_type}")
        print(f"[STOP LOSS] 推理: {signal.reasoning}")
        print(f"[STOP LOSS] 卖出原因: {signal.metadata.get('reason', 'N/A')}")

        return signal
    else:
        print("[STOP LOSS] 未生成止损信号")

    return None


def simulate_take_profit(position: Position):
    """模拟止盈信号"""
    print_separator()
    print("[TAKE PROFIT] 模拟止盈信号")
    print_separator()

    # 生成持续上涨数据（触发止盈）
    quotes = generate_ascending_quotes(days=30, base_price=18.0, trend="up")

    # 创建分析器
    analyzer = QuoteDataAnalyzer(quotes)

    # 创建策略
    config = StrategyConfig(
        name="trend_scoring",
        params={
            "max_position_ratio": 0.30,
            "stop_loss_threshold": -0.05,
            "take_profit_threshold": 0.15,
        },
    )

    strategy = TrendScoringStrategy(config)

    # 更新持仓（盈利状态）
    position.current_price = quotes[-1].price
    position.updated_at = datetime.now()

    print(f"[TAKE PROFIT] 当前价格: {position.current_price:.2f}")
    print(f"[TAKE PROFIT] 成本价格: {position.avg_cost:.2f}")
    print(f"[TAKE PROFIT] 盈亏比例: {position.pnl_ratio*100:+.2f}%")
    print(f"[TAKE PROFIT] 浮动盈亏: {position.pnl:+.2f}")

    # 模拟账户信息
    account_info = {
        "cash": 85000.0,
        "total_value": 118000.0,
        "positions": [position],
    }

    # 生成信号
    signal = strategy.generate_signal(analyzer, account_info)

    if signal:
        print(f"[TAKE PROFIT] 信号类型: {signal.signal_type}")
        print(f"[TAKE PROFIT] 推理: {signal.reasoning}")
        print(f"[TAKE PROFIT] 卖出原因: {signal.metadata.get('reason', 'N/A')}")

        return signal
    else:
        print("[TAKE PROFIT] 未生成止盈信号")

    return None


def run_full_trading_test():
    """运行完整交易测试"""
    print_separator()
    print("[FULL TRADING] 完整交易流程测试")
    print_separator()

    # 初始资金
    initial_cash = 100000.0
    print(f"[FULL] 初始资金: {initial_cash:.2f}")

    # 1. 买入信号
    position = simulate_buy_signal()
    if not position:
        print("[FULL] 买入测试失败")
        return

    print_separator()
    print(f"[FULL] 买入后持仓状态:")
    print(f"      股票代码: {position.symbol}")
    print(f"      持股数量: {position.shares}")
    print(f"      成本价格: {position.avg_cost:.2f}")
    print(f"      剩余现金: {initial_cash - position.cost_value:.2f}")

    # 2. 测试止损
    print_separator()
    print("[FULL] 测试场景1: 止损")
    signal = simulate_stop_loss(position)
    if signal and signal.signal_type == "sell":
        print("[FULL] [OK] 止损信号生成成功")
    else:
        print("[FULL] [FAIL] 止损信号未生成")

    # 3. 测试止盈
    print_separator()
    print("[FULL] 测试场景2: 止盈")
    signal = simulate_take_profit(position)
    if signal and signal.signal_type == "sell":
        print("[FULL] [OK] 止盈信号生成成功")
    else:
        print("[FULL] [FAIL] 止盈信号未生成")

    # 4. 测试普通卖出
    print_separator()
    print("[FULL] 测试场景3: 趋势反转卖出")
    signal = simulate_sell_signal(position)
    if signal and signal.signal_type == "sell":
        print("[FULL] [OK] 卖出信号生成成功")
    else:
        print("[FULL] [FAIL] 卖出信号未生成")

    print_separator()
    print("[FULL] 完整交易流程测试完成")
    print_separator()


if __name__ == "__main__":
    print_separator()
    print(" [AI Trader Agent] Full Trading Cycle Test ")
    print_separator()
    print()
    print("测试内容:")
    print("  1. 买入信号生成 (多头趋势)")
    print("  2. 止损信号生成 (亏损触发)")
    print("  3. 止盈信号生成 (盈利触发)")
    print("  4. 卖出信号生成 (趋势反转)")
    print()

    run_full_trading_test()

    print_separator()
    print("[Complete] All trading cycle tests finished!")
    print_separator()