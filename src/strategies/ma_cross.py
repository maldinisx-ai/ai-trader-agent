# -*- coding: utf-8 -*-
"""
均线交叉策略

经典的移动平均线交叉策略。
"""

import logging
from typing import Dict, Any, Optional

from .base import BaseStrategy, StrategyConfig, StrategySignal, SignalType
from src.indicators import QuoteDataAnalyzer


logger = logging.getLogger(__name__)


class MACrossStrategy(BaseStrategy):
    """
    均线交叉策略

    策略逻辑：
    - 金叉（短期均线上穿长期均线）→ 买入
    - 死叉（短期均线下穿长期均线）→ 卖出
    """

    def __init__(self, config: StrategyConfig):
        super().__init__(config)

        # 默认参数
        self.fast_period = config.get("fast_period", 5)   # 快线周期
        self.slow_period = config.get("slow_period", 20)  # 慢线周期
        self.signal_period = config.get("signal_period", 3)  # 信号确认周期

    def generate_signal(
        self,
        analyzer: QuoteDataAnalyzer,
        account_info: Dict[str, Any],
    ) -> Optional[StrategySignal]:
        """生成交易信号"""
        if len(analyzer.quotes) < self.slow_period + self.signal_period:
            return None

        # 计算均线
        fast_ma = analyzer.get_sma(self.fast_period)
        slow_ma = analyzer.get_sma(self.slow_period)

        # 检查是否有有效数据
        if fast_ma[-1] is None or slow_ma[-1] is None:
            return None

        # 获取最新行情
        latest_quote = analyzer.quotes[-1]

        # 检查持仓
        positions = account_info.get("positions", [])
        has_position = any(p.symbol == latest_quote.symbol for p in positions)

        # 检测交叉
        cross_type = self._detect_cross(fast_ma, slow_ma)

        if cross_type == "golden" and not has_position:
            # 金叉买入
            quantity = self.get_position_size(
                latest_quote.price,
                account_info,
                self.config.get("max_position_ratio", 0.30),
            )

            return StrategySignal(
                signal_type=SignalType.BUY,
                symbol=latest_quote.symbol,
                price=latest_quote.price,
                quantity=quantity,
                confidence=0.7,
                reasoning=f"MA{self.fast_period}金叉MA{self.slow_period}",
                metadata={
                    "fast_ma": fast_ma[-1],
                    "slow_ma": slow_ma[-1],
                    "cross_type": "golden",
                },
            )

        elif cross_type == "death" and has_position:
            # 死叉卖出
            position = next(p for p in positions if p.symbol == latest_quote.symbol)

            return StrategySignal(
                signal_type=SignalType.SELL,
                symbol=latest_quote.symbol,
                price=latest_quote.price,
                quantity=position.shares,
                confidence=0.7,
                reasoning=f"MA{self.fast_period}死叉MA{self.slow_period}",
                metadata={
                    "fast_ma": fast_ma[-1],
                    "slow_ma": slow_ma[-1],
                    "cross_type": "death",
                },
            )

        return None

    def _detect_cross(self, fast_ma: list, slow_ma: list) -> Optional[str]:
        """
        检测均线交叉

        Args:
            fast_ma: 快线数据
            slow_ma: 慢线数据

        Returns:
            "golden" - 金叉
            "death" - 死叉
            None - 无交叉
        """
        # 需要最近 signal_period 个数据点来确认
        if len(fast_ma) < self.signal_period + 1:
            return None

        # 检查最近的数据
        for i in range(len(fast_ma) - self.signal_period, len(fast_ma)):
            if fast_ma[i] is None or slow_ma[i] is None:
                return None

        # 检测交叉
        prev_fast = fast_ma[-self.signal_period - 1]
        prev_slow = slow_ma[-self.signal_period - 1]
        curr_fast = fast_ma[-1]
        curr_slow = slow_ma[-1]

        # 金叉：快线从下方穿过慢线
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            return "golden"

        # 死叉：快线从上方穿过慢线
        if prev_fast >= prev_slow and curr_fast < curr_slow:
            return "death"

        return None


class TripleMACrossStrategy(BaseStrategy):
    """
    三均线交叉策略

    使用短期、中期、长期三条均线。
    """

    def __init__(self, config: StrategyConfig):
        super().__init__(config)

        self.short_period = config.get("short_period", 5)
        self.medium_period = config.get("medium_period", 10)
        self.long_period = config.get("long_period", 30)

    def generate_signal(
        self,
        analyzer: QuoteDataAnalyzer,
        account_info: Dict[str, Any],
    ) -> Optional[StrategySignal]:
        """生成交易信号"""
        if len(analyzer.quotes) < self.long_period + 3:
            return None

        # 计算三条均线
        short_ma = analyzer.get_sma(self.short_period)
        medium_ma = analyzer.get_sma(self.medium_period)
        long_ma = analyzer.get_sma(self.long_period)

        # 检查有效性
        if short_ma[-1] is None or medium_ma[-1] is None or long_ma[-1] is None:
            return None

        latest_quote = analyzer.quotes[-1]
        positions = account_info.get("positions", [])
        has_position = any(p.symbol == latest_quote.symbol for p in positions)

        # 多头排列：短 > 中 > 长
        if (short_ma[-1] > medium_ma[-1] > long_ma[-1] and not has_position):
            # 检查是否刚刚形成多头排列（需要至少2个数据点）
            if len(short_ma) >= 2 and (short_ma[-2] <= medium_ma[-2] or medium_ma[-2] <= long_ma[-2]):
                quantity = self.get_position_size(latest_quote.price, account_info, 0.30)

                return StrategySignal(
                    signal_type=SignalType.BUY,
                    symbol=latest_quote.symbol,
                    price=latest_quote.price,
                    quantity=quantity,
                    confidence=0.8,
                    reasoning=f"三均线多头排列 (MA{self.short_period} > MA{self.medium_period} > MA{self.long_period})",
                    metadata={
                        "short_ma": short_ma[-1],
                        "medium_ma": medium_ma[-1],
                        "long_ma": long_ma[-1],
                    },
                )

        # 空头排列：短 < 中 < 长
        elif (short_ma[-1] < medium_ma[-1] < long_ma[-1] and has_position):
            # 检查是否刚刚形成空头排列（需要至少2个数据点）
            if len(short_ma) >= 2 and (short_ma[-2] >= medium_ma[-2] or medium_ma[-2] >= long_ma[-2]):
                position = next(p for p in positions if p.symbol == latest_quote.symbol)

                return StrategySignal(
                    signal_type=SignalType.SELL,
                    symbol=latest_quote.symbol,
                    price=latest_quote.price,
                    quantity=position.shares,
                    confidence=0.8,
                    reasoning=f"三均线空头排列 (MA{self.short_period} < MA{self.medium_period} < MA{self.long_period})",
                    metadata={
                        "short_ma": short_ma[-1],
                        "medium_ma": medium_ma[-1],
                        "long_ma": long_ma[-1],
                    },
                )

        return None
