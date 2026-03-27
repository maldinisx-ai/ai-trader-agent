# -*- coding: utf-8 -*-
"""
多维度综合策略

结合技术面、基本面、资金面的智能交易策略。
"""

import logging
from typing import Dict, Any, Optional

from .base import BaseStrategy, StrategyConfig, StrategySignal, SignalType
from src.indicators import QuoteDataAnalyzer
from core.comprehensive_scoring import ComprehensiveScoringSystem, ComprehensiveScore
from core.schemas import BuySignal


logger = logging.getLogger(__name__)


class ComprehensiveStrategy(BaseStrategy):
    """
    多维度综合策略

    基于 3 个维度的综合评分系统：
    - 技术面 (35%): 趋势、乖离率、量能、MACD、RSI
    - 基本面 (35%): ROE、成长性、估值、质量
    - 资金面 (30%): 主力流入、净流入、融资融券

    评分阈值:
    - ≥75: 强烈买入
    - ≥60: 买入
    - ≥45: 持有
    - ≥30: 观望
    - <30: 卖出
    """

    def __init__(self, config: StrategyConfig):
        super().__init__(config)

        # 获取数据目录
        self.data_dir = config.get("data_dir", "data")

        # 创建综合评分系统
        self.scorer = ComprehensiveScoringSystem(data_dir=self.data_dir)

        # 信号阈值
        self.strong_buy_threshold = config.get("strong_buy_threshold", 75)
        self.buy_threshold = config.get("buy_threshold", 60)
        self.hold_threshold = config.get("hold_threshold", 45)
        self.wait_threshold = config.get("wait_threshold", 30)

        # 止损止盈
        self.stop_loss_threshold = config.get("stop_loss_threshold", -0.08)  # -8%
        self.take_profit_threshold = config.get("take_profit_threshold", 0.20)  # +20%

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
        symbol = latest_quote.symbol
        current_price = latest_quote.price

        # 计算综合评分
        result: ComprehensiveScore = self.scorer.score(
            symbol=symbol,
            analyzer=analyzer,
            current_price=current_price
        )

        # 获取持仓
        positions = account_info.get("positions", [])
        has_position = any(p.symbol == symbol for p in positions)

        # 根据信号类型和持仓情况生成操作
        if not has_position:
            return self._generate_buy_signal(latest_quote, result, account_info)
        else:
            return self._generate_sell_signal(latest_quote, result, positions, account_info)

    def _generate_buy_signal(
        self,
        quote,
        result: ComprehensiveScore,
        account_info: Dict[str, Any],
    ) -> Optional[StrategySignal]:
        """生成买入信号"""
        # 只在买入信号时操作
        if result.buy_signal not in [BuySignal.BUY, BuySignal.STRONG_BUY]:
            return None

        # 计算仓位
        max_position_ratio = self.config.get("max_position_ratio", 0.30)
        quantity = self.get_position_size(
            quote.price,
            account_info,
            max_position_ratio,
        )

        # 根据信号强度和综合得分调整置信度
        if result.buy_signal == BuySignal.STRONG_BUY:
            confidence = 0.9
        else:
            # 根据综合得分调整置信度
            confidence = min(0.85, 0.5 + result.total_score / 200)

        return StrategySignal(
            signal_type=SignalType.BUY,
            symbol=quote.symbol,
            price=quote.price,
            quantity=quantity,
            confidence=confidence,
            reasoning=self._format_reasoning(result),
            metadata={
                "comprehensive_result": result.to_dict(),
                "total_score": result.total_score,
                "technical_score": result.technical_score,
                "fundamental_score": result.fundamental_score,
                "money_flow_score": result.money_flow_score,
            },
        )

    def _generate_sell_signal(
        self,
        quote,
        result: ComprehensiveScore,
        positions: list,
        account_info: Dict[str, Any],
    ) -> Optional[StrategySignal]:
        """生成卖出信号"""
        position = next((p for p in positions if p.symbol == quote.symbol), None)
        if position is None:
            return None

        # 检查止损止盈
        pnl_ratio = getattr(position, "pnl_ratio", 0)

        # 止损检查
        if pnl_ratio < self.stop_loss_threshold:
            return StrategySignal(
                signal_type=SignalType.SELL,
                symbol=quote.symbol,
                price=quote.price,
                quantity=position.shares,
                confidence=1.0,
                reasoning=f"止损：亏损{pnl_ratio*100:.1f}%",
                metadata={
                    "comprehensive_result": result.to_dict(),
                    "pnl_ratio": pnl_ratio,
                    "reason": "stop_loss",
                },
            )

        # 止盈检查
        if pnl_ratio > self.take_profit_threshold:
            return StrategySignal(
                signal_type=SignalType.SELL,
                symbol=quote.symbol,
                price=quote.price,
                quantity=position.shares,
                confidence=0.8,
                reasoning=f"止盈：盈利{pnl_ratio*100:.1f}%",
                metadata={
                    "comprehensive_result": result.to_dict(),
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
                    "comprehensive_result": result.to_dict(),
                    "total_score": result.total_score,
                    "pnl_ratio": pnl_ratio,
                    "reason": "signal",
                },
            )

        return None

    def _format_reasoning(self, result: ComprehensiveScore) -> str:
        """格式化推理说明"""
        parts = [f"评分:{result.total_score}/100"]

        # 添加各维度得分
        parts.append(f"技术:{result.technical_score}")
        parts.append(f"基本面:{result.fundamental_score}")
        parts.append(f"资金:{result.money_flow_score}")

        if result.reasons:
            parts.append(" " + " ".join(result.reasons))

        if result.risk_factors:
            parts.append(" 风险:" + " ".join(result.risk_factors))

        return " | ".join(parts)