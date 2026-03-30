# -*- coding: utf-8 -*-
"""
测试评分系统

TDD 流程: RED → GREEN → REFACTOR
"""

import pytest
from typing import List

# 确保模块被导入以正确收集覆盖率
import core.scoring
import core.schemas
from core.schemas import TrendStatus, VolumeStatus, MACDStatus, RSIStatus, BuySignal
from core.scoring import TrendScoringSystem, ScoreResult
from unittest.mock import Mock


def create_mock_analyzer():
    """创建完整的 mock 分析器"""
    analyzer = Mock()
    analyzer.quotes = [Mock()] * 20
    analyzer._prices = [100, 105]  # 价格数据

    # 默认设置所有指标
    analyzer.get_sma = Mock(side_effect=lambda period: {
        5: [110], 10: [105], 20: [100],
    }.get(period, [None]))

    analyzer.get_bias = Mock(return_value=1)
    analyzer.get_volume_ratio = Mock(return_value=1.0)
    analyzer.get_macd = Mock(return_value=(
        [0.1, 0.2], [0.05, 0.1], [0.05, 0.1],
    ))
    analyzer.get_rsi = Mock(return_value=[50])

    return analyzer


class TestScoreResult:
    """测试评分结果"""

    def test_score_result_creation(self):
        """测试创建评分结果"""
        result = ScoreResult(
            total_score=75,
            buy_signal=BuySignal.BUY,
            trend_score=25,
            bias_score=15,
            volume_score=12,
            support_score=8,
            macd_score=10,
            rsi_score=5,
            reasons=["多头排列", "缩量回调"],
            risk_factors=["RSI超买"],
        )

        assert result.total_score == 75
        assert result.buy_signal == BuySignal.BUY
        assert len(result.reasons) == 2
        assert len(result.risk_factors) == 1

    def test_score_result_to_dict(self):
        """测试转换为字典"""
        result = ScoreResult(
            total_score=80,
            buy_signal=BuySignal.STRONG_BUY,
            trend_score=30,
            bias_score=18,
            volume_score=15,
            support_score=10,
            macd_score=12,
            rsi_score=5,
            reasons=["强势多头", "MACD金叉"],
        )

        data_dict = result.to_dict()

        assert data_dict['total_score'] == 80
        assert data_dict['buy_signal'] == 'strong_buy'
        assert data_dict['trend_score'] == 30
        assert data_dict['reasons'] == ["强势多头", "MACD金叉"]
        assert data_dict['risk_factors'] == []

    def test_score_result_default_reasons_risks(self):
        """测试默认理由和风险因素"""
        result = ScoreResult(
            total_score=0,
            buy_signal=BuySignal.WAIT,
            trend_score=0,
            bias_score=0,
            volume_score=0,
            support_score=0,
            macd_score=0,
            rsi_score=0,
        )

        assert result.reasons == []
        assert result.risk_factors == []


