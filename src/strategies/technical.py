# -*- coding: utf-8 -*-
"""
技术指标策略

基于技术指标的多种策略实现。
"""

import logging
from typing import Dict, Any, Optional, List

from .base import BaseStrategy, StrategyConfig, StrategySignal, SignalType
from src.indicators import QuoteDataAnalyzer


logger = logging.getLogger(__name__)


class TechnicalStrategy(BaseStrategy):
    """
    技术指标策略

    支持多种技术指标组合的策略。
    """

    def __init__(self, config: StrategyConfig):
        super().__init__(config)

        # 默认参数
        self.rsi_period = config.get("rsi_period", 14)
        self.rsi_oversold = config.get("rsi_oversold", 30)
        self.rsi_overbought = config.get("rsi_overbought", 70)

        self.macd_fast = config.get("macd_fast", 12)
        self.macd_slow = config.get("macd_slow", 26)
        self.macd_signal = config.get("macd_signal", 9)

        self.use_volume = config.get("use_volume", True)
        self.min_volume = config.get("min_volume", 1000000)

        # 止损止盈阈值（可配置）
        self.stop_loss_threshold = config.get("stop_loss_threshold", -0.05)
        self.take_profit_threshold = config.get("take_profit_threshold", 0.15)

    def generate_signal(
        self,
        analyzer: QuoteDataAnalyzer,
        account_info: Dict[str, Any],
    ) -> Optional[StrategySignal]:
        """生成交易信号"""
        if len(analyzer.quotes) < 50:
            return None

        # 获取最新行情
        latest_quote = analyzer.quotes[-1]

        # 检查成交量
        if self.use_volume and latest_quote.volume < self.min_volume:
            return None

        # 获取技术指标
        signals = analyzer.get_latest_signals()

        # 获取持仓
        positions = account_info.get("positions", [])
        has_position = any(p.symbol == latest_quote.symbol for p in positions)

        # 生成信号
        if not has_position:
            return self._generate_buy_signal(latest_quote, signals, account_info)
        else:
            return self._generate_sell_signal(latest_quote, signals, positions, account_info)

    def _generate_buy_signal(
        self,
        quote,
        signals: Dict[str, str],
        account_info: Dict[str, Any],
    ) -> Optional[StrategySignal]:
        """生成买入信号"""
        reasons = []
        confidence = 0.0

        # RSI 超卖
        if signals.get("rsi") == "oversold":
            reasons.append("RSI超卖")
            confidence += 0.3

        # MACD 金叉
        if signals.get("macd") == "bullish_cross":
            reasons.append("MACD金叉")
            confidence += 0.4

        # 布林带下轨
        if signals.get("bollinger") == "below_lower":
            reasons.append("跌破布林带下轨")
            confidence += 0.3

        # 上升趋势
        if signals.get("trend") == "uptrend":
            reasons.append("上升趋势")
            confidence += 0.2

        # 需要至少满足2个条件
        if len(reasons) >= 2 and confidence >= 0.6:
            quantity = self.get_position_size(
                quote.price,
                account_info,
                self.config.get("max_position_ratio", 0.30),
            )

            return StrategySignal(
                signal_type=SignalType.BUY,
                symbol=quote.symbol,
                price=quote.price,
                quantity=quantity,
                confidence=min(confidence, 1.0),
                reasoning=", ".join(reasons),
                metadata={
                    "indicators": signals,
                    "rsi": signals.get("rsi"),
                    "macd": signals.get("macd"),
                },
            )

        return None

    def _generate_sell_signal(
        self,
        quote,
        signals: Dict[str, str],
        positions: List,
        account_info: Dict[str, Any],
    ) -> Optional[StrategySignal]:
        """生成卖出信号"""
        position = next((p for p in positions if p.symbol == quote.symbol), None)
        if position is None:
            return None

        reasons = []
        confidence = 0.0

        # RSI 超买
        if signals.get("rsi") == "overbought":
            reasons.append("RSI超买")
            confidence += 0.4

        # MACD 死叉
        if signals.get("macd") == "bearish_cross":
            reasons.append("MACD死叉")
            confidence += 0.4

        # 布林带上轨
        if signals.get("bollinger") == "above_upper":
            reasons.append("突破布林带上轨")
            confidence += 0.2

        # 止损：亏损超过阈值
        pnl_ratio = getattr(position, "pnl_ratio", 0)
        if pnl_ratio < self.stop_loss_threshold:
            reasons.append(f"止损(亏损{pnl_ratio*100:.1f}%)")
            confidence = 1.0

        # 止盈：盈利超过阈值
        if pnl_ratio > self.take_profit_threshold:
            reasons.append(f"止盈(盈利{pnl_ratio*100:.1f}%)")
            confidence = 0.8

        # 需要至少满足1个条件（止损/止盈除外）
        if len(reasons) >= 1 and confidence >= 0.4:
            return StrategySignal(
                signal_type=SignalType.SELL,
                symbol=quote.symbol,
                price=quote.price,
                quantity=position.shares,
                confidence=min(confidence, 1.0),
                reasoning=", ".join(reasons),
                metadata={
                    "indicators": signals,
                    "pnl_ratio": pnl_ratio,
                },
            )

        return None


class AdaptiveTechnicalStrategy(TechnicalStrategy):
    """
    自适应技术指标策略

    根据市场状态动态调整参数。
    """

    def __init__(self, config: StrategyConfig):
        super().__init__(config)

        # 波动率阈值
        self.volatility_threshold = config.get("volatility_threshold", 0.02)

        # 自适应参数
        self.low_vol_rsi_period = config.get("low_vol_rsi_period", 14)
        self.high_vol_rsi_period = config.get("high_vol_rsi_period", 7)

    def _calculate_volatility(self, analyzer: QuoteDataAnalyzer, period: int = 20) -> float:
        """计算波动率"""
        if len(analyzer._prices) < period:
            return 0.0

        prices = analyzer._prices[-period:]
        import numpy as np
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        return np.std(returns)

    def generate_signal(
        self,
        analyzer: QuoteDataAnalyzer,
        account_info: Dict[str, Any],
    ) -> Optional[StrategySignal]:
        """生成交易信号（自适应）"""
        # 计算波动率
        volatility = self._calculate_volatility(analyzer)

        # 根据波动率调整参数
        if volatility > self.volatility_threshold:
            # 高波动：使用更短的周期
            self.rsi_period = self.high_vol_rsi_period
        else:
            # 低波动：使用更长的周期
            self.rsi_period = self.low_vol_rsi_period

        return super().generate_signal(analyzer, account_info)
