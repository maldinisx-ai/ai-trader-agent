# -*- coding: utf-8 -*-
"""
测试市场状态感知

TDD 流程: RED → GREEN → REFACTOR
"""

import pytest
import pandas as pd
from datetime import datetime

from core.schemas import MarketRegime, MarketState, QuoteData
from core.market_regime import MarketRegimeDetector, MarketData


import core.market_regime


class TestMarketRegimeDetector:
    """测试市场状态检测器"""

    def test_class_constants(self):
        """测试类常量"""
        assert MarketRegimeDetector.STRONG_BULL_THRESHOLD == 1.5
        assert MarketRegimeDetector.STRONG_BEAR_THRESHOLD == 0.67

    def test_initialization(self):
        """测试初始化"""
        detector = MarketRegimeDetector()
        assert detector is not None

    def test_detect_bull_market(self):
        """测试检测牛市"""
        detector = MarketRegimeDetector()

        # 牛市特征：均线多头排列
        data = MarketData(
            index_code="000001.SH",
            ma5=1750.0,
            ma10=1700.0,
            ma20=1650.0,
            ma60=1600.0,
            up_down_ratio=2.0,  # 涨跌家数比 > 1.5
            volume_ratio=1.5,  # 量能配合
        )

        state = detector.detect(data)
        assert state.regime == MarketRegime.BULL
        assert state.max_position_ratio == 0.30
        assert state.confidence > 0.7

    def test_detect_bear_market(self):
        """测试检测熊市"""
        detector = MarketRegimeDetector()

        # 熊市特征：均线空头排列
        data = MarketData(
            index_code="000001.SH",
            ma5=1600.0,
            ma10=1650.0,
            ma20=1700.0,
            ma60=1750.0,
            up_down_ratio=0.4,  # 涨跌家数比 < 0.67
            volume_ratio=0.8,
        )

        state = detector.detect(data)
        assert state.regime == MarketRegime.BEAR
        assert state.max_position_ratio == 0.10

    def test_detect_sideways_market(self):
        """测试检测震荡市"""
        detector = MarketRegimeDetector()

        # 震荡市特征：均线交织
        data = MarketData(
            index_code="000001.SH",
            ma5=1700.0,
            ma10=1705.0,
            ma20=1695.0,
            ma60=1700.0,
            up_down_ratio=1.0,  # 涨跌家数比接近 1
            volume_ratio=1.0,
        )

        state = detector.detect(data)
        assert state.regime == MarketRegime.SIDEWAYS
        assert state.max_position_ratio == 0.20

    def test_calculate_confidence(self):
        """测试置信度计算"""
        detector = MarketRegimeDetector()

        # 强牛市信号
        data = MarketData(
            index_code="000001.SH",
            ma5=1800.0,
            ma10=1700.0,
            ma20=1600.0,
            ma60=1500.0,
            up_down_ratio=3.0,
            volume_ratio=2.0,
        )

        state = detector.detect(data)
        assert state.confidence > 0.8

    def test_indicators_saved(self):
        """测试指标被保存"""
        detector = MarketRegimeDetector()

        data = MarketData(
            index_code="000001.SH",
            ma5=1750.0,
            ma10=1700.0,
            ma20=1650.0,
            ma60=1600.0,
            up_down_ratio=2.0,
            volume_ratio=1.5,
        )

        state = detector.detect(data)
        assert "ma_trend" in state.indicators
        assert "volatility" in state.indicators
        assert "breadth" in state.indicators