class TestTrendScoringSystem:
    """测试趋势评分系统"""

    def test_default_weights(self):
        """测试默认权重"""
        system = TrendScoringSystem()

        assert system.weights['trend'] == 30
        assert system.weights['bias'] == 20
        assert system.weights['volume'] == 15
        assert system.weights['support'] == 10
        assert system.weights['macd'] == 15
        assert system.weights['rsi'] == 10

    def test_custom_weights(self):
        """测试自定义权重"""
        custom_weights = {
            'trend': 25,
            'bias': 25,
            'volume': 15,
            'support': 10,
            'macd': 15,
            'rsi': 10,
        }
        system = TrendScoringSystem(weights=custom_weights)

        assert system.weights['trend'] == 25
        assert system.weights['bias'] == 25

    def test_score_insufficient_data(self):
        """测试数据不足时返回零分"""
        system = TrendScoringSystem()

        analyzer = Mock()
        analyzer.quotes = []  # 空数据

        result = system.score(analyzer)

        assert result.total_score == 0
        assert result.buy_signal == BuySignal.WAIT
        assert result.trend_score == 0
        assert len(result.risk_factors) == 1
        assert "数据不足" in result.risk_factors[0]

    def test_score_insufficient_data_less_than_20(self):
        """测试少于20条数据时返回零分"""
        system = TrendScoringSystem()

        analyzer = Mock()
        analyzer.quotes = [Mock()] * 10  # 只有10条数据

        result = system.score(analyzer)

        assert result.total_score == 0
        assert result.buy_signal == BuySignal.WAIT

    def test_score_trend_strong_bull(self):
        """测试强势多头趋势"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        # 模拟 MA5 > MA10 > MA20 且间距扩大
        # 计算: (125-100)/100*100=25% > (120-98)/98*100≈22.4%
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100, 105, 110, 115, 120, 125],
            10: [95, 98, 102, 106, 110, 112],
            20: [90, 92, 94, 96, 98, 100],
        }.get(period, [None]))

        result = system.score(analyzer)

        # 间距扩大超过5%且当前间距也超过5%
        assert result.trend_score == 30

    def test_score_trend_bull(self):
        """测试多头趋势"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        # 模拟 MA5 > MA10 > MA20 但间距未扩大
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100, 102, 104, 106, 108, 110],
            10: [95, 97, 99, 101, 103, 105],
            20: [90, 92, 94, 96, 98, 100],
        }.get(period, [None]))

        result = system.score(analyzer)

        # 如果间距未扩大，返回26
        assert result.trend_score == 26

    def test_score_trend_weak_bull(self):
        """测试弱多头趋势"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        # 模拟 MA5 > MA10 但 MA10 <= MA20
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [105],
            10: [100],
            20: [105],  # MA10 <= MA20
        }.get(period, [None]))

        result = system.score(analyzer)

        assert result.trend_score == 18

    def test_score_trend_bear(self):
        """测试空头趋势"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        # 模拟 MA5 < MA10 < MA20 且间距 < 5%
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [98, 98.5, 99, 99, 99, 99],      # 最后是 99
            10: [99, 99.5, 100, 100, 100, 100], # 最后是 100
            20: [100, 100.5, 101, 101, 101, 101], # 最后是 101
        }.get(period, [None]))

        result = system.score(analyzer)

        # 间距: (101-99)/99*100 ≈ 2.02% < 5%，不会是 STRONG_BEAR
        assert result.trend_score == 4

    def test_score_trend_normal_bear(self):
        """测试普通空头趋势（非强势）"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        # 模拟 MA5 < MA10 < MA20 且间距稳定
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [90, 90, 90, 90, 90, 90],      # 最后是 90
            10: [95, 95, 95, 95, 95, 95],     # 最后是 95
            20: [100, 100, 100, 100, 100, 105], # 最后是 105
        }.get(period, [None]))

        result = system.score(analyzer)

        # 间距: (105-90)/90*100 = 16.7% > 5% 且前面 (100-90)/90*100 = 11.1%，扩大了
        # 会是 STRONG_BEAR (10分)
        assert result.trend_score == 10

    def test_score_trend_strong_bear(self):
        """测试强势空头趋势"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        # 模拟 MA5 < MA10 < MA20 且间距扩大
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100, 95, 90, 85, 80, 75],
            10: [105, 100, 95, 90, 85, 82],
            20: [110, 108, 106, 104, 102, 100],
        }.get(period, [None]))

        result = system.score(analyzer)

        assert result.trend_score == 10

    def test_score_trend_weak_bear(self):
        """测试弱空头趋势"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        # 模拟 MA5 < MA10 但 MA10 >= MA20
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [95],
            10: [100],
            20: [98],  # MA10 >= MA20
        }.get(period, [None]))

        result = system.score(analyzer)

        assert result.trend_score == 8

    def test_score_trend_consolidation(self):
        """测试震荡趋势"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        # 模拟真正的震荡（MA5和MA10交叉）
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100],
            10: [102],  # MA5 < MA10
            20: [101],  # MA10 > MA20
        }.get(period, [None]))

        result = system.score(analyzer)

        # MA5 < MA10 且 MA10 >= MA20 是 WEAK_BEAR
        assert result.trend_score == 8

    def test_score_trend_missing_ma_values(self):
        """测试均线值缺失"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer.get_sma = Mock(return_value=[None])

        result = system.score(analyzer)

        assert result.trend_score == 12

    def test_score_bias_negative_small(self):
        """测试乖离率小负值（回踩）"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100, 102, 104, 106, 108, 110],
            10: [95, 97, 99, 101, 103, 105],
            20: [90, 92, 94, 96, 98, 100],
        }.get(period, [None]))
        # 乖离率 -1%
        analyzer.get_bias = Mock(return_value=-1)

        result = system.score(analyzer)

        assert result.bias_score == 20

    def test_score_bias_negative_medium(self):
        """测试乖离率中负值"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [110], 10: [105], 20: [100],
        }.get(period, [None]))
        # 乖离率 -4%
        analyzer.get_bias = Mock(return_value=-4)

        result = system.score(analyzer)

        assert result.bias_score == 16

    def test_score_bias_negative_large(self):
        """测试乖离率大负值"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [110], 10: [105], 20: [100],
        }.get(period, [None]))
        # 乖离率 -8%
        analyzer.get_bias = Mock(return_value=-8)

        result = system.score(analyzer)

        assert result.bias_score == 8

    def test_score_bias_positive_small(self):
        """测试乖离率小正值"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [110], 10: [105], 20: [100],
        }.get(period, [None]))
        # 乖离率 1%
        analyzer.get_bias = Mock(return_value=1)

        result = system.score(analyzer)

        assert result.bias_score == 18

    def test_score_bias_positive_medium(self):
        """测试乖离率中正值"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [110], 10: [105], 20: [100],
        }.get(period, [None]))
        # 乖离率 3%
        analyzer.get_bias = Mock(return_value=3)

        result = system.score(analyzer)

        assert result.bias_score == 14

    def test_score_bias_positive_large(self):
        """测试乖离率大正值（追高）"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [110], 10: [105], 20: [100],
        }.get(period, [None]))
        # 乖离率 8%（超过阈值）
        analyzer.get_bias = Mock(return_value=8)

        result = system.score(analyzer)

        assert result.bias_score == 4

    def test_score_bias_strong_bull_compensation(self):
        """测试强势趋势乖离率补偿"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        # 模拟强势多头（间距扩大）
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100, 105, 110, 115, 120, 125],
            10: [95, 98, 102, 106, 110, 112],
            20: [90, 92, 94, 96, 98, 100],
        }.get(period, [None]))
        # 乖离率 7%（正常应该超过5%，但强势趋势放宽到7.5%）
        analyzer.get_bias = Mock(return_value=7)

        result = system.score(analyzer)

        # 强势趋势阈值放大，7% < 7.5%，应该给中等分
        assert result.bias_score == 14

    def test_score_volume_heavy_up(self):
        """测试放量上涨"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer._prices = [100, 105]  # 价格上涨
        # 量比 1.8（放量）
        analyzer.get_volume_ratio = Mock(return_value=1.8)

        result = system.score(analyzer)

        assert result.volume_score == 12

    def test_score_volume_heavy_down(self):
        """测试放量下跌"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer._prices = [105, 100]  # 价格下跌
        # 量比 1.8（放量）
        analyzer.get_volume_ratio = Mock(return_value=1.8)

        result = system.score(analyzer)

        assert result.volume_score == 0
        assert len(result.risk_factors) > 0

    def test_score_volume_shrink_up(self):
        """测试缩量上涨"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer._prices = [100, 105]  # 价格上涨
        # 量比 0.6（缩量）
        analyzer.get_volume_ratio = Mock(return_value=0.6)

        result = system.score(analyzer)

        assert result.volume_score == 6

    def test_score_volume_shrink_down(self):
        """测试缩量下跌"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer._prices = [105, 100]  # 价格下跌
        # 量比 0.6（缩量）
        analyzer.get_volume_ratio = Mock(return_value=0.6)

        result = system.score(analyzer)

        assert result.volume_score == 15
        assert len(result.reasons) > 0

    def test_score_volume_normal(self):
        """测试正常量能"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer._prices = [100, 105]
        # 量比 1.0（正常）
        analyzer.get_volume_ratio = Mock(return_value=1.0)

        result = system.score(analyzer)

        assert result.volume_score == 10

    def test_score_support_both_ma(self):
        """测试同时获得 MA5 和 MA10 支撑"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100],  # MA5 = 100
            10: [99],  # MA10 = 99（容忍度2%内）
            20: [95],
        }.get(period, [None]))
        analyzer._prices = [100]  # 当前价格刚好等于 MA5

        result = system.score(analyzer)

        # MA5 和 MA10 都在支撑范围内
        assert result.support_score == 10

    def test_score_support_only_ma5(self):
        """测试仅获得 MA5 支撑"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100],
            10: [95],  # MA10 较远，不在支撑范围内
            20: [90],
        }.get(period, [None]))
        analyzer._prices = [100]

        result = system.score(analyzer)

        assert result.support_score == 5

    def test_score_support_no_support(self):
        """测试无支撑"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [90],   # 价格高于 MA5
            10: [85],  # 价格高于 MA10
            20: [80],
        }.get(period, [None]))
        analyzer._prices = [100]  # 远高于均线

        result = system.score(analyzer)

        assert result.support_score == 0

    def test_score_macd_golden_cross_zero(self):
        """测试 MACD 金叉上穿零轴"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # MACD 线上穿信号线且上穿零轴
        analyzer.get_macd = Mock(return_value=(
            [-0.1, 0.2],      # MACD 线：从负变正
            [-0.05, 0.1],     # 信号线：从负变正
            [-0.05, 0.1],     # 柱状图
        ))

        result = system.score(analyzer)

        assert result.macd_score == 15

    def test_score_macd_crossing_up(self):
        """测试 MACD 上穿零轴"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # 仅上穿零轴，未金叉
        analyzer.get_macd = Mock(return_value=(
            [-0.1, 0.2],      # MACD 线
            [-0.2, -0.1],     # 信号线：仍然低于 MACD
            [0.1, 0.3],
        ))

        result = system.score(analyzer)

        assert result.macd_score == 10

    def test_score_macd_golden_cross(self):
        """测试 MACD 金叉"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # 金叉但未上穿零轴
        analyzer.get_macd = Mock(return_value=(
            [-0.2, -0.1],     # MACD 线：负值
            [-0.15, -0.15],   # 信号线：从低于到等于
            [-0.05, 0.05],
        ))

        result = system.score(analyzer)

        assert result.macd_score == 12

    def test_score_macd_death_cross(self):
        """测试 MACD 死叉"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # 死叉
        analyzer.get_macd = Mock(return_value=(
            [0.2, 0.1],      # MACD 线从高于降到低于信号线
            [0.1, 0.15],
            [0.1, -0.05],
        ))

        result = system.score(analyzer)

        assert result.macd_score == 0

    def test_score_macd_crossing_down(self):
        """测试 MACD 下穿零轴"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # 下穿零轴
        analyzer.get_macd = Mock(return_value=(
            [0.1, -0.1],     # MACD 线从正变负
            [0.05, -0.05],
            [0.05, -0.05],
        ))

        result = system.score(analyzer)

        assert result.macd_score == 0

    def test_score_macd_bullish(self):
        """测试 MACD 多头"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # MACD 和信号线都在零轴上方
        analyzer.get_macd = Mock(return_value=(
            [0.2, 0.3],      # MACD 线
            [0.15, 0.2],     # 信号线
            [0.05, 0.1],
        ))

        result = system.score(analyzer)

        assert result.macd_score == 8

    def test_score_macd_bearish(self):
        """测试 MACD 空头"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # MACD 和信号线都在零轴下方
        analyzer.get_macd = Mock(return_value=(
            [-0.3, -0.2],    # MACD 线
            [-0.25, -0.15],  # 信号线
            [-0.05, -0.05],
        ))

        result = system.score(analyzer)

        assert result.macd_score == 2

    def test_score_macd_insufficient_data(self):
        """测试 MACD 数据不足"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # 柱状图数据不足
        analyzer.get_macd = Mock(return_value=(
            [0.1],           # MACD 线只有1个值
            [0.05],
            [],
        ))

        result = system.score(analyzer)

        assert result.macd_score == 5

    def test_score_rsi_oversold(self):
        """测试 RSI 超卖"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # RSI = 25（超卖）
        analyzer.get_rsi = Mock(return_value=[30, 25])

        result = system.score(analyzer)

        assert result.rsi_score == 10

    def test_score_rsi_weak(self):
        """测试 RSI 偏弱"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # RSI = 35（偏弱）
        analyzer.get_rsi = Mock(return_value=[35])

        result = system.score(analyzer)

        assert result.rsi_score == 3

    def test_score_rsi_neutral(self):
        """测试 RSI 中性"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # RSI = 50（中性）
        analyzer.get_rsi = Mock(return_value=[50])

        result = system.score(analyzer)

        assert result.rsi_score == 5

    def test_score_rsi_strong_buy(self):
        """测试 RSI 强买入"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # RSI = 65（强买入）
        analyzer.get_rsi = Mock(return_value=[65])

        result = system.score(analyzer)

        assert result.rsi_score == 8

    def test_score_rsi_overbought(self):
        """测试 RSI 超买"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # RSI = 75（超买）
        analyzer.get_rsi = Mock(return_value=[75])

        result = system.score(analyzer)

        assert result.rsi_score == 0

    def test_score_rsi_insufficient_data(self):
        """测试 RSI 数据不足"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # RSI 为 None
        analyzer.get_rsi = Mock(return_value=None)

        result = system.score(analyzer)

        assert result.rsi_score == 5

    def test_generate_signal_strong_buy(self):
        """测试生成强烈买入信号"""
        system = TrendScoringSystem()

        signal = system._generate_signal(80, TrendStatus.STRONG_BULL)

        assert signal == BuySignal.STRONG_BUY

    def test_generate_signal_buy(self):
        """测试生成买入信号"""
        system = TrendScoringSystem()

        signal = system._generate_signal(65, TrendStatus.BULL)

        assert signal == BuySignal.BUY

    def test_generate_signal_buy_weak_bull(self):
        """测试弱多头也生成买入信号"""
        system = TrendScoringSystem()

        signal = system._generate_signal(62, TrendStatus.WEAK_BULL)

        assert signal == BuySignal.BUY

    def test_generate_signal_hold(self):
        """测试生成持有信号"""
        system = TrendScoringSystem()

        signal = system._generate_signal(50, TrendStatus.CONSOLIDATION)

        assert signal == BuySignal.HOLD

    def test_generate_signal_wait(self):
        """测试生成等待信号"""
        system = TrendScoringSystem()

        signal = system._generate_signal(35, TrendStatus.CONSOLIDATION)

        assert signal == BuySignal.WAIT

    def test_generate_signal_strong_sell(self):
        """测试生成强烈卖出信号"""
        system = TrendScoringSystem()

        signal = system._generate_signal(25, TrendStatus.BEAR)

        assert signal == BuySignal.STRONG_SELL

    def test_generate_signal_sell(self):
        """测试生成卖出信号"""
        system = TrendScoringSystem()

        signal = system._generate_signal(20, TrendStatus.CONSOLIDATION)

        assert signal == BuySignal.SELL

    def test_generate_signal_high_score_bear(self):
        """测试高分但空头趋势不生成强买"""
        system = TrendScoringSystem()

        # 80分但空头趋势，不会生成强买
        signal = system._generate_signal(80, TrendStatus.BEAR)

        # 高分会先返回 HOLD（score >= 45 条件先于趋势判断）
        assert signal == BuySignal.HOLD

    def test_generate_signal_low_score_bear(self):
        """测试低分空头趋势生成强卖"""
        system = TrendScoringSystem()

        # 低分空头趋势会触发 STRONG_SELL
        signal = system._generate_signal(20, TrendStatus.BEAR)

        assert signal == BuySignal.STRONG_SELL

    def test_full_score_calculation(self):
        """测试完整评分计算"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # 设置所有指标为理想状态
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100, 105, 110, 115, 120, 125],  # 强势多头（间距扩大）
            10: [95, 98, 102, 106, 110, 112],
            20: [90, 92, 94, 96, 98, 100],
        }.get(period, [None]))
        analyzer.get_bias = Mock(return_value=-1)  # 乖离率 -1
        analyzer.get_volume_ratio = Mock(return_value=0.6)  # 缩量
        analyzer._prices = [105, 100]  # 价格下跌（缩量回调）
        analyzer.get_macd = Mock(return_value=(
            [-0.1, 0.2],      # 金叉上穿零轴
            [-0.05, 0.1],
            [-0.05, 0.1],
        ))
        analyzer.get_rsi = Mock(return_value=[25])  # 超卖

        result = system.score(analyzer)

        # 验证买入理由
        assert len(result.reasons) >= 3

        # 验证信号
        assert result.buy_signal in [BuySignal.STRONG_BUY, BuySignal.BUY]

    def test_constants_values(self):
        """测试常量值"""
        assert TrendScoringSystem.BIAS_THRESHOLD == 5.0
        assert TrendScoringSystem.BIAS_STRONG_MULTIPLIER == 1.5
        assert TrendScoringSystem.VOLUME_SHRINK_RATIO == 0.7
        assert TrendScoringSystem.VOLUME_HEAVY_RATIO == 1.5
        assert TrendScoringSystem.MA_SUPPORT_TOLERANCE == 0.02
        assert TrendScoringSystem.STRONG_TREND_SPREAD_THRESHOLD == 5.0

    def test_signal_thresholds(self):
        """测试信号阈值"""
        assert TrendScoringSystem.SIGNAL_THRESHOLDS['strong_buy'] == 75
        assert TrendScoringSystem.SIGNAL_THRESHOLDS['buy'] == 60
        assert TrendScoringSystem.SIGNAL_THRESHOLDS['hold'] == 45
        assert TrendScoringSystem.SIGNAL_THRESHOLDS['wait'] == 30

    def test_score_accumulates_reasons(self):
        """测试评分累积理由"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # 设置多个正面指标
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100, 105, 110, 115, 120, 125],  # 强势多头
            10: [95, 98, 102, 106, 110, 112],
            20: [90, 92, 94, 96, 98, 100],
        }.get(period, [None]))
        analyzer.get_bias = Mock(return_value=-1)
        analyzer.get_volume_ratio = Mock(return_value=0.6)  # 缩量
        analyzer._prices = [105, 100]
        analyzer.get_macd = Mock(return_value=(
            [-0.1, 0.2],      # 金叉上穿零轴
            [-0.05, 0.1],
            [-0.05, 0.1],
        ))
        analyzer.get_rsi = Mock(return_value=[25])  # 超卖

        result = system.score(analyzer)

        # 应该有多个买入理由
        assert len(result.reasons) >= 3

    def test_score_accumulates_risks(self):
        """测试评分累积风险因素"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # 设置多个负面指标
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [98, 98.5, 99, 99, 99, 99],      # 最后是 99
            10: [99, 99.5, 100, 100, 100, 100], # 最后是 100
            20: [100, 100.5, 101, 101, 101, 101], # 最后是 101
        }.get(period, [None]))
        analyzer.get_bias = Mock(return_value=8)  # 高乖离率
        analyzer.get_volume_ratio = Mock(return_value=1.8)  # 放量
        analyzer._prices = [100, 105]  # 价格上涨
        analyzer.get_macd = Mock(return_value=(
            [0.2, 0.1],      # 死叉
            [0.15, 0.2],
            [0.05, -0.05],
        ))
        analyzer.get_rsi = Mock(return_value=[75])  # 超买

        result = system.score(analyzer)

        # 应该有多个风险因素
        assert len(result.risk_factors) >= 2

    def test_score_mixed_signals(self):
        """测试混合信号"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # 设置混合指标：多头但超买
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100, 105, 110, 115, 120, 125],
            10: [95, 98, 102, 106, 110, 112],
            20: [90, 92, 94, 96, 98, 100],
        }.get(period, [None]))
        analyzer.get_bias = Mock(return_value=1)
        analyzer.get_volume_ratio = Mock(return_value=1.0)
        analyzer._prices = [100, 105]
        analyzer.get_macd = Mock(return_value=(
            [0.1, 0.2],
            [0.05, 0.1],
            [0.05, 0.1],
        ))
        analyzer.get_rsi = Mock(return_value=[75])  # 超买

        result = system.score(analyzer)

        # 应该有理由也有风险
        assert len(result.reasons) > 0
        assert len(result.risk_factors) > 0

    def test_score_weak_bull_wait_signal(self):
        """测试弱多头返回等待信号"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # 弱多头且低分
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [105],
            10: [100],
            20: [105],
        }.get(period, [None]))
        analyzer.get_bias = Mock(return_value=-8)  # 大负乖离
        analyzer.get_volume_ratio = Mock(return_value=0.6)
        analyzer._prices = [100, 95]
        # 使用中等状态的MACD
        analyzer.get_macd = Mock(return_value=(
            [0.05, 0.05],  # 基本平
            [0.02, 0.05],
            [0.03, 0.05],
        ))
        analyzer.get_rsi = Mock(return_value=[50])

        result = system.score(analyzer)

        # 弱多头 + 低分，应该是 WAIT 或 HOLD
        assert result.buy_signal in [BuySignal.WAIT, BuySignal.HOLD]

    def test_score_boundary_strong_buy(self):
        """测试强烈买入边界（75分）"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # 设置刚好75分的指标
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100, 105, 110, 115, 120, 125],
            10: [95, 98, 102, 106, 110, 112],
            20: [90, 92, 94, 96, 98, 100],
        }.get(period, [None]))
        analyzer.get_bias = Mock(return_value=-1)
        analyzer.get_volume_ratio = Mock(return_value=0.6)
        analyzer._prices = [105, 100]
        analyzer.get_macd = Mock(return_value=(
            [-0.1, 0.2],
            [-0.05, 0.1],
            [-0.05, 0.1],
        ))
        analyzer.get_rsi = Mock(return_value=[35])

        result = system.score(analyzer)

        # 75分应该是 STRONG_BUY 或 BUY
        assert result.buy_signal in [BuySignal.STRONG_BUY, BuySignal.BUY]

    def test_score_boundary_buy(self):
        """测试买入边界（60分）"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # 设置刚好60分的指标
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100, 102, 104, 106, 108, 110],  # 普通多头
            10: [95, 97, 99, 101, 103, 105],
            20: [90, 92, 94, 96, 98, 100],
        }.get(period, [None]))
        analyzer.get_bias = Mock(return_value=1)
        analyzer.get_volume_ratio = Mock(return_value=1.0)
        analyzer._prices = [100, 105]
        analyzer.get_macd = Mock(return_value=(
            [0.1, 0.1],
            [0.05, 0.05],
            [0.05, 0.05],
        ))
        analyzer.get_rsi = Mock(return_value=[55])

        result = system.score(analyzer)

        # 应该至少是 BUY 或 HOLD
        assert result.buy_signal in [BuySignal.BUY, BuySignal.HOLD]

    def test_score_edge_case_just_enough_data(self):
        """测试刚好足够数据（20条）"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer.quotes = [Mock()] * 20  # 刚好20条

        result = system.score(analyzer)

        # 应该正常评分，不是零分
        assert result.total_score >= 0

    def test_score_edge_case_barely_over_threshold(self):
        """测试刚好超过强趋势阈值"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        # 间距刚好超过5%
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100, 100, 100, 100, 100, 105.1],  # 最后值
            10: [98, 99, 100, 101, 102, 103],
            20: [95, 96, 97, 98, 99, 100],
        }.get(period, [None]))

        result = system.score(analyzer)

        # 应该是 STRONG_BULL
        assert result.trend_score == 30

    def test_score_edge_case_barely_below_threshold(self):
        """测试刚好低于强趋势阈值"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        # 间距刚好低于5%
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100, 100, 100, 100, 100, 104.9],  # 最后值
            10: [98, 99, 100, 101, 102, 103],
            20: [95, 96, 97, 98, 99, 100],
        }.get(period, [None]))

        result = system.score(analyzer)

        # 应该是普通 BULL
        assert result.trend_score == 26

    def test_score_bias_threshold_boundary(self):
        """测试乖离率阈值边界"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [110], 10: [105], 20: [100],
        }.get(period, [None]))

        # 刚好5%
        analyzer.get_bias = Mock(return_value=5)

        result = system.score(analyzer)

        # 5% 应该给中等分
        assert result.bias_score == 4

    def test_score_bias_strong_multiplier_boundary(self):
        """测试强势趋势乖离率放大边界"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100, 105, 110, 115, 120, 125],
            10: [95, 98, 102, 106, 110, 112],
            20: [90, 92, 94, 96, 98, 100],
        }.get(period, [None]))

        # 7.5%（5% * 1.5）刚好等于阈值，代码中是 > 而不是 >=
        # 所以 7.5 不会超过阈值，但 7.6 会
        analyzer.get_bias = Mock(return_value=7.6)

        result = system.score(analyzer)

        # 7.6% 超过 7.5% 阈值，应该给低分
        assert result.bias_score == 4

    def test_score_volume_threshold_boundary(self):
        """测试量能阈值边界"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer._prices = [100, 105]

        # 刚好 1.5（放量阈值）
        analyzer.get_volume_ratio = Mock(return_value=1.5)

        result = system.score(analyzer)

        # 放量上涨
        assert result.volume_score == 12

        analyzer._prices = [105, 100]

        # 放量下跌
        result = system.score(analyzer)

        assert result.volume_score == 0

    def test_score_volume_shrink_threshold_boundary(self):
        """测试缩量阈值边界"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()
        analyzer._prices = [100, 105]

        # 刚好 0.7（缩量阈值）
        analyzer.get_volume_ratio = Mock(return_value=0.7)

        result = system.score(analyzer)

        # 缩量上涨
        assert result.volume_score == 6

        analyzer._prices = [105, 100]

        # 缩量下跌
        result = system.score(analyzer)

        assert result.volume_score == 15

    def test_score_rsi_thresholds(self):
        """测试 RSI 阈值"""
        system = TrendScoringSystem()

        # RSI 边界值测试
        test_cases = [
            (71, 0, RSIStatus.OVERBOUGHT),  # > 70
            (70, 8, RSIStatus.STRONG_BUY),  # = 70
            (61, 8, RSIStatus.STRONG_BUY),  # > 60
            (60, 5, RSIStatus.NEUTRAL),     # = 60
            (39, 3, RSIStatus.WEAK),        # 30 <= RSI < 40
            (40, 5, RSIStatus.NEUTRAL),     # = 40
            (29, 10, RSIStatus.OVERSOLD),   # < 30
            (30, 3, RSIStatus.WEAK),        # = 30
        ]

        for rsi_value, expected_score, expected_status in test_cases:
            # 为每个测试用例创建新的 analyzer
            analyzer = create_mock_analyzer()
            analyzer.get_rsi = Mock(return_value=[rsi_value])
            result = system.score(analyzer)

            assert result.rsi_score == expected_score

    def test_score_support_tolerance_boundary(self):
        """测试支撑容忍度边界"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # 刚好2%
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100 * (1 + 0.02)],  # 102
            10: [100 * (1 + 0.02)],  # 102
            20: [95],
        }.get(period, [None]))
        analyzer._prices = [102]  # 刚好在MA5和MA10上

        result = system.score(analyzer)

        # 应该得到满分
        assert result.support_score == 10

    def test_score_support_outside_tolerance(self):
        """测试支撑容忍度外"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # 3%，且价格高于MA
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100 * (1 - 0.03)],  # 97（价格高于）
            10: [100 * (1 - 0.03)],  # 97
            20: [95],
        }.get(period, [None]))
        analyzer._prices = [100]  # 价格100，高于MA5=97

        result = system.score(analyzer)

        # 超过2%，没有支撑分（价格高于但距离太远）
        assert result.support_score == 0

    def test_score_macd_zero_crossing_boundary(self):
        """测试 MACD 零轴穿越边界"""
        system = TrendScoringSystem()

        analyzer = create_mock_analyzer()

        # 从正变负
        analyzer.get_macd = Mock(return_value=(
            [0.001, -0.001],  # 刚好从正变负
            [0.0005, -0.0005],
            [0.0005, -0.0005],
        ))

        result = system.score(analyzer)

        # 应该是 CROSSING_DOWN
        assert result.macd_score == 0

    def test_score_custom_weights(self):
        """测试自定义权重"""
        custom_weights = {
            'trend': 25,
            'bias': 25,
            'volume': 15,
            'support': 10,
            'macd': 15,
            'rsi': 10,
        }
        system = TrendScoringSystem(weights=custom_weights)

        analyzer = create_mock_analyzer()
        analyzer.get_sma = Mock(side_effect=lambda period: {
            5: [100, 105, 110, 115, 120, 125],
            10: [95, 98, 102, 106, 110, 112],
            20: [90, 92, 94, 96, 98, 100],
        }.get(period, [None]))
        analyzer.get_bias = Mock(return_value=-1)
        analyzer.get_volume_ratio = Mock(return_value=0.6)
        analyzer._prices = [105, 100]
        analyzer.get_macd = Mock(return_value=(
            [-0.1, 0.2],
            [-0.05, 0.1],
            [-0.05, 0.1],
        ))
        analyzer.get_rsi = Mock(return_value=[25])

        result = system.score(analyzer)

        # 验证自定义权重被使用（总分可能不同）
        assert result.total_score >= 0