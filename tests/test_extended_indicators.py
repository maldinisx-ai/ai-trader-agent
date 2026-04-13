# -*- coding: utf-8 -*-
"""
扩展技术指标测试

测试新增的乖离率、量比、评分系统和趋势评分策略。
"""

import pytest
from datetime import datetime, timedelta

from src.indicators import TechnicalIndicators, QuoteDataAnalyzer
from core.scoring import TrendScoringSystem, ScoreResult
from core.schemas import (
    QuoteData,
    TrendStatus,
    VolumeStatus,
    MACDStatus,
    RSIStatus,
    BuySignal,
)
from src.strategies.trend_scoring import TrendScoringStrategy
from src.strategies.base import StrategyConfig


# ============================================================================
# 辅助函数
# ============================================================================

def create_sample_quotes(days: int = 60, trend: str = "up") -> list:
    """
    创建模拟行情数据

    Args:
        days: 天数
        trend: 趋势方向 (up/down/sideways)

    Returns:
        行情数据列表
    """
    quotes = []
    base_price = 10.0
    base_date = datetime(2024, 1, 1)

    for i in range(days):
        date = base_date + timedelta(days=i)

        if trend == "up":
            # 上升趋势
            change = 0.002 + (i * 0.0001) + (i % 3) * 0.005
        elif trend == "down":
            # 下降趋势
            change = -0.002 - (i * 0.0001) - (i % 3) * 0.005
        else:
            # 盘整
            change = (i % 5 - 2) * 0.003

        price = base_price * (1 + change)
        high = price * 1.02
        low = price * 0.98
        open_price = price * 0.99
        volume = 1000000 + (i % 10) * 100000

        quote = QuoteData(
            symbol="000001",
            name="测试股票",
            price=price,
            change=change * 100,
            volume=volume,
            amount=price * volume,
            high=high,
            low=low,
            open=open_price,
            timestamp=date,
        )
        quotes.append(quote)

    return quotes


# ============================================================================
# TechnicalIndicators 新方法测试
# ============================================================================

class TestBiasCalculation:
    """乖离率计算测试"""

    def test_bias_basic(self):
        """测试基本乖离率计算"""
        prices = [10, 12, 14, 16, 18, 20]
        ma = [10, 11, 12, 13, 14, 15]

        result = TechnicalIndicators.bias(prices, ma)

        assert len(result) == len(prices)
        assert abs(result[0] - 0) < 0.01  # (10-10)/10*100
        assert abs(result[1] - 9.09) < 0.1  # (12-11)/11*100
        assert abs(result[2] - 16.67) < 0.1  # (14-12)/12*100

    def test_bias_negative(self):
        """测试负乖离率"""
        prices = [10, 11, 12, 13, 14]
        ma = [12, 13, 14, 15, 16]

        result = TechnicalIndicators.bias(prices, ma)

        # 价格低于均线，负乖离率
        assert all(r < 0 for r in result if r is not None)

    def test_bias_mismatched_length(self):
        """测试长度不匹配"""
        prices = [10, 12, 14]
        ma = [10, 12]

        with pytest.raises(ValueError):
            TechnicalIndicators.bias(prices, ma)


class TestVolumeRatio:
    """量比计算测试"""

    def test_volume_ratio_basic(self):
        """测试基本量比计算"""
        volumes = [100, 120, 140, 160, 180, 200]

        result = TechnicalIndicators.volume_ratio(volumes, 3)

        assert len(result) == len(volumes)
        assert result[0] is None
        assert result[1] is None
        # 第3天: 140/((100+120+140)/3) = 140/120 = 1.167
        assert abs(result[2] - 1.167) < 0.01
        # 第4天: 160/((120+140+160)/3) = 160/140 = 1.143
        assert abs(result[3] - 1.143) < 0.01

    def test_volume_ratio_insufficient_data(self):
        """测试数据不足"""
        volumes = [100, 120]
        result = TechnicalIndicators.volume_ratio(volumes, 5)

        assert all(r is None for r in result)

    def test_volume_ratio_heavy(self):
        """测试放量"""
        volumes = [100, 100, 100, 100, 200]  # 最后一天放量

        result = TechnicalIndicators.volume_ratio(volumes, 3)

        # 最后一天量比应该 >= 1.5
        assert result[-1] >= 1.5


