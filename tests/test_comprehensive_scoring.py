# -*- coding: utf-8 -*-
"""
测试综合评分系统
"""

from unittest.mock import MagicMock, patch
import pytest

# 确保模块导入以收集覆盖率
import core.comprehensive_scoring

from core.comprehensive_scoring import (
    ComprehensiveScoringSystem,
    ComprehensiveScore,
)
from core.schemas import BuySignal, QuoteData
from src.indicators import QuoteDataAnalyzer
from core.scoring import ScoreResult
from core.fundamental_scoring import FundamentalScore
from core.money_flow_scoring import MoneyFlowScore


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def sample_quotes():
    """创建样例行清数据"""
    return [
        QuoteData(symbol="600519", name="贵州茅台", price=1680.00, change=1.2, volume=1000000,
                  amount=1680000000.0, high=1695.00, low=1675.00, upper_limit=1688.00, lower_limit=1672.00),
        QuoteData(symbol="600519", name="贵州茅台", price=1685.00, change=1.5, volume=1200000,
                  amount=2022000000.0, high=1700.00, low=1680.00, upper_limit=1693.50, lower_limit=1676.50),
        QuoteData(symbol="600519", name="贵州茅台", price=1690.00, change=1.8, volume=1500000,
                  amount=2535000000.0, high=1710.00, low=1685.00, upper_limit=1699.00, lower_limit=1681.00),
        QuoteData(symbol="600519", name="贵州茅台", price=1688.00, change=1.6, volume=1100000,
                  amount=1856800000.0, high=1695.00, low=1680.00, upper_limit=1696.80, lower_limit=1679.20),
        QuoteData(symbol="600519", name="贵州茅台", price=1682.00, change=1.3, volume=900000,
                  amount=1513800000.0, high=1688.00, low=1675.00, upper_limit=1685.00, lower_limit=1674.80),
    ]


@pytest.fixture
def mock_analyzer(sample_quotes):
    """创建模拟的分析器"""
    analyzer = MagicMock(spec=QuoteDataAnalyzer)
    analyzer.quotes = sample_quotes
    return analyzer


@pytest.fixture
def mock_scoring_results():
    """创建模拟的评分结果"""
    tech_result = ScoreResult(
        total_score=75,
        buy_signal=BuySignal.BUY,
        trend_score=80,
        bias_score=70,
        volume_score=75,
        support_score=72,
        macd_score=68,
        rsi_score=70,
        reasons=["趋势向上", "量能放大"],
        risk_factors=["短期超买"],
    )

    fund_result = FundamentalScore(
        total_score=70,
        roe_score=75,
        growth_score=65,
        valuation_score=68,
        quality_score=72,
        reasons=["ROE优秀", "成长性好"],
        risk_factors=["估值偏高"],
    )

    money_result = MoneyFlowScore(
        total_score=65,
        main_flow_score=70,
        net_flow_score=60,
        margin_score=65,
        reasons=["主力流入"],
        risk_factors=["融资增加"],
    )

    return tech_result, fund_result, money_result


# ============================================
# ComprehensiveScore 测试
# ============================================

