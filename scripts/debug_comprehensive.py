# -*- coding: utf-8 -*-
"""
综合策略调试 - 查看详细评分
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import datetime
import logging

logging.basicConfig(level=logging.WARNING)

from src.indicators import QuoteDataAnalyzer
from core.comprehensive_scoring import ComprehensiveScoringSystem
from core.scoring import TrendScoringSystem
from core.fundamental_scoring import FundamentalScorer
from core.money_flow_scoring import MoneyFlowScorer

def load_stock_data(symbol: str):
    """加载股票数据"""
    try:
        df = pd.read_csv(f'data/stocks/stock_{symbol}.csv')
        return df
    except Exception as e:
        print(f"加载数据失败 {symbol}: {e}")
        return None

def debug_scoring(symbol: str):
    """调试评分"""
    print("=" * 70)
    print(f"调试综合评分: {symbol}")
    print("=" * 70)

    # 加载K线数据
    df_klines = load_stock_data(symbol)
    if df_klines is None or df_klines.empty:
        print(f"[ERROR] 无法加载K线数据")
        return

    # 转换为QuoteData
    from core.schemas import QuoteData
    quotes = []
    for _, row in df_klines.iterrows():
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
            timestamp=datetime.now(),
        )
        quotes.append(quote)

    print(f"\n[K线数据]")
    print(f"  数据量: {len(quotes)}条")
    print(f"  最新价格: {quotes[-1].price:.2f}")

    # 技术面评分
    print(f"\n[技术面评分]")
    analyzer = QuoteDataAnalyzer(quotes)
    tech_scorer = TrendScoringSystem()
    tech_result = tech_scorer.score(analyzer)
    print(f"  总分: {tech_result.total_score}/100")
    print(f"  趋势: {tech_result.trend_score}/30")
    print(f"  乖离: {tech_result.bias_score}/20")
    print(f"  量能: {tech_result.volume_score}/15")
    print(f"  支撑: {tech_result.support_score}/10")
    print(f"  MACD: {tech_result.macd_score}/15")
    print(f"  RSI:  {tech_result.rsi_score}/10")
    print(f"  信号: {tech_result.buy_signal.value}")
    print(f"  理由: {tech_result.reasons}")
    print(f"  风险: {tech_result.risk_factors}")

    # 基本面评分
    print(f"\n[基本面评分]")
    fund_scorer = FundamentalScorer(data_dir="data")
    fund_result = fund_scorer.score(f"{symbol}.SZ" if symbol.startswith('000') or symbol.startswith('002') or symbol.startswith('300') else f"{symbol}.SH", quotes[-1].price)
    print(f"  总分: {fund_result.total_score}/100")
    print(f"  ROE: {fund_result.roe_score}/25")
    print(f"  成长: {fund_result.growth_score}/25")
    print(f"  估值: {fund_result.valuation_score}/25")
    print(f"  质量: {fund_result.quality_score}/25")
    print(f"  理由: {fund_result.reasons}")
    print(f"  风险: {fund_result.risk_factors}")

    # 资金面评分
    print(f"\n[资金面评分]")
    money_scorer = MoneyFlowScorer(data_dir="data")
    money_result = money_scorer.score(f"{symbol}.SZ" if symbol.startswith('000') or symbol.startswith('002') or symbol.startswith('300') else f"{symbol}.SH")
    print(f"  总分: {money_result.total_score}/100")
    print(f"  主力: {money_result.main_flow_score}/40")
    print(f"  净流入: {money_result.net_flow_score}/30")
    print(f"  融资: {money_result.margin_score}/30")
    print(f"  理由: {money_result.reasons}")
    print(f"  风险: {money_result.risk_factors}")

    # 综合评分
    print(f"\n[综合评分]")
    total_score = (
        tech_result.total_score * 0.35 +
        fund_result.total_score * 0.35 +
        money_result.total_score * 0.30
    )
    print(f"  综合得分: {total_score:.1f}/100")
    print(f"  = 技术面({tech_result.total_score}) × 0.35")
    print(f"  + 基本面({fund_result.total_score}) × 0.35")
    print(f"  + 资金面({money_result.total_score}) × 0.30")

    # 判断信号
    if total_score >= 75:
        signal = "强烈买入"
    elif total_score >= 60:
        signal = "买入"
    elif total_score >= 45:
        signal = "持有"
    elif total_score >= 30:
        signal = "观望"
    else:
        signal = "卖出"

    print(f"  信号: {signal}")

    print(f"\n{'=' * 70}")

if __name__ == "__main__":
    # 测试几只股票
    symbols = ['000001', '600519', '600036']

    for symbol in symbols:
        debug_scoring(symbol)