class TestQuoteDataAnalyzerExtensions:
    """QuoteDataAnalyzer 扩展测试"""

    def test_get_bias(self):
        """测试获取乖离率"""
        quotes = create_sample_quotes(days=20)
        analyzer = QuoteDataAnalyzer(quotes)

        bias_5 = analyzer.get_bias(5)
        bias_10 = analyzer.get_bias(10)
        bias_20 = analyzer.get_bias(20)

        # 应该返回数值
        assert isinstance(bias_5, float)
        assert isinstance(bias_10, float)
        assert isinstance(bias_20, float)

    def test_get_volume_ratio(self):
        """测试获取量比"""
        quotes = create_sample_quotes(days=10)
        analyzer = QuoteDataAnalyzer(quotes)

        ratio = analyzer.get_volume_ratio(5)

        assert isinstance(ratio, float)
        assert ratio > 0


# ============================================================================
# TrendScoringSystem 测试
# ============================================================================

class TestTrendScoringSystem:
    """趋势评分系统测试"""

    def test_score_uptrend(self):
        """测试上升趋势评分"""
        quotes = create_sample_quotes(days=60, trend="up")
        analyzer = QuoteDataAnalyzer(quotes)

        scorer = TrendScoringSystem()
        result = scorer.score(analyzer)

        assert isinstance(result, ScoreResult)
        assert 0 <= result.total_score <= 100
        assert result.buy_signal in BuySignal

    def test_score_downtrend(self):
        """测试下降趋势评分"""
        quotes = create_sample_quotes(days=60, trend="down")
        analyzer = QuoteDataAnalyzer(quotes)

        scorer = TrendScoringSystem()
        result = scorer.score(analyzer)

        assert isinstance(result, ScoreResult)
        # 下降趋势评分应该较低
        assert result.total_score < 50

    def test_score_insufficient_data(self):
        """测试数据不足"""
        quotes = create_sample_quotes(days=10)
        analyzer = QuoteDataAnalyzer(quotes)

        scorer = TrendScoringSystem()
        result = scorer.score(analyzer)

        assert result.total_score == 0
        assert result.buy_signal == BuySignal.WAIT
        assert "数据不足" in result.risk_factors[0]

    def test_score_components(self):
        """测试评分组成部分"""
        quotes = create_sample_quotes(days=60, trend="up")
        analyzer = QuoteDataAnalyzer(quotes)

        scorer = TrendScoringSystem()
        result = scorer.score(analyzer)

        # 检查各部分评分
        assert 0 <= result.trend_score <= 30
        assert 0 <= result.bias_score <= 20
        assert 0 <= result.volume_score <= 15
        assert 0 <= result.support_score <= 10
        assert 0 <= result.macd_score <= 15
        assert 0 <= result.rsi_score <= 10

    def test_custom_weights(self):
        """测试自定义权重"""
        quotes = create_sample_quotes(days=60)
        analyzer = QuoteDataAnalyzer(quotes)

        custom_weights = {
            'trend': 40,
            'bias': 10,
            'volume': 10,
            'support': 10,
            'macd': 15,
            'rsi': 15,
        }

        scorer = TrendScoringSystem(weights=custom_weights)
        result = scorer.score(analyzer)

        assert isinstance(result, ScoreResult)


# ============================================================================
# TrendScoringStrategy 测试
# ============================================================================

