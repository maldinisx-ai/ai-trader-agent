# -*- coding: utf-8 -*-
"""
下单工具
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

from core.tool_executor import Tool
from core.schemas import Order, OrderSide, OrderType, OrderStatus, PolicyResult


class PlaceOrderTool(Tool):
    """
    下单工具

    创建买入或卖出订单，包含风控检查。
    """

    def __init__(self, policy_engine=None):
        """
        初始化下单工具

        Args:
            policy_engine: 风控引擎（可选）
        """
        super().__init__()
        self.policy_engine = policy_engine

    @property
    def name(self) -> str:
        return "place_order"

    @property
    def description(self) -> str:
        return "创建买入或卖出订单，自动进行风控检查"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码（如 600519）",
                },
                "side": {
                    "type": "string",
                    "enum": ["buy", "sell"],
                    "description": "买卖方向",
                },
                "quantity": {
                    "type": "integer",
                    "description": "数量（100 的整数倍）",
                },
                "price": {
                    "type": "number",
                    "description": "委托价格（限价单，可选）",
                },
                "order_type": {
                    "type": "string",
                    "enum": ["market", "limit"],
                    "description": "订单类型，默认 market",
                },
            },
            "required": ["symbol", "side", "quantity"],
        }

    async def _execute(self, **kwargs) -> Order:
        """
        执行下单

        Args:
            symbol: 股票代码
            side: 买卖方向
            quantity: 数量
            price: 价格（可选）
            order_type: 订单类型

        Returns:
            Order: 订单对象
        """
        symbol = kwargs.get("symbol", "")
        side_str = kwargs.get("side", "")
        quantity = kwargs.get("quantity", 0)
        price = kwargs.get("price")
        order_type_str = kwargs.get("order_type", "market")

        # 参数转换
        side = OrderSide.BUY if side_str == "buy" else OrderSide.SELL
        order_type = OrderType.MARKET if order_type_str == "market" else OrderType.LIMIT

        # 创建订单
        order = Order(
            order_id=str(uuid4()),
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
            status=OrderStatus.PENDING,
        )

        # 风控检查（如果有风控引擎）
        if self.policy_engine:
            policy_result = await self._check_policy(order)
            if not policy_result.allowed:
                order.status = OrderStatus.REJECTED
                order.reject_reason = policy_result.reason
                return order

        # 订单创建成功（实际撮合由 matcher 处理）
        order.status = OrderStatus.PENDING

        return order

    async def _check_policy(self, order: Order) -> PolicyResult:
        """
        风控检查

        Args:
            order: 订单对象

        Returns:
            PolicyResult: 风控结果
        """
        if self.policy_engine is None:
            return PolicyResult(allowed=True)

        try:
            # 调用风控引擎检查
            result = await self.policy_engine.check(order)
            return result
        except Exception as e:
            # 风控检查失败，拒绝订单
            return PolicyResult(
                allowed=False,
                reason=f"风控检查异常: {str(e)}",
            )


class PlaceOrderToolMock(PlaceOrderTool):
    """
    下单工具（模拟版本，用于测试）
    """

    async def _execute(self, **kwargs) -> Order:
        """返回模拟订单"""
        symbol = kwargs.get("symbol", "")
        side_str = kwargs.get("side", "")
        quantity = kwargs.get("quantity", 0)
        price = kwargs.get("price")

        side = OrderSide.BUY if side_str == "buy" else OrderSide.SELL

        order = Order(
            order_id=str(uuid4()),
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=OrderType.MARKET,
            status=OrderStatus.PENDING,
        )

        # 模拟风控通过
        return order
