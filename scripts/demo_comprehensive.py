# -*- coding: utf-8 -*-
"""
综合策略演示 - 使用真实数据
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import datetime
import logging

from src.strategies.comprehensive import ComprehensiveStrategy
from src.strategies.base import StrategyConfig
from src.indicators import QuoteDataAnalyzer
from core.schemas import QuoteData

# 配置日志
logging.basicConfig(level=logging.WARNING)

def load_stock_data(symbol: str) -> list[QuoteData]:
    """加载股票数据"""
    try:
        # 读取K线数据
        df = pd.read_csv(f'data/stocks/stock_{symbol}.csv')

        quotes = []
        for _, row in df.iterrows():
            quote = QuoteData(
                symbol=symbol,
                name=row.get('name', ''),
                price=float(row['close']),
                change=0.0,
                volume=int(row['volume']),
                amount=float(row.get('amount', 0)),
                high=float(row['high']),
                low=float(row['low']),
                open=float(row['open']),
                timestamp=datetime.now(),  # 使用当前时间
            )
            quotes.append(quote)

        return quotes

    except Exception as e:
        print(f"加载数据失败 {symbol}: {e}")
        return []


def test_comprehensive_strategy():
    """测试综合策略"""
    print("=" * 70)
    print("多维度综合策略演示")
    print("=" * 70)

    # 使用已有数据的股票
    symbols = ['000001', '600519', '600036']

    for symbol in symbols:
        print(f"\n{'=' * 70}")
        print(f"测试股票: {symbol}")
        print(f"{'=' * 70}")

        # 加载数据
        quotes = load_stock_data(symbol)
        if not quotes:
            print(f"[ERROR] 无法加载 {symbol} 的数据")
            continue

        print(f"数据条数: {len(quotes)}")
        print(f"最新价格: {quotes[-1].price:.2f}")
        print(f"价格范围: {quotes[0].price:.2f} -> {quotes[-1].price:.2f}")

        # 创建分析器
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
            print(f"\n[买入信号]")
            print(f"  信号类型: {signal.signal_type}")
            print(f"  买入价格: {signal.price:.2f}")
            print(f"  买入数量: {signal.quantity}")
            print(f"  置信度: {signal.confidence:.2f}")
            print(f"  推理: {signal.reasoning}")

            # 显示详细评分
            metadata = signal.metadata
            print(f"\n[详细评分]")
            print(f"  综合得分: {metadata.get('total_score', 'N/A')}/100")
            print(f"  技术面: {metadata.get('technical_score', 'N/A')}/100")
            print(f"  基本面: {metadata.get('fundamental_score', 'N/A')}/100")
            print(f"  资金面: {metadata.get('money_flow_score', 'N/A')}/100")

            comprehensive_result = metadata.get('comprehensive_result', {})
            if comprehensive_result:
                print(f"\n[细分得分]")
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
            print(f"\n[未生成买入信号]")
            print(f"可能原因: 综合评分未达到买入阈值 (>=60)")

    print(f"\n{'=' * 70}")
    print("演示完成")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    test_comprehensive_strategy()