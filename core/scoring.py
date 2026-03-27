# -*- coding: utf-8 -*-
"""
趋势评分系统

基于 daily_stock_analysis 的 100 分制评分体系：
- 趋势: 30分
- 乖离率: 20分
- 量能: 15分
- 支撑: 10分
- MACD: 15分
- RSI: 10分
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from core.schemas import (
    TrendStatus,
    VolumeStatus,
    MACDStatus,
    RSIStatus,
    BuySignal,
)
from src.indicators import QuoteDataAnalyzer


logger = logging.getLogger(__name__)


@dataclass
class ScoreResult:
    """评分结果"""
    total_score: int              # 总分 0-100
    buy_signal: BuySignal         # 买入信号
    trend_score: int              # 趋势得分
    bias_score: int               # 乖离率得分
    volume_score: int             # 量能得分
    support_score: int            # 支撑得分
    macd_score: int               # MACD得分
    rsi_score: int                # RSI得分
    reasons: List[str] = field(default_factory=list)            # 买入理由
    risk_factors: List[str] = field(default_factory=list)       # 风险因素

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'total_score': self.total_score,
            'buy_signal': self.buy_signal.value,
            'trend_score': self.trend_score,
            'bias_score': self.bias_score,
            'volume_score': self.volume_score,
            'support_score': self.support_score,
            'macd_score': self.macd_score,
            'rsi_score': self.rsi_score,
            'reasons': self.reasons,
            'risk_factors': self.risk_factors,
        }


class TrendScoringSystem:
    """
    趋势评分系统

    基于 daily_stock_analysis 的严进策略：
    1. 多头排列（MA5 > MA10 > MA20）
    2. 乖离率控制（不追高，<5%）
    3. 缩量回调偏好
    4. 综合评分决策
    """

    # 默认权重
    DEFAULT_WEIGHTS = {
        'trend': 30,
        'bias': 20,
        'volume': 15,
        'support': 10,
        'macd': 15,
        'rsi': 10,
    }

    # 配置参数
    BIAS_THRESHOLD = 5.0              # 乖离率阈值（%）
    BIAS_STRONG_MULTIPLIER = 1.5      # 强势趋势乖离率放大倍数
    VOLUME_SHRINK_RATIO = 0.7         # 缩量判断阈值
    VOLUME_HEAVY_RATIO = 1.5          # 放量判断阈值
    MA_SUPPORT_TOLERANCE = 0.02       # MA支撑容忍度（2%）
    STRONG_TREND_SPREAD_THRESHOLD = 5.0  # 强势趋势间距阈值（%）

    # 评分阈值
    SIGNAL_THRESHOLDS = {
        'strong_buy': 75,
        'buy': 60,
        'hold': 45,
        'wait': 30,
    }

    def __init__(self, weights: Optional[Dict[str, int]] = None):
        """
        初始化评分系统

        Args:
            weights: 自定义权重（可选）
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()

    def score(self, analyzer: QuoteDataAnalyzer) -> ScoreResult:
        """
        计算综合评分

        Args:
            analyzer: 行情数据分析器

        Returns:
            评分结果
        """
        if len(analyzer.quotes) < 20:
            logger.warning("数据不足，无法完成评分")
            return ScoreResult(
                total_score=0,
                buy_signal=BuySignal.WAIT,
                trend_score=0,
                bias_score=0,
                volume_score=0,
                support_score=0,
                macd_score=0,
                rsi_score=0,
                risk_factors=["数据不足，无法完成分析"],
            )

        score = 0
        reasons = []
        risks = []

        # 1. 趋势评分（30分）
        trend_score, trend_status = self._score_trend(analyzer)
        score += trend_score
        if trend_status in [TrendStatus.STRONG_BULL, TrendStatus.BULL]:
            reasons.append(f"[+] {trend_status.value}, trend following")
        elif trend_status in [TrendStatus.BEAR, TrendStatus.STRONG_BEAR]:
            risks.append(f"[!] {trend_status.value}, not suitable for long")

        # 2. 乖离率评分（20分）
        bias_score = self._score_bias(analyzer, trend_status)
        score += bias_score

        # 3. 量能评分（15分）
        volume_score, volume_status = self._score_volume(analyzer)
        score += volume_score
        if volume_status == VolumeStatus.SHRINK_VOLUME_DOWN:
            reasons.append("[+] Low volume pullback, main force wash")
        elif volume_status == VolumeStatus.HEAVY_VOLUME_DOWN:
            risks.append("[!] Heavy volume down, watch risk")

        # 4. 支撑评分（10分）
        support_score = self._score_support(analyzer)
        score += support_score

        # 5. MACD 评分（15分）
        macd_score, macd_status = self._score_macd(analyzer)
        score += macd_score
        if macd_status in [MACDStatus.GOLDEN_CROSS_ZERO, MACDStatus.GOLDEN_CROSS]:
            reasons.append(f"[+] {macd_status.value}")
        elif macd_status in [MACDStatus.DEATH_CROSS, MACDStatus.CROSSING_DOWN]:
            risks.append(f"[!] {macd_status.value}")

        # 6. RSI 评分（10分）
        rsi_score, rsi_status = self._score_rsi(analyzer)
        score += rsi_score
        if rsi_status in [RSIStatus.OVERSOLD, RSIStatus.STRONG_BUY]:
            reasons.append(f"[+] {rsi_status.value}")
        elif rsi_status == RSIStatus.OVERBOUGHT:
            risks.append(f"[!] {rsi_status.value}")

        # 生成买入信号
        buy_signal = self._generate_signal(score, trend_status)

        return ScoreResult(
            total_score=score,
            buy_signal=buy_signal,
            trend_score=trend_score,
            bias_score=bias_score,
            volume_score=volume_score,
            support_score=support_score,
            macd_score=macd_score,
            rsi_score=rsi_score,
            reasons=reasons,
            risk_factors=risks,
        )

    def _score_trend(self, analyzer: QuoteDataAnalyzer) -> tuple[int, TrendStatus]:
        """趋势评分（30分）"""
        ma5 = analyzer.get_sma(5)
        ma10 = analyzer.get_sma(10)
        ma20 = analyzer.get_sma(20)

        if not all([ma5[-1], ma10[-1], ma20[-1]]):
            return 12, TrendStatus.CONSOLIDATION

        # 判断均线排列
        if ma5[-1] > ma10[-1] > ma20[-1]:
            # 检查间距是否扩大（强势）
            if len(ma5) >= 5:
                prev_spread = (ma5[-5] - ma20[-5]) / ma20[-5] * 100 if ma20[-5] else 0
                curr_spread = (ma5[-1] - ma20[-1]) / ma20[-1] * 100 if ma20[-1] else 0

                if curr_spread > prev_spread and curr_spread > self.STRONG_TREND_SPREAD_THRESHOLD:
                    return 30, TrendStatus.STRONG_BULL

            return 26, TrendStatus.BULL

        elif ma5[-1] > ma10[-1] and ma10[-1] <= ma20[-1]:
            return 18, TrendStatus.WEAK_BULL

        elif ma5[-1] < ma10[-1] < ma20[-1]:
            if len(ma5) >= 5:
                prev_spread = (ma20[-5] - ma5[-5]) / ma5[-5] * 100 if ma5[-5] else 0
                curr_spread = (ma20[-1] - ma5[-1]) / ma5[-1] * 100 if ma5[-1] else 0

                if curr_spread > prev_spread and curr_spread > self.STRONG_TREND_SPREAD_THRESHOLD:
                    return 10, TrendStatus.STRONG_BEAR

            return 4, TrendStatus.BEAR

        elif ma5[-1] < ma10[-1] and ma10[-1] >= ma20[-1]:
            return 8, TrendStatus.WEAK_BEAR

        else:
            return 12, TrendStatus.CONSOLIDATION

    def _score_bias(self, analyzer: QuoteDataAnalyzer, trend_status: TrendStatus) -> int:
        """乖离率评分（20分）"""
        bias = analyzer.get_bias(5)

        # 强势趋势补偿：放宽阈值
        effective_threshold = self.BIAS_THRESHOLD
        if trend_status == TrendStatus.STRONG_BULL:
            effective_threshold = self.BIAS_THRESHOLD * self.BIAS_STRONG_MULTIPLIER

        if bias < 0:
            # 价格低于 MA5（回踩）
            if bias > -3:
                return 20
            elif bias > -5:
                return 16
            else:
                return 8
        elif bias < 2:
            return 18
        elif bias < effective_threshold:
            return 14
        elif bias > effective_threshold:
            return 4
        else:
            return 4

    def _score_volume(self, analyzer: QuoteDataAnalyzer) -> tuple[int, VolumeStatus]:
        """量能评分（15分）"""
        volume_ratio = analyzer.get_volume_ratio(5)
        current_price = analyzer._prices[-1]
        prev_price = analyzer._prices[-2] if len(analyzer._prices) >= 2 else current_price
        price_change = (current_price - prev_price) / prev_price * 100 if prev_price > 0 else 0

        # 判断量能状态
        if volume_ratio >= self.VOLUME_HEAVY_RATIO:
            if price_change > 0:
                return 12, VolumeStatus.HEAVY_VOLUME_UP
            else:
                return 0, VolumeStatus.HEAVY_VOLUME_DOWN
        elif volume_ratio <= self.VOLUME_SHRINK_RATIO:
            if price_change > 0:
                return 6, VolumeStatus.SHRINK_VOLUME_UP
            else:
                return 15, VolumeStatus.SHRINK_VOLUME_DOWN
        else:
            return 10, VolumeStatus.NORMAL

    def _score_support(self, analyzer: QuoteDataAnalyzer) -> int:
        """支撑评分（10分）"""
        score = 0
        current_price = analyzer._prices[-1]

        # MA5 支撑
        ma5 = analyzer.get_sma(5)
        if ma5[-1]:
            ma5_distance = abs(current_price - ma5[-1]) / ma5[-1]
            if ma5_distance <= self.MA_SUPPORT_TOLERANCE and current_price >= ma5[-1]:
                score += 5

        # MA10 支撑
        ma10 = analyzer.get_sma(10)
        if ma10[-1]:
            ma10_distance = abs(current_price - ma10[-1]) / ma10[-1]
            if ma10_distance <= self.MA_SUPPORT_TOLERANCE and current_price >= ma10[-1]:
                score += 5

        return score

    def _score_macd(self, analyzer: QuoteDataAnalyzer) -> tuple[int, MACDStatus]:
        """MACD 评分（15分）"""
        macd_line, signal_line, histogram = analyzer.get_macd()

        if not histogram or len(histogram) < 2:
            return 5, MACDStatus.BULLISH

        # 获取有效值
        macd_last = macd_line[-1]
        signal_last = signal_line[-1]
        macd_prev = macd_line[-2]
        signal_prev = signal_line[-2]

        # 如果值为 None，返回中性状态
        if macd_last is None or signal_last is None or macd_prev is None or signal_prev is None:
            return 5, MACDStatus.BULLISH

        # 判断金叉死叉
        prev_dif_dea = macd_prev - signal_prev
        curr_dif_dea = macd_last - signal_last

        is_golden_cross = prev_dif_dea <= 0 and curr_dif_dea > 0
        is_death_cross = prev_dif_dea >= 0 and curr_dif_dea < 0

        # 零轴穿越
        is_crossing_up = macd_prev <= 0 and macd_last > 0
        is_crossing_down = macd_prev >= 0 and macd_last < 0

        # 判断 MACD 状态
        if is_golden_cross and macd_last > 0:
            return 15, MACDStatus.GOLDEN_CROSS_ZERO
        elif is_crossing_up:
            return 10, MACDStatus.CROSSING_UP
        elif is_golden_cross:
            return 12, MACDStatus.GOLDEN_CROSS
        elif is_death_cross:
            return 0, MACDStatus.DEATH_CROSS
        elif is_crossing_down:
            return 0, MACDStatus.CROSSING_DOWN
        elif macd_last > 0 and signal_last > 0:
            return 8, MACDStatus.BULLISH
        elif macd_last < 0 and signal_last < 0:
            return 2, MACDStatus.BEARISH
        else:
            return 5, MACDStatus.BULLISH

    def _score_rsi(self, analyzer: QuoteDataAnalyzer) -> tuple[int, RSIStatus]:
        """RSI 评分（10分）"""
        rsi = analyzer.get_rsi(12)

        if not rsi or rsi[-1] is None:
            return 5, RSIStatus.NEUTRAL

        rsi_value = rsi[-1]

        if rsi_value > 70:
            return 0, RSIStatus.OVERBOUGHT
        elif rsi_value > 60:
            return 8, RSIStatus.STRONG_BUY
        elif rsi_value >= 40:
            return 5, RSIStatus.NEUTRAL
        elif rsi_value >= 30:
            return 3, RSIStatus.WEAK
        else:
            return 10, RSIStatus.OVERSOLD

    def _generate_signal(self, score: int, trend_status: TrendStatus) -> BuySignal:
        """生成买入信号"""
        if score >= 75 and trend_status in [TrendStatus.STRONG_BULL, TrendStatus.BULL]:
            return BuySignal.STRONG_BUY
        elif score >= 60 and trend_status in [TrendStatus.STRONG_BULL, TrendStatus.BULL, TrendStatus.WEAK_BULL]:
            return BuySignal.BUY
        elif score >= 45:
            return BuySignal.HOLD
        elif score >= 30:
            return BuySignal.WAIT
        elif trend_status in [TrendStatus.BEAR, TrendStatus.STRONG_BEAR]:
            return BuySignal.STRONG_SELL
        else:
            return BuySignal.SELL
