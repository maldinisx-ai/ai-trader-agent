# -*- coding: utf-8 -*-
"""
调试脚本 - 检查评分系统
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime, timedelta

from src.indicators import QuoteDataAnalyzer
from core.schemas import QuoteData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_ascending_quotes(days=30, base_price=10.0, trend="up"):
    """生成模拟行情数据 - 更强的上涨趋势"""
    quotes = []
    current_price = base_price

    for i in range(days):
        # 更强的上涨趋势
        if trend == "up":
            change = 0.008 if i < 15 else 0.003  # 前期快速上涨
        elif trend == "down":
            change = -0.005
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
            symbol="600000",
            name="浦发银行",
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


def test_scoring():
    """测试评分系统"""
    from core.scoring import TrendScoringSystem

    # 生成强势上涨数据
    quotes = generate_ascending_quotes(days=30, base_price=10.0, trend="up")

    print(f"数据点数量: {len(quotes)}")
    print(f"价格范围: {quotes[0].price:.2f} -> {quotes[-1].price:.2f}")

    # 创建分析器
    analyzer = QuoteDataAnalyzer(quotes)

    # 创建评分系统
    scorer = TrendScoringSystem()

    # 计算评分
    result = scorer.score(analyzer)

    print(f"\n=== 评分结果 ===")
    print(f"总分: {result.total_score}/100")
    print(f"买入信号: {result.buy_signal.value}")
    print(f"\n细分得分:")
    print(f"  趋势得分: {result.trend_score}/30")
    print(f"  乖离得分: {result.bias_score}/20")
    print(f"  量能得分: {result.volume_score}/15")
    print(f"  支撑得分: {result.support_score}/10")
    print(f"  MACD得分: {result.macd_score}/15")
    print(f"  RSI得分:  {result.rsi_score}/10")
    print(f"\n买入理由: {result.reasons}")
    print(f"风险因素: {result.risk_factors}")


if __name__ == "__main__":
    test_scoring()