class TestCalculateMATrend:
    """测试均线趋势计算"""

    def test_bullish_arrangement(self):
        """测试多头排列"""
        detector = MarketRegimeDetector()
        data = MarketData(
            index_code="000001.SH",
            ma5=1750.0,
            ma10=1700.0,
            ma20=1650.0,
            ma60=1600.0,
            up_down_ratio=1.0,
            volume_ratio=1.0,
        )

        result = detector._calculate_ma_trend(data)
        assert result["bullish"] is True
        assert result["bearish"] is False
        assert result["score"] > 0

    def test_bearish_arrangement(self):
        """测试空头排列"""
        detector = MarketRegimeDetector()
        data = MarketData(
            index_code="000001.SH",
            ma5=1600.0,
            ma10=1650.0,
            ma20=1700.0,
            ma60=1750.0,
            up_down_ratio=1.0,
            volume_ratio=1.0,
        )

        result = detector._calculate_ma_trend(data)
        assert result["bullish"] is False
        assert result["bearish"] is True
        assert result["score"] < 0

    def test_sideways_small_spread(self):
        """测试震荡市 - 小价差 (< 2%)"""
        detector = MarketRegimeDetector()
        data = MarketData(
            index_code="000001.SH",
            ma5=1701.0,  # 仅相差 0.06%
            ma10=1702.0,
            ma20=1699.0,
            ma60=1700.0,
            up_down_ratio=1.0,
            volume_ratio=1.0,
        )

        result = detector._calculate_ma_trend(data)
        assert result["bullish"] is False
        assert result["bearish"] is False
        assert result["score"] == 0.0

    def test_sideways_medium_spread(self):
        """测试震荡市 - 中等价差 (2%-5%) - 均线非有序排列"""
        detector = MarketRegimeDetector()
        data = MarketData(
            index_code="000001.SH",
            ma5=1750.0,  # ma5 > ma10 > ma20 < ma60 (非有序排列)
            ma10=1730.0,
            ma20=1720.0,
            ma60=1780.0,  # ma60 > ma20，打破空头排列
            up_down_ratio=1.0,
            volume_ratio=1.0,
        )

        result = detector._calculate_ma_trend(data)
        assert result["bullish"] is False
        assert result["bearish"] is False
        # (1750 - 1780) / 1780 ≈ 0.017 < 0.02
        assert result["score"] == 0.0

    def test_sideways_large_spread(self):
        """测试震荡市 - 大价差 (>= 5%) - 均线非有序排列"""
        detector = MarketRegimeDetector()
        data = MarketData(
            index_code="000001.SH",
            ma5=1850.0,  # ma5 > ma10 > ma20 < ma60 (非有序排列)
            ma10=1750.0,
            ma20=1700.0,
            ma60=1800.0,  # ma60 > ma20，打破空头排列
            up_down_ratio=1.0,
            volume_ratio=1.0,
        )

        result = detector._calculate_ma_trend(data)
        assert result["bullish"] is False
        assert result["bearish"] is False
        # (1850 - 1800) / 1800 ≈ 0.028 < 0.05
        assert result["score"] == 0.5

    def test_bullish_score_capped_at_1(self):
        """测试多头分数上限为 1.0"""
        detector = MarketRegimeDetector()
        # 使用非常大的价差，确保分数被限制在 1.0
        data = MarketData(
            index_code="000001.SH",
            ma5=2000.0,
            ma10=1500.0,
            ma20=1000.0,
            ma60=500.0,
            up_down_ratio=1.0,
            volume_ratio=1.0,
        )

        result = detector._calculate_ma_trend(data)
        assert result["bullish"] is True
        assert result["score"] == 1.0

    def test_bearish_score_capped_at_neg1(self):
        """测试空头分数下限为 -1.0"""
        detector = MarketRegimeDetector()
        # 使用非常大的价差，确保分数被限制在 -1.0
        data = MarketData(
            index_code="000001.SH",
            ma5=500.0,
            ma10=1000.0,
            ma20=1500.0,
            ma60=2000.0,
            up_down_ratio=1.0,
            volume_ratio=1.0,
        )

        result = detector._calculate_ma_trend(data)
        assert result["bearish"] is True
        assert result["score"] == -1.0


