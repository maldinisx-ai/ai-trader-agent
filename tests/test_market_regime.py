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


class TestMarketRegimeDetector:
    """测试市场状态检测器"""

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