class TestComprehensiveScore:
    """测试综合评分结果"""

    def test_create_comprehensive_score(self):
        """测试创建综合评分结果"""
        score = ComprehensiveScore(
            total_score=70,
            technical_score=75,
            fundamental_score=70,
            money_flow_score=65,
            buy_signal=BuySignal.BUY,
            trend_score=80,
            bias_score=70,
            volume_score=75,
            roe_score=75,
            growth_score=65,
            valuation_score=68,
            quality_score=72,
            main_flow_score=70,
            net_flow_score=60,
            margin_score=65,
            reasons=["趋势向上", "ROE优秀"],
            risk_factors=["估值偏高", "短期超买"],
        )

        assert score.total_score == 70
        assert score.technical_score == 75
        assert score.buy_signal == BuySignal.BUY
        assert len(score.reasons) == 2
        assert len(score.risk_factors) == 2

    def test_to_dict(self):
        """测试转换为字典"""
        score = ComprehensiveScore(
            total_score=70,
            technical_score=75,
            fundamental_score=70,
            money_flow_score=65,
            buy_signal=BuySignal.BUY,
            trend_score=80,
            bias_score=70,
            volume_score=75,
            roe_score=75,
            growth_score=65,
            valuation_score=68,
            quality_score=72,
            main_flow_score=70,
            net_flow_score=60,
            margin_score=65,
            reasons=["趋势向上"],
            risk_factors=["估值偏高"],
        )

        result = score.to_dict()

        assert result['total_score'] == 70
        assert result['buy_signal'] == 'buy'  # BuySignal.BUY.value is lowercase
        assert result['technical_score'] == 75
        assert len(result['reasons']) == 1
        assert len(result['risk_factors']) == 1


# ============================================
# ComprehensiveScoringSystem 测试
# ============================================

class TestComprehensiveScoringSystem:
    """测试综合评分系统"""

    def test_init(self):
        """测试初始化"""
        system = ComprehensiveScoringSystem(data_dir="data")

        assert system.technical_scorer is not None
        assert system.fundamental_scorer is not None
        assert system.money_flow_scorer is not None

    def test_weights_configuration(self):
        """测试权重配置"""
        system = ComprehensiveScoringSystem()

        assert system.COMPREHENSIVE_WEIGHTS['technical'] == 35
        assert system.COMPREHENSIVE_WEIGHTS['fundamental'] == 35
        assert system.COMPREHENSIVE_WEIGHTS['money_flow'] == 30
        assert sum(system.COMPREHENSIVE_WEIGHTS.values()) == 100

    def test_signal_thresholds(self):
        """测试信号阈值"""
        system = ComprehensiveScoringSystem()

        assert system.SIGNAL_THRESHOLDS['strong_buy'] == 75
        assert system.SIGNAL_THRESHOLDS['buy'] == 60
        assert system.SIGNAL_THRESHOLDS['hold'] == 45
        assert system.SIGNAL_THRESHOLDS['wait'] == 30

    def test_score_with_mocked_scorers(self, mock_analyzer, mock_scoring_results):
        """测试评分（使用模拟的评分器）"""
        tech_result, fund_result, money_result = mock_scoring_results

        system = ComprehensiveScoringSystem(data_dir="data")

        # Mock 各个评分器
        system.technical_scorer.score = MagicMock(return_value=tech_result)
        system.fundamental_scorer.score = MagicMock(return_value=fund_result)
        system.money_flow_scorer.score = MagicMock(return_value=money_result)

        # 执行评分
        result = system.score("600519", mock_analyzer, current_price=1680.00)

        # 验证加权总分计算: 75*0.35 + 70*0.35 + 65*0.30 = 26.25 + 24.5 + 19.5 = 70.25
        assert result.total_score == 70  # 取整
        assert result.technical_score == 75
        assert result.fundamental_score == 70
        assert result.money_flow_score == 65
        assert result.buy_signal == BuySignal.BUY

        # 验证细分得分
        assert result.trend_score == 80
        assert result.bias_score == 70
        assert result.volume_score == 75
        assert result.roe_score == 75
        assert result.growth_score == 65
        assert result.valuation_score == 68
        assert result.quality_score == 72
        assert result.main_flow_score == 70
        assert result.net_flow_score == 60
        assert result.margin_score == 65

        # 验证理由和风险因素合并
        assert len(result.reasons) == 5  # 2 + 2 + 1 = 5
        assert "趋势向上" in result.reasons
        assert "ROE优秀" in result.reasons
        assert "主力流入" in result.reasons

        assert len(result.risk_factors) == 3
        assert "短期超买" in result.risk_factors
        assert "估值偏高" in result.risk_factors
        assert "融资增加" in result.risk_factors

    def test_determine_signal_strong_buy(self):
        """测试确定信号：强烈买入"""
        system = ComprehensiveScoringSystem()

        assert system._determine_signal(80) == BuySignal.STRONG_BUY
        assert system._determine_signal(75) == BuySignal.STRONG_BUY

    def test_determine_signal_buy(self):
        """测试确定信号：买入"""
        system = ComprehensiveScoringSystem()

        assert system._determine_signal(70) == BuySignal.BUY
        assert system._determine_signal(60) == BuySignal.BUY

    def test_determine_signal_hold(self):
        """测试确定信号：持有"""
        system = ComprehensiveScoringSystem()

        assert system._determine_signal(55) == BuySignal.HOLD
        assert system._determine_signal(45) == BuySignal.HOLD

    def test_determine_signal_wait(self):
        """测试确定信号：观望"""
        system = ComprehensiveScoringSystem()

        assert system._determine_signal(35) == BuySignal.WAIT
        assert system._determine_signal(30) == BuySignal.WAIT

    def test_determine_signal_sell(self):
        """测试确定信号：卖出"""
        system = ComprehensiveScoringSystem()

        assert system._determine_signal(25) == BuySignal.SELL
        assert system._determine_signal(10) == BuySignal.SELL
        assert system._determine_signal(0) == BuySignal.SELL