class TestTrendScoringStrategy:
    """趋势评分策略测试"""

    def test_strategy_initialization(self):
        """测试策略初始化"""
        config = StrategyConfig(
            name="trend_scoring",
            params={
                "bias_threshold": 5.0,
                "strong_buy_threshold": 75,
            }
        )

        strategy = TrendScoringStrategy(config)

        assert strategy.name == "trend_scoring"
        assert strategy.bias_threshold == 5.0
        assert strategy.strong_buy_threshold == 75

    def test_generate_buy_signal(self):
        """测试生成买入信号"""
        quotes = create_sample_quotes(days=60, trend="up")
        analyzer = QuoteDataAnalyzer(quotes)

        config = StrategyConfig(name="trend_scoring", params={})
        strategy = TrendScoringStrategy(config)

        account_info = {
            "cash": 100000,
            "total_value": 100000,
        }

        signal = strategy.generate_signal(analyzer, account_info)

        # 强势趋势可能产生买入信号
        if signal:
            assert signal.symbol == "000001"
            assert signal.quantity >= 100
            assert 0 <= signal.confidence <= 1

    def test_generate_sell_signal(self):
        """测试生成卖出信号"""
        quotes = create_sample_quotes(days=60, trend="down")
        analyzer = QuoteDataAnalyzer(quotes)

        config = StrategyConfig(name="trend_scoring", params={})
        strategy = TrendScoringStrategy(config)

        # 模拟持仓
        from core.schemas import Position
        position = Position(
            symbol="000001",
            shares=100,
            avg_cost=12,
            current_price=10,
            opened_at=datetime.now(),
        )

        account_info = {
            "cash": 90000,
            "total_value": 100000,
            "positions": [position],
        }

        signal = strategy.generate_signal(analyzer, account_info)

        # 可能产生卖出信号
        if signal:
            assert signal.symbol == "000001"
            assert signal.quantity == 100

    def test_stop_loss(self):
        """测试止损"""
        quotes = create_sample_quotes(days=20)
        analyzer = QuoteDataAnalyzer(quotes)

        config = StrategyConfig(
            name="trend_scoring",
            params={
                "stop_loss_threshold": -0.05,
            }
        )
        strategy = TrendScoringStrategy(config)

        # 模拟亏损持仓
        from core.schemas import Position
        position = Position(
            symbol="000001",
            shares=100,
            avg_cost=12,
            current_price=11,  # -8.33% 亏损
            opened_at=datetime.now(),
        )

        account_info = {
            "cash": 90000,
            "total_value": 100000,
            "positions": [position],
        }

        signal = strategy.generate_signal(analyzer, account_info)

        # 应该触发止损
        assert signal is not None
        assert signal.signal_type.value == "sell"
        assert "止损" in signal.reasoning

    def test_take_profit(self):
        """测试止盈"""
        quotes = create_sample_quotes(days=20)
        analyzer = QuoteDataAnalyzer(quotes)

        config = StrategyConfig(
            name="trend_scoring",
            params={
                "take_profit_threshold": 0.15,
            }
        )
        strategy = TrendScoringStrategy(config)

        # 模拟盈利持仓
        from core.schemas import Position
        position = Position(
            symbol="000001",
            shares=100,
            avg_cost=10,
            current_price=12,  # +20% 盈利
            opened_at=datetime.now(),
        )

        account_info = {
            "cash": 120000,
            "total_value": 132000,
            "positions": [position],
        }

        signal = strategy.generate_signal(analyzer, account_info)

        # 应该触发止盈
        assert signal is not None
        assert signal.signal_type.value == "sell"
        assert "止盈" in signal.reasoning


# ============================================================================
# 集成测试
# ============================================================================

class TestScoringIntegration:
    """评分系统集成测试"""

    def test_full_scoring_workflow(self):
        """测试完整评分流程"""
        # 创建上升趋势数据
        quotes = create_sample_quotes(days=60, trend="up")
        analyzer = QuoteDataAnalyzer(quotes)

        # 评分
        scorer = TrendScoringSystem()
        result = scorer.score(analyzer)

        # 验证结果结构
        assert hasattr(result, 'total_score')
        assert hasattr(result, 'buy_signal')
        assert hasattr(result, 'reasons')
        assert hasattr(result, 'risk_factors')

        # 验证信号类型
        assert result.buy_signal in BuySignal

    def test_scoring_with_real_data_pattern(self):
        """测试真实数据模式下的评分"""
        # 模拟多头排列数据
        quotes = []
        for i in range(60):
            price = 10 + i * 0.05  # 逐步上涨
            ma5 = price - 0.2  # MA5 略低于价格
            ma10 = price - 0.4  # MA10 更低
            ma20 = price - 0.6  # MA20 最低

            quote = QuoteData(
                symbol="000001",
                name="测试股票",
                price=price,
                change=0.5,
                volume=1000000,
                amount=price * 1000000,
                high=price * 1.02,
                low=price * 0.98,
                open=price * 0.99,
                timestamp=datetime(2024, 1, 1) + timedelta(days=i),
            )
            quotes.append(quote)

        analyzer = QuoteDataAnalyzer(quotes)
        scorer = TrendScoringSystem()
        result = scorer.score(analyzer)

        # 多头排列应该有较高评分
        assert result.total_score >= 60
        assert result.buy_signal in [BuySignal.BUY, BuySignal.STRONG_BUY]
