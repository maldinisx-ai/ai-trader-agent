# -*- coding: utf-8 -*-
"""
Trend Scoring Strategy Demo

Demonstrate the enhanced indicators from daily_stock_analysis.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime, timedelta

from src.indicators import TechnicalIndicators, QuoteDataAnalyzer
from core.scoring import TrendScoringSystem, ScoreResult
from core.schemas import QuoteData, TrendStatus, BuySignal
from src.strategies.trend_scoring import TrendScoringStrategy
from src.strategies.base import StrategyConfig


logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_demo_data(days: int = 60) -> list:
    """Create demo data (uptrend)"""
    quotes = []
    base_price = 10.0

    for i in range(days):
        # Uptrend + small fluctuations
        change = 0.003 + (i % 5) * 0.002
        price = base_price * (1 + change)
        high = price * 1.015
        low = price * 0.985
        open_price = price * 0.995
        volume = 1000000 + (i % 3) * 200000

        quote = QuoteData(
            symbol="000001",
            name="Demo Stock",
            price=price,
            change=change * 100,
            volume=volume,
            amount=price * volume,
            high=high,
            low=low,
            open=open_price,
            timestamp=datetime(2024, 1, 1) + timedelta(days=i),
        )
        quotes.append(quote)
        base_price = price

    return quotes


def demo_indicators():
    """Demo new indicators"""
    print("\n" + "="*60)
    print("[Technical Indicators] Enhanced Features Demo")
    print("="*60)

    quotes = create_demo_data(20)
    analyzer = QuoteDataAnalyzer(quotes)

    # Bias
    print("\n[BIAS] Bias Rate:")
    for period in [5, 10, 20]:
        bias = analyzer.get_bias(period)
        ma = analyzer.get_sma(period)[-1]
        print(f"  MA{period:2d}: Bias = {bias:+6.2f}% (MA: {ma:.2f})")

    # Volume Ratio
    print("\n[VOLUME] Volume Analysis:")
    ratio = analyzer.get_volume_ratio(5)
    print(f"  Volume Ratio(5d): {ratio:.2f}x", end="")
    if ratio >= 1.5:
        print(" -> Heavy Volume")
    elif ratio <= 0.7:
        print(" -> Low Volume")
    else:
        print(" -> Normal")


def demo_scoring_system():
    """Demo scoring system"""
    print("\n" + "="*60)
    print("[Scoring System] Comprehensive Scoring Demo")
    print("="*60)

    quotes = create_demo_data(60)
    analyzer = QuoteDataAnalyzer(quotes)

    scorer = TrendScoringSystem()
    result = scorer.score(analyzer)

    print(f"\nTotal Score: {result.total_score}/100")
    print(f"Buy Signal: {result.buy_signal.value}")
    print(f"\nBreakdown:")
    print(f"  Trend Score:   {result.trend_score:2d}/30")
    print(f"  Bias Score:    {result.bias_score:2d}/20")
    print(f"  Volume Score:  {result.volume_score:2d}/15")
    print(f"  Support Score:  {result.support_score:2d}/10")
    print(f"  MACD Score:    {result.macd_score:2d}/15")
    print(f"  RSI Score:     {result.rsi_score:2d}/10")

    if result.reasons:
        print(f"\n[+] Buy Reasons:")
        for reason in result.reasons:
            print(f"  {reason}")

    if result.risk_factors:
        print(f"\n[!] Risk Factors:")
        for risk in result.risk_factors:
            print(f"  {risk}")


def demo_strategy():
    """Demo trend scoring strategy"""
    print("\n" + "="*60)
    print("[Strategy] Trend Scoring Strategy Demo")
    print("="*60)

    quotes = create_demo_data(60)
    analyzer = QuoteDataAnalyzer(quotes)

    # Create strategy
    config = StrategyConfig(
        name="trend_scoring",
        params={
            "bias_threshold": 5.0,
            "strong_buy_threshold": 75,
            "buy_threshold": 60,
        }
    )

    strategy = TrendScoringStrategy(config)

    # Simulate account
    account_info = {
        "cash": 100000,
        "total_value": 100000,
    }

    # Generate signal
    signal = strategy.generate_signal(analyzer, account_info)

    if signal:
        print(f"\nSignal Type: {signal.signal_type.value}")
        print(f"Symbol:      {signal.symbol}")
        print(f"Price:       {signal.price:.2f}")
        print(f"Quantity:    {signal.quantity}")
        print(f"Confidence:  {signal.confidence:.2f}")
        print(f"Reasoning:   {signal.reasoning}")
        print(f"\nMetadata:")
        print(f"  Total Score: {signal.metadata['total_score']}")
    else:
        print("\nNo signal generated")


def main():
    """Main demo function"""
    print("\n" + "="*60)
    print("[AI Trader Agent] Technical Indicators Enhancement Demo")
    print("="*60)
    print("\nFeatures ported from daily_stock_analysis:")
    print("  [√] Bias (BIAS) - Strict entry strategy core")
    print("  [√] Volume Ratio - Heavy/Low volume detection")
    print("  [√] Trend Status - 7-level classification")
    print("  [√] MACD/RSI Status - Detailed signal analysis")
    print("  [√] Support/Resistance - MA support detection")
    print("  [√] Scoring System - 100-point decision system")

    try:
        demo_indicators()
        demo_scoring_system()
        demo_strategy()

        print("\n" + "="*60)
        print("[Complete] Demo finished! All features working properly")
        print("="*60)

    except Exception as e:
        logger.error(f"Demo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