# ============================================
# 边界情况测试
# ============================================

class TestEdgeCases:
    """测试边界情况"""

    def test_score_boundary_75(self):
        """测试边界：75分（强烈买入阈值）"""
        system = ComprehensiveScoringSystem()
        assert system._determine_signal(75) == BuySignal.STRONG_BUY

    def test_score_boundary_60(self):
        """测试边界：60分（买入阈值）"""
        system = ComprehensiveScoringSystem()
        assert system._determine_signal(60) == BuySignal.BUY

    def test_score_boundary_45(self):
        """测试边界：45分（持有阈值）"""
        system = ComprehensiveScoringSystem()
        assert system._determine_signal(45) == BuySignal.HOLD

    def test_score_boundary_30(self):
        """测试边界：30分（观望阈值）"""
        system = ComprehensiveScoringSystem()
        assert system._determine_signal(30) == BuySignal.WAIT

    def test_score_boundary_29(self):
        """测试边界：29分（卖出）"""
        system = ComprehensiveScoringSystem()
        assert system._determine_signal(29) == BuySignal.SELL

    def test_perfect_score(self):
        """测试满分"""
        system = ComprehensiveScoringSystem()
        assert system._determine_signal(100) == BuySignal.STRONG_BUY

    def test_zero_score(self):
        """测试零分"""
        system = ComprehensiveScoringSystem()
        assert system._determine_signal(0) == BuySignal.SELL


# ============================================
# 集成测试
# ============================================

class TestIntegration:
    """集成测试"""

    def test_full_scoring_pipeline(self, mock_analyzer, mock_scoring_results):
        """测试完整评分流程"""
        tech_result, fund_result, money_result = mock_scoring_results

        system = ComprehensiveScoringSystem(data_dir="data")

        # Mock 各个评分器
        system.technical_scorer.score = MagicMock(return_value=tech_result)
        system.fundamental_scorer.score = MagicMock(return_value=fund_result)
        system.money_flow_scorer.score = MagicMock(return_value=money_result)

        # 执行评分
        result = system.score("600519", mock_analyzer, current_price=1680.00)

        # 验证所有评分器都被调用
        system.technical_scorer.score.assert_called_once_with(mock_analyzer)
        system.fundamental_scorer.score.assert_called_once_with("600519", 1680.00)
        system.money_flow_scorer.score.assert_called_once_with("600519")

        # 验证结果完整性
        assert result.total_score >= 0 and result.total_score <= 100
        assert isinstance(result.buy_signal, BuySignal)
        assert isinstance(result.reasons, list)
        assert isinstance(result.risk_factors, list)
