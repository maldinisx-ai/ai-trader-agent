# -*- coding: utf-8 -*-
"""
趋势评分策略

基于 daily_stock_analysis 的严进策略：
1. 多头排列（MA5 > MA10 > MA20）
2. 乖离率控制（不追高，<5%）
3. 缩量回调偏好
4. 综合评分决策
"""

import logging
from typing import Dict, Any, Optional

from .base import BaseStrategy, StrategyConfig, StrategySignal, SignalType
from src.indicators import QuoteDataAnalyzer
from core.scoring import TrendScoringSystem, ScoreResult
from core.schemas import BuySignal


logger = logging.getLogger(__name__)


class TrendScoringStrategy(BaseStrategy):
    """
    趋势评分策略

    使用综合评分系统生成交易信号，基于：
    - 趋势状态（多头排列）
    - 乖离率控制（不追高）
    - 量能分析（偏好缩量回调）
    - 支撑压力位
    - MACD 和 RSI 状态

    评分阈值：
    - ≥75: 强烈买入
    - ≥60: 买入
    - ≥45: 持有
    - ≥30: 观望
    - <30: 卖出
    """

    def __init__(self, config: StrategyConfig):
        super().__init__(config)

        # 获取配置参数
        self.bias_threshold = config.get("bias_threshold", 5.0)
        self.volume_shrink_ratio = config.get("volume_shrink_ratio", 0.7)
        self.volume_heavy_ratio = config.get("volume_heavy_ratio", 1.5)
        self.ma_support_tolerance = config.get("ma_support_tolerance", 0.02)

        # 信号阈值
        self.strong_buy_threshold = config.get("strong_buy_threshold", 75)
        self.buy_threshold = config.get("buy_threshold", 60)
        self.hold_threshold = config.get("hold_threshold", 45)
        self.wait_threshold = config.get("wait_threshold", 30)

        # 自定义权重（可选）
        self.scoring_weights = config.get("scoring_weights", None)

        # 创建评分系统
        self.scorer = TrendScoringSystem(weights=self.scoring_weights)

    def generate_signal(
        self,
        analyzer: QuoteDataAnalyzer,
        account_info: Dict[str, Any],
    ) -> Optional[StrategySignal]:
        """
        生成交易信号

        Args:
            analyzer: 行情数据分析器
            account_info: 账户信息

        Returns:
            策略信号
        """
        if len(analyzer.quotes) < 20:
            logger.warning("数据不足，无法生成信号")
            return None

        # 获取最新行情
        latest_quote = analyzer.quotes[-1]

        # 计算评分
        result: ScoreResult = self.scorer.score(analyzer)

        # 获取持仓
        positions = account_info.get("positions", [])
        has_position = any(p.symbol == latest_quote.symbol for p in positions)

        # 根据信号类型和持仓情况生成操作
        if not has_position:
            return self._generate_buy_signal(latest_quote, result, account_info)
        else:
            return self._generate_sell_signal(latest_quote, result, positions, account_info)

    def _generate_buy_signal(
        self,
        quote,
        result: ScoreResult,
        account_info: Dict[str, Any],
    ) -> Optional[StrategySignal]:
        """生成买入信号"""
        # 只在买入信号时操作
        if result.buy_signal not in [BuySignal.BUY, BuySignal.STRONG_BUY]:
            return None

        # 计算仓位
        quantity = self.get_position_size(
            quote.price,
            account_info,
            self.config.get("max_position_ratio", 0.30),
        )

        # 根据信号强度调整置信度
        if result.buy_signal == BuySignal.STRONG_BUY:
            confidence = 0.9
        else:
            confidence = 0.7

        return StrategySignal(
            signal_type=SignalType.BUY,
            symbol=quote.symbol,
            price=quote.price,
            quantity=quantity,
            confidence=confidence,
            reasoning=self._format_reasoning(result),
            metadata={
                "score_result": result.to_dict(),
                "total_score": result.total_score,
            },
        )

    def _generate_sell_signal(
        self,
        quote,
        result: ScoreResult,
        positions: list,
        account_info: Dict[str, Any],
    ) -> Optional[StrategySignal]:
        """生成卖出信号"""
        position = next((p for p in positions if p.symbol == quote.symbol), None)
        if position is None:
            return None

        # 检查止损止盈
        pnl_ratio = getattr(position, "pnl_ratio", 0)
        stop_loss = self.config.get("stop_loss_threshold", -0.05)
        take_profit = self.config.get("take_profit_threshold", 0.15)

        # 止损检查
        if pnl_ratio < stop_loss:
            return StrategySignal(
                signal_type=SignalType.SELL,
                symbol=quote.symbol,
                price=quote.price,
                quantity=position.shares,
                confidence=1.0,
                reasoning=f"止损：亏损{pnl_ratio*100:.1f}%",
                metadata={
                    "score_result": result.to_dict(),
                    "pnl_ratio": pnl_ratio,
                    "reason": "stop_loss",
                },
            )

        # 止盈检查
        if pnl_ratio > take_profit:
            return StrategySignal(
                signal_type=SignalType.SELL,
                symbol=quote.symbol,
                price=quote.price,
                quantity=position.shares,
                confidence=0.8,
                reasoning=f"止盈：盈利{pnl_ratio*100:.1f}%",
                metadata={
                    "score_result": result.to_dict(),
                    "pnl_ratio": pnl_ratio,
                    "reason": "take_profit",
                },
            )

        # 根据评分决定卖出
        if result.buy_signal in [BuySignal.SELL, BuySignal.STRONG_SELL]:
            confidence = 0.9 if result.buy_signal == BuySignal.STRONG_SELL else 0.7

            return StrategySignal(
                signal_type=SignalType.SELL,
                symbol=quote.symbol,
                price=quote.price,
                quantity=position.shares,
                confidence=confidence,
                reasoning=self._format_reasoning(result),
                metadata={
                    "score_result": result.to_dict(),
                    "total_score": result.total_score,
                    "pnl_ratio": pnl_ratio,
                },
            )

        return None

    def _format_reasoning(self, result: ScoreResult) -> str:
        """格式化推理说明"""
        parts = [f"评分:{result.total_score}/100"]

        if result.reasons:
            parts.append(" ".join(result.reasons))

        if result.risk_factors:
            parts.append("风险:" + " ".join(result.risk_factors))

        return " | ".join(parts)
