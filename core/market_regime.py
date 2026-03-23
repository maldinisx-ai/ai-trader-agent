# -*- coding: utf-8 -*-
"""
市场状态感知

根据大盘环境调整防御策略。

市场状态定义:
- 牛市: 均线多头排列，仓位上限30%
- 熊市: 均线空头排列，仓位上限10%
- 震荡: 均线交织，仓位上限20%
"""

from dataclasses import dataclass
from typing import Optional

from core.schemas import MarketRegime, MarketState


@dataclass
class MarketData:
    """市场数据"""
    index_code: str  # 指数代码
    ma5: float       # 5日均线
    ma10: float      # 10日均线
    ma20: float      # 20日均线
    ma60: float      # 60日均线
    up_down_ratio: float  # 涨跌家数比
    volume_ratio: float   # 量能比例


class MarketRegimeDetector:
    """
    市场状态检测器

    判断依据:
    1. 大盘趋势: MA20/MA60 多头排列
    2. 波动率: 相对高低点
    3. 成交量: 量能配合
    4. 涨跌家数比: 市场情绪
    """

    # 涨跌家数比阈值
    STRONG_BULL_THRESHOLD = 1.5  # 强牛市
    STRONG_BEAR_THRESHOLD = 0.67  # 强熊市

    def __init__(self):
        """初始化检测器"""
        pass

    def detect(self, data: MarketData) -> MarketState:
        """
        检测当前市场状态

        Args:
            data: 市场数据

        Returns:
            MarketState: 市场状态
        """
        # 计算技术指标
        ma_trend = self._calculate_ma_trend(data)
        breadth = self._calculate_market_breadth(data)
        volatility = self._calculate_volatility(data)

        # 综合判断
        regime, confidence = self._determine_regime(ma_trend, breadth, volatility)

        # 设置仓位上限
        max_position_ratio = self._get_max_position_ratio(regime)

        # 保存指标
        indicators = {
            "ma_trend": ma_trend["score"],
            "breadth": breadth["score"],
            "volatility": volatility["value"],
        }

        return MarketState(
            regime=regime,
            confidence=confidence,
            max_position_ratio=max_position_ratio,
            indicators=indicators,
        )

    def _calculate_ma_trend(self, data: MarketData) -> dict:
        """
        计算均线趋势

        Returns:
            {
                "bullish": bool,  # 是否多头
                "score": float,  # 趋势分数 (-1 到 1)
            }
        """
        # 多头排列: MA5 > MA10 > MA20 > MA60
        bullish = (
            data.ma5 > data.ma10 > data.ma20 > data.ma60
        )

        # 空头排列: MA5 < MA10 < MA20 < MA60
        bearish = (
            data.ma5 < data.ma10 < data.ma20 < data.ma60
        )

        if bullish:
            # 计算多头强度
            spread_5_10 = (data.ma5 - data.ma10) / data.ma10
            spread_10_20 = (data.ma10 - data.ma20) / data.ma20
            spread_20_60 = (data.ma20 - data.ma60) / data.ma60
            score = min(1.0, (spread_5_10 + spread_10_20 + spread_20_60) * 10)
        elif bearish:
            # 计算空头强度（负值）
            spread_5_10 = (data.ma10 - data.ma5) / data.ma10
            spread_10_20 = (data.ma20 - data.ma10) / data.ma20
            spread_20_60 = (data.ma60 - data.ma20) / data.ma60
            score = max(-1.0, -(spread_5_10 + spread_10_20 + spread_20_60) * 10)
        else:
            # 震荡，根据均线的分散程度
            spread_5_60 = abs(data.ma5 - data.ma60) / data.ma60
            score = 0.0 if spread_5_60 < 0.02 else (0.5 if spread_5_60 < 0.05 else -0.5)

        return {
            "bullish": bullish,
            "bearish": bearish,
            "score": score,
        }

    def _calculate_market_breadth(self, data: MarketData) -> dict:
        """
        计算市场广度

        Returns:
            {
                "strong": bool,  # 是否强势
                "weak": bool,    # 是否弱势
                "score": float,  # 广度分数 (0 到 1)
            }
        """
        up_down_ratio = data.up_down_ratio

        if up_down_ratio >= self.STRONG_BULL_THRESHOLD:
            strong = True
            weak = False
            score = min(1.0, up_down_ratio / 3.0)
        elif up_down_ratio <= self.STRONG_BEAR_THRESHOLD:
            strong = False
            weak = True
            score = up_down_ratio / 3.0
        else:
            strong = False
            weak = False
            # 接近1为中性
            score = 1.0 - abs(up_down_ratio - 1.0) / 2.0

        return {
            "strong": strong,
            "weak": weak,
            "score": score,
        }

    def _calculate_volatility(self, data: MarketData) -> dict:
        """
        计算波动率（简化版）

        Returns:
            {
                "value": float,  # 波动率值
            }
        """
        # 简化：使用量能比例作为波动率代理
        # 实际实现应该使用ATR或标准差
        return {
            "value": data.volume_ratio,
        }

    def _determine_regime(self, ma_trend: dict, breadth: dict,
                        volatility: dict) -> tuple[MarketRegime, float]:
        """
        综合判断市场状态

        Args:
            ma_trend: 均线趋势
            breadth: 市场广度
            volatility: 波动率

        Returns:
            (MarketRegime, confidence)
        """
        # 牛市条件
        if ma_trend["bullish"] and breadth["strong"]:
            return MarketRegime.BULL, min(0.95, 0.7 + ma_trend["score"] * 0.15 + breadth["score"] * 0.15)

        # 熊市条件
        if ma_trend["bearish"] or breadth["weak"]:
            return MarketRegime.BEAR, min(0.95, 0.7 + abs(ma_trend["score"]) * 0.15 + (1 - breadth["score"]) * 0.15)

        # 震荡市
        # 置信度基于趋势的明确程度
        trend_clarity = 1.0 - abs(ma_trend["score"])
        return MarketRegime.SIDEWAYS, max(0.5, trend_clarity)

    def _get_max_position_ratio(self, regime: MarketRegime) -> float:
        """
        获取最大仓位比例

        Args:
            regime: 市场状态

        Returns:
            最大仓位比例
        """
        if regime == MarketRegime.BULL:
            return 0.30
        elif regime == MarketRegime.BEAR:
            return 0.10
        else:  # SIDEWAYS
            return 0.20
