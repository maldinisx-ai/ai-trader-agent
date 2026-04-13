# -*- coding: utf-8 -*-
"""
多维度综合策略测试脚本
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime, timedelta

from src.strategies.comprehensive import ComprehensiveStrategy
from src.strategies.base import StrategyConfig
from src.indicators import QuoteDataAnalyzer
from core.schemas import QuoteData, Position

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_quotes(symbol: str = "600000", days: int = 30, trend: str = "up"):
    """生成模拟行情数据"""
    quotes = []
    current_price = 10.0

    for i in range(days):
        if trend == "up":
            change = 0.008 if i < 15 else 0.003
        elif trend == "down":
            change = -0.006
        else:
            change = 0.0

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
            symbol=symbol,
            name="测试股票",
            price=round(current_price, 2),
            change=round(change * 100, 2),
            volume=volume,
            amount=volume * current_price * 100,
            high=round(high_price, 2),
            low=round(low_price, 2),
            open=round(open_price, 2),
            timestamp=datetime.now() - timedelta(days=days - i),
        )

        quotes.append(quote)

    return quotes


def test_comprehensive_strategy():
    """测试多维度综合策略"""
    print("=" * 70)
    print("多维度综合策略测试")
    print("=" * 70)

    # 生成行情数据
    quotes = generate_quotes(symbol="600519", days=30, trend="up")
    analyzer = QuoteDataAnalyzer(quotes)

    # 创建策略
    config = StrategyConfig(
        name="comprehensive",
        params={
            "data_dir": "data",
            "max_position_ratio": 0.30,
            "stop_loss_threshold": -0.08,
            "take_profit_threshold": 0.20,
        },
    )

    strategy = ComprehensiveStrategy(config)

    # 模拟账户信息
    account_info = {
        "cash": 100000.0,
        "total_value": 100000.0,
        "positions": [],
    }

    # 生成信号
    signal = strategy.generate_signal(analyzer, account_info)

    if signal:
        print("\n[买入信号]")
        print(f"  信号类型: {signal.signal_type}")
        print(f"  股票代码: {signal.symbol}")
        print(f"  买入价格: {signal.price:.2f}")
        print(f"  买入数量: {signal.quantity}")
        print(f"  置信度: {signal.confidence:.2f}")
        print(f"  推理: {signal.reasoning}")

        # 显示详细评分
        metadata = signal.metadata
        print("\n[详细评分]")
        print(f"  综合得分: {metadata.get('total_score', 'N/A')}/100")
        print(f"  技术面: {metadata.get('technical_score', 'N/A')}/100")
        print(f"  基本面: {metadata.get('fundamental_score', 'N/A')}/100")
        print(f"  资金面: {metadata.get('money_flow_score', 'N/A')}/100")

        comprehensive_result = metadata.get('comprehensive_result', {})
        if comprehensive_result:
            print("\n[细分得分]")
            print(f"  趋势: {comprehensive_result.get('trend_score', 0)}/30")
            print(f"  乖离: {comprehensive_result.get('bias_score', 0)}/20")
            print(f"  量能: {comprehensive_result.get('volume_score', 0)}/15")
            print(f"  ROE: {comprehensive_result.get('roe_score', 0)}/25")
            print(f"  成长: {comprehensive_result.get('growth_score', 0)}/25")
            print(f"  估值: {comprehensive_result.get('valuation_score', 0)}/25")
            print(f"  质量: {comprehensive_result.get('quality_score', 0)}/25")
            print(f"  主力: {comprehensive_result.get('main_flow_score', 0)}/40")
            print(f"  净流入: {comprehensive_result.get('net_flow_score', 0)}/30")
            print(f"  融资: {comprehensive_result.get('margin_score', 0)}/30")

    else:
        print("\n[未生成买入信号]")

    # 测试止损
    print("\n" + "=" * 70)
    print("测试止损场景")
    print("=" * 70)

    position = Position(
        symbol="600519",
        shares=1000,
        avg_cost=12.0,
        current_price=11.0,  # 亏损
        opened_at=datetime.now(),
    )

    account_info_with_position = {
        "cash": 88000.0,
        "total_value": 99000.0,
        "positions": [position],
    }

    signal = strategy.generate_signal(analyzer, account_info_with_position)

    if signal:
        print(f"\n[卖出信号]")
        print(f"  信号类型: {signal.signal_type}")
        print(f"  推理: {signal.reasoning}")
        if "reason" in signal.metadata:
            print(f"  卖出原因: {signal.metadata['reason']}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    test_comprehensive_strategy()