class TestCalculateMarketBreadth:
    """测试市场广度计算"""

    def test_strong_bull_threshold_exact(self):
        """测试强牛市阈值边界 (1.5)"""
        detector = MarketRegimeDetector()
        data = MarketData(
            index_code="000001.SH",
            ma5=1700.0,
            ma10=1700.0,
            ma20=1700.0,
            ma60=1700.0,
            up_down_ratio=1.5,  # 正好等于阈值
            volume_ratio=1.0,
        )

        result = detector._calculate_market_breadth(data)
        assert result["strong"] is True
        assert result["weak"] is False
        assert result["score"] == 0.5  # 1.5 / 3.0

    def test_strong_bull_above_threshold(self):
        """测试强牛市阈值之上"""
        detector = MarketRegimeDetector()
        data = MarketData(
            index_code="000001.SH",
            ma5=1700.0,
            ma10=1700.0,
            ma20=1700.0,
            ma60=1700.0,
            up_down_ratio=3.0,
            volume_ratio=1.0,
        )

        result = detector._calculate_market_breadth(data)
        assert result["strong"] is True
        assert result["weak"] is False
        assert result["score"] == 1.0  # min(1.0, 3.0/3.0)

    def test_strong_bear_threshold_exact(self):
        """测试强熊市阈值边界 (0.67)"""
        detector = MarketRegimeDetector()
        data = MarketData(
            index_code="000001.SH",
            ma5=1700.0,
            ma10=1700.0,
            ma20=1700.0,
            ma60=1700.0,
            up_down_ratio=0.67,  # 正好等于阈值
            volume_ratio=1.0,
        )

        result = detector._calculate_market_breadth(data)
        assert result["strong"] is False
        assert result["weak"] is True
        assert result["score"] == 0.67 / 3.0

    def test_strong_bear_below_threshold(self):
        """测试强熊市阈值之下"""
        detector = MarketRegimeDetector()
        data = MarketData(
            index_code="000001.SH",
            ma5=1700.0,
            ma10=1700.0,
            ma20=1700.0,
            ma60=1700.0,
            up_down_ratio=0.3,
            volume_ratio=1.0,
        )

        result = detector._calculate_market_breadth(data)
        assert result["strong"] is False
        assert result["weak"] is True
        assert result["score"] == pytest.approx(0.1, rel=1e-9)  # 0.3 / 3.0

    def test_neutral_breadth(self):
        """测试中性广度 (ratio = 1.0)"""
        detector = MarketRegimeDetector()
        data = MarketData(
            index_code="000001.SH",
            ma5=1700.0,
            ma10=1700.0,
            ma20=1700.0,
            ma60=1700.0,
            up_down_ratio=1.0,
            volume_ratio=1.0,
        )

        result = detector._calculate_market_breadth(data)
        assert result["strong"] is False
        assert result["weak"] is False
        assert result["score"] == 1.0  # 1.0 - |1.0 - 1.0| / 2.0

    def test_neutral_breadth_slightly_bullish(self):
        """测试略偏多头的广度 (ratio = 1.3)"""
        detector = MarketRegimeDetector()
        data = MarketData(
            index_code="000001.SH",
            ma5=1700.0,
            ma10=1700.0,
            ma20=1700.0,
            ma60=1700.0,
            up_down_ratio=1.3,
            volume_ratio=1.0,
        )

        result = detector._calculate_market_breadth(data)
        assert result["strong"] is False
        assert result["weak"] is False
        # 1.0 - |1.3 - 1.0| / 2.0 = 1.0 - 0.15 = 0.85
        assert result["score"] == 0.85


class TestCalculateVolatility:
    """测试波动率计算"""

    def test_volatility_equals_volume_ratio(self):
        """测试波动率等于量能比例"""
        detector = MarketRegimeDetector()
        data = MarketData(
            index_code="000001.SH",
            ma5=1700.0,
            ma10=1700.0,
            ma20=1700.0,
            ma60=1700.0,
            up_down_ratio=1.0,
            volume_ratio=1.5,
        )

        result = detector._calculate_volatility(data)
        assert result["value"] == 1.5

    def test_volatility_low(self):
        """测试低波动率"""
        detector = MarketRegimeDetector()
        data = MarketData(
            index_code="000001.SH",
            ma5=1700.0,
            ma10=1700.0,
            ma20=1700.0,
            ma60=1700.0,
            up_down_ratio=1.0,
            volume_ratio=0.5,
        )

        result = detector._calculate_volatility(data)
        assert result["value"] == 0.5

    def test_volatility_high(self):
        """测试高波动率"""
        detector = MarketRegimeDetector()
        data = MarketData(
            index_code="000001.SH",
            ma5=1700.0,
            ma10=1700.0,
            ma20=1700.0,
            ma60=1700.0,
            up_down_ratio=1.0,
            volume_ratio=3.0,
        )

        result = detector._calculate_volatility(data)
        assert result["value"] == 3.0


