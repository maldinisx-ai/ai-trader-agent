# -*- coding: utf-8 -*-
"""
反思机制

对亏损交易进行反思分析，生成改进建议。

触发条件:
- 交易亏损离场时（收益率 < -2%）
- 连续3笔亏损

反思内容:
- 亏损股票和亏损金额
- 亏损原因分析（追高、未设止损、市场突变等）
- K线形态记录
- 下次应对策略
- 存储到情节记忆
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass

from core.schemas import (
    Trade, OrderSide, ErrorType, ReflectionRecord,
    DecisionChain,
)


@dataclass
class DecisionChain:
    """决策链路"""
    trade_id: str
    thought_process: str
    tool_calls: list[dict]
    observations: list[dict]
    final_decision: dict


class ReflectionEngine:
    """
    反思引擎

    生成反思记录，从失败交易中学习
    """

    LOSS_THRESHOLD = -0.02  # 2% 亏损触发反思
    CONSECUTIVE_LOSS = 3      # 连续3笔亏损触发反思

    def __init__(self):
        """初始化反思引擎"""
        self._reflections: list[ReflectionRecord] = []

    async def reflect_on_loss(
        self,
        trade: Trade,
        loss_ratio: float,
        decision_chain: Optional[DecisionChain] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ReflectionRecord:
        """
        对亏损交易进行反思

        Args:
            trade: 交易记录
            loss_ratio: 亏损比例（负数）
            decision_chain: 决策链路
            context: 上下文信息

        Returns:
            ReflectionRecord: 反思记录
        """
        # 1. 识别错误类型
        error_type = self._classify_error(
            trade,
            context.get("max_price") if context else None,
            context.get("total_value") if context else None,
            loss_ratio,
        )

        # 2. 生成反思内容
        reflection = ReflectionRecord(
            reflection_id=f"ref_{trade.trade_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            trade_id=trade.trade_id,
            loss_amount=trade.amount * abs(loss_ratio),
            loss_ratio=abs(loss_ratio),
            error_type=error_type,
            analysis=self._generate_analysis(trade, error_type, decision_chain),
            lesson=self._generate_lesson(error_type),
            avoid_action=self._generate_avoid_action(error_type),
            timestamp=datetime.now(),
        )

        # 3. 存储反思记录
        self._reflections.append(reflection)

        return reflection

    def _classify_error(
        self,
        trade: Trade,
        max_price: Optional[float] = None,
        total_value: Optional[float] = None,
        loss_ratio: Optional[float] = None,
    ) -> ErrorType:
        """
        分类错误类型

        Args:
            trade: 交易记录
            max_price: 持仓期间最高价
            total_value: 总资产
            loss_ratio: 亏损比例

        Returns:
            ErrorType: 错误类型
        """
        # 检查入场时机错误（2小时内亏损>5%）
        if loss_ratio and loss_ratio < -0.05:
            holding_duration = datetime.now() - trade.timestamp
            if holding_duration < timedelta(hours=2):
                return ErrorType.ENTRY

        # 检查时机错误（追高）
        if max_price and trade.price:
            # 入场价 > 最高价 × 0.95 视为追高
            if trade.price >= max_price * 0.95:
                return ErrorType.TIMING

        # 检查仓位错误（持仓比例>20%）
        if total_value and trade.amount:
            position_ratio = trade.amount / total_value
            if position_ratio > 0.2:
                return ErrorType.POSITION

        # 默认为出场错误
        return ErrorType.EXIT

    def _generate_analysis(
        self,
        trade: Trade,
        error_type: ErrorType,
        decision_chain: Optional[DecisionChain] = None,
    ) -> str:
        """
        生成分析内容

        Args:
            trade: 交易记录
            error_type: 错误类型
            decision_chain: 决策链路

        Returns:
            str: 分析内容
        """
        analysis_parts = [
            f"股票: {trade.symbol}",
            f"亏损: {abs(trade.pnl if hasattr(trade, 'pnl') else 0):.2f}",
        ]

        if error_type == ErrorType.ENTRY:
            analysis_parts.append("错误类型: 入场时机错误")
            analysis_parts.append("原因: 在趋势不明或弱势时过早入场")
        elif error_type == ErrorType.TIMING:
            analysis_parts.append("错误类型: 追高")
            analysis_parts.append("原因: 在高位买入，未等待回调")
        elif error_type == ErrorType.POSITION:
            analysis_parts.append("错误类型: 仓位过重")
            analysis_parts.append("原因: 单笔交易占比过高，风险过大")
        elif error_type == ErrorType.EXIT:
            analysis_parts.append("错误类型: 出场决策错误")
            analysis_parts.append("原因: 止盈/止损设置不当，未及时离场")

        return "，".join(analysis_parts) + "。"

    def _generate_lesson(self, error_type: ErrorType) -> str:
        """
        生成经验教训

        Args:
            error_type: 错误类型

        Returns:
            str: 经验教训
        """
        lessons = {
            ErrorType.ENTRY: "等待趋势确认后再入场，避免在震荡市中过早操作",
            ErrorType.TIMING: "等待回调后再买入，不要追高",
            ErrorType.POSITION: "控制单笔交易占比，分散风险",
            ErrorType.EXIT: "设置明确的止盈止损点，严格执行",
        }

        return lessons.get(error_type, "需要加强风险控制")

    def _generate_avoid_action(self, error_type: ErrorType) -> str:
        """
        生成避免措施

        Args:
            error_type: 错误类型

        Returns:
            str: 避免措施
        """
        actions = {
            ErrorType.ENTRY: "下次观察20日均线和成交量，等待趋势明确",
            ErrorType.TIMING: "等待价格回调至5日均线附近再考虑买入",
            ErrorType.POSITION: "单笔交易不超过总资产的15%",
            ErrorType.EXIT: "买入时同时设置止损位（-3%）和止盈位（+5%）",
        }

        return actions.get(error_type, "加强风险控制")

    def get_reflections(self, limit: int = 10) -> list[ReflectionRecord]:
        """
        获取反思记录

        Args:
            limit: 返回数量限制

        Returns:
            反思记录列表
        """
        return self._reflections[-limit:]

    def get_reflections_by_symbol(self, symbol: str) -> list[ReflectionRecord]:
        """
        获取指定股票的反思记录

        Args:
            symbol: 股票代码

        Returns:
            反思记录列表
        """
        return [r for r in self._reflections if symbol in r.trade_id]

    def get_reflections_by_error_type(self, error_type: ErrorType) -> list[ReflectionRecord]:
        """
        获取指定错误类型的反思记录

        Args:
            error_type: 错误类型

        Returns:
            反思记录列表
        """
        return [r for r in self._reflections if r.error_type == error_type]
