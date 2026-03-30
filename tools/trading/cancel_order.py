# -*- coding: utf-8 -*-
"""
撤单工具
"""

import asyncio
from typing import Dict, Any
from uuid import uuid4

from core.tool_executor import Tool
from core.schemas import Order, OrderStatus


class CancelOrderTool(Tool):
    """
    撤单工具

    撤销未成交或部分成交的订单。
    """

    def __init__(self, matcher=None, policy_engine=None):
        """
        初始化撤单工具

        Args:
            matcher: 撮合引擎实例
            policy_engine: 风控引擎实例
        """
        super().__init__()
        self.matcher = matcher
        self.policy_engine = policy_engine

    @property
    def name(self) -> str:
        return "cancel_order"

    @property
    def description(self) -> str:
        return "撤销未成交或部分成交的订单"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "订单ID",
                },
            },
            "required": ["order_id"],
        }

    async def _execute(self, **kwargs) -> Order:
        """
        执行撤单

        Args:
            order_id: 订单ID

        Returns:
            Order: 更新后的订单对象（状态为 CANCELLED）

        Raises:
            ValueError: 订单ID为空
        """
        order_id = kwargs.get("order_id", "")

        if not order_id:
            raise ValueError("订单ID不能为空")

        # 获取订单（从 matcher 中）
        if self.matcher and hasattr(self.matcher, '_active_orders'):
            order = self.matcher._active_orders.get(order_id)
        else:
            # 模拟撤单（测试用）
            order = Order(
                order_id=order_id,
                symbol="MOCK",
                side="buy",
                quantity=100,
                order_type="market",
                status=OrderStatus.PENDING,
            )

        if not order:
            # 返回包含错误信息的订单（而不是抛出异常）
            error_order = Order(
                order_id=order_id,
                symbol="ERROR",
                side="buy",
                quantity=100,  # Pydantic 要求 quantity > 0 且是100的倍数
                order_type="market",
                status=OrderStatus.REJECTED,
            )
            error_order.reject_reason = f"订单不存在: {order_id}"
            return error_order

        # 风控检查（如果有风控引擎）
        if self.policy_engine:
            policy_result = self.policy_engine.validate_cancel_order(order)
            if not policy_result.allowed:
                order.status = OrderStatus.REJECTED
                order.reject_reason = policy_result.reason
                return order

        try:
            if self.matcher:
                order = await self.matcher.cancel_order(order_id)
            else:
                # 模拟撤单成功
                order.status = OrderStatus.CANCELLED
            return order
        except ValueError as e:
            # 返回包含错误信息的订单
            error_order = Order(
                order_id=order_id,
                symbol="ERROR",
                side="buy",
                quantity=100,  # Pydantic 要求 quantity > 0 且是100的倍数
                order_type="market",
                status=OrderStatus.REJECTED,
            )
            error_order.reject_reason = str(e)
            return error_order


class CancelOrderToolMock(CancelOrderTool):
    """
    撤单工具（模拟版本，用于测试）
    """

    async def _execute(self, **kwargs) -> Order:
        """返回模拟撤单结果"""
        order_id = kwargs.get("order_id", str(uuid4()))

        order = Order(
            order_id=order_id,
            symbol="MOCK",
            side="buy",
            quantity=100,
            order_type="market",
            status=OrderStatus.CANCELLED,
        )

        return order