class TestDetermineRegime:
    """测试市场状态判断"""

    def test_bull_market_high_confidence(self):
        """测试牛市高置信度"""
        detector = MarketRegimeDetector()
        ma_trend = {"bullish": True, "bearish": False, "score": 0.8}
        breadth = {"strong": True, "weak": False, "score": 0.9}
        volatility = {"value": 1.5}

        regime, confidence = detector._determine_regime(ma_trend, breadth, volatility)
        assert regime == MarketRegime.BULL
        # 0.7 + 0.8*0.15 + 0.9*0.15 = 0.7 + 0.12 + 0.135 = 0.955 -> capped at 0.95
        assert confidence == 0.95

    def test_bear_market_bearish_trend(self):
        """测试熊市 - 空头趋势"""
        detector = MarketRegimeDetector()
        ma_trend = {"bullish": False, "bearish": True, "score": -0.7}
        breadth = {"strong": False, "weak": False, "score": 0.6}
        volatility = {"value": 0.8}

        regime, confidence = detector._determine_regime(ma_trend, breadth, volatility)
        assert regime == MarketRegime.BEAR

    def test_bear_market_weak_breadth(self):
        """测试熊市 - 弱势广度"""
        detector = MarketRegimeDetector()
        ma_trend = {"bullish": False, "bearish": False, "score": 0.0}
        breadth = {"strong": False, "weak": True, "score": 0.2}
        volatility = {"value": 0.8}

        regime, confidence = detector._determine_regime(ma_trend, breadth, volatility)
        assert regime == MarketRegime.BEAR

    def test_sideways_market(self):
        """测试震荡市"""
        detector = MarketRegimeDetector()
        ma_trend = {"bullish": False, "bearish": False, "score": 0.2}
        breadth = {"strong": False, "weak": False, "score": 0.7}
        volatility = {"value": 1.0}

        regime, confidence = detector._determine_regime(ma_trend, breadth, volatility)
        assert regime == MarketRegime.SIDEWAYS
        # 1.0 - |0.2| = 0.8, max(0.5, 0.8) = 0.8
        assert confidence == 0.8

    def test_sideways_low_confidence_capped(self):
        """测试震荡市低置信度被限制在 0.5"""
        detector = MarketRegimeDetector()
        ma_trend = {"bullish": False, "bearish": False, "score": 0.9}
        breadth = {"strong": False, "weak": False, "score": 0.5}
        volatility = {"value": 1.0}

        regime, confidence = detector._determine_regime(ma_trend, breadth, volatility)
        assert regime == MarketRegime.SIDEWAYS
        # 1.0 - 0.9 = 0.1, max(0.5, 0.1) = 0.5
        assert confidence == 0.5


class TestGetMaxPositionRatio:
    """测试最大仓位比例"""

    def test_bull_market_max_position(self):
        """测试牛市最大仓位"""
        detector = MarketRegimeDetector()
        ratio = detector._get_max_position_ratio(MarketRegime.BULL)
        assert ratio == 0.30

    def test_bear_market_max_position(self):
        """测试熊市最大仓位"""
        detector = MarketRegimeDetector()
        ratio = detector._get_max_position_ratio(MarketRegime.BEAR)
        assert ratio == 0.10

    def test_sideways_market_max_position(self):
        """测试震荡市最大仓位"""
        detector = MarketRegimeDetector()
        ratio = detector._get_max_position_ratio(MarketRegime.SIDEWAYS)
        assert ratio == 0.20


class TestMarketData:
    """测试市场数据类"""

    def test_market_data_creation(self):
        """测试市场数据创建"""
        data = MarketData(
            index_code="000001.SH",
            ma5=1750.0,
            ma10=1700.0,
            ma20=1650.0,
            ma60=1600.0,
            up_down_ratio=2.0,
            volume_ratio=1.5,
        )

        assert data.index_code == "000001.SH"
        assert data.ma5 == 1750.0
        assert data.ma10 == 1700.0
        assert data.ma20 == 1650.0
        assert data.ma60 == 1600.0
        assert data.up_down_ratio == 2.0
        assert data.volume_ratio == 1.5
