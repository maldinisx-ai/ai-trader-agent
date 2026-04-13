# -*- coding: utf-8 -*-
"""
测试下单工具
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock
from uuid import uuid4

# 确保模块被导入以正确收集覆盖率
import tools.trading.place_order
from core.schemas import Order, OrderSide, OrderType, OrderStatus, PolicyResult
from tools.trading.place_order import PlaceOrderTool, PlaceOrderToolMock


class TestPlaceOrderTool:
    """测试下单工具"""

    def test_init_default(self):
        """测试默认初始化"""
        tool = PlaceOrderTool()
        assert tool.name == "place_order"
        assert tool.policy_engine is None

    def test_init_with_policy_engine(self):
        """测试带风控引擎初始化"""
        mock_policy = Mock()
        tool = PlaceOrderTool(policy_engine=mock_policy)
        assert tool.policy_engine == mock_policy

    def test_parameters_schema(self):
        """测试参数模式"""
        tool = PlaceOrderTool()
        schema = tool.parameters_schema

        assert schema["type"] == "object"
        assert "symbol" in schema["properties"]
        assert "side" in schema["properties"]
        assert "quantity" in schema["properties"]
        assert "price" in schema["properties"]
        assert "order_type" in schema["properties"]
        assert "symbol" in schema["required"]
        assert "side" in schema["required"]
        assert "quantity" in schema["required"]

    @pytest.mark.asyncio
    async def test_execute_buy_order(self):
        """测试买入订单"""
        tool = PlaceOrderToolMock()
        order = await tool.execute(
            symbol="600519",
            side="buy",
            quantity=100,
            price=1680.0
        )

        assert order.symbol == "600519"
        assert order.side == OrderSide.BUY
        assert order.quantity == 100
        assert order.price == 1680.0
        assert order.status == OrderStatus.PENDING

    @pytest.mark.asyncio
    async def test_execute_sell_order(self):
        """测试卖出订单"""
        tool = PlaceOrderToolMock()
        order = await tool.execute(
            symbol="600519",
            side="sell",
            quantity=100
        )

        assert order.symbol == "600519"
        assert order.side == OrderSide.SELL
        assert order.status == OrderStatus.PENDING

    @pytest.mark.asyncio
    async def test_execute_market_order(self):
        """测试市价单"""
        tool = PlaceOrderToolMock()
        order = await tool.execute(
            symbol="600519",
            side="buy",
            quantity=100,
            order_type="market"
        )

        assert order.order_type == OrderType.MARKET

    @pytest.mark.asyncio
    async def test_execute_limit_order(self):
        """测试限价单"""
        tool = PlaceOrderToolMock()
        order = await tool.execute(
            symbol="600519",
            side="buy",
            quantity=100,
            price=1680.0,
            order_type="limit"
        )

        assert order.order_type == OrderType.LIMIT

    @pytest.mark.asyncio
    async def test_execute_missing_required_params(self):
        """测试缺少必需参数"""
        tool = PlaceOrderTool()

        with pytest.raises(TypeError):
            await tool.execute(side="buy", quantity=100)

    @pytest.mark.asyncio
    async def test_check_policy_pass(self):
        """测试风控检查通过"""
        mock_policy = AsyncMock(return_value=PolicyResult(allowed=True))
        tool = PlaceOrderTool(policy_engine=mock_policy)

        order = await tool.execute(
            symbol="600519",
            side="buy",
            quantity=100
        )

        assert order.status == OrderStatus.PENDING

    @pytest.mark.asyncio
    async def test_check_policy_reject(self):
        """测试风控拒绝"""
        mock_policy = AsyncMock(
            return_value=PolicyResult(
                allowed=False,
                reason="资金不足"
            )
        )
        tool = PlaceOrderTool(policy_engine=mock_policy)

        order = await tool.execute(
            symbol="600519",
            side="buy",
            quantity=100
        )

        assert order.status == OrderStatus.REJECTED
        assert "资金不足" in order.reject_reason

    @pytest.mark.asyncio
    async def test_check_policy_error(self):
        """测试风控检查异常"""
        mock_policy = AsyncMock(side_effect=Exception("风控错误"))
        tool = PlaceOrderTool(policy_engine=mock_policy)

        order = await tool.execute(
            symbol="600519",
            side="buy",
            quantity=100
        )

        assert order.status == OrderStatus.REJECTED
        assert "风控" in order.reject_reason


class TestPlaceOrderToolMock:
    """测试模拟下单工具"""

    def test_mock_order_id(self):
        """测试模拟订单ID生成"""
        tool = PlaceOrderToolMock()
        order = tool._execute_sync(
            symbol="600519",
            side="buy",
            quantity=100
        )

        # 验证是有效的UUID
        uuid.UUID(order.order_id)
        assert order.status == OrderStatus.PENDING

    @pytest.mark.asyncio
    async def test_mock_multiple_orders(self):
        """测试多次创建订单"""
        tool = PlaceOrderToolMock()

        order_ids = []
        for i in range(5):
            order = await tool.execute(
                symbol="600519",
                side="buy",
                quantity=100
            )
            order_ids.append(order.order_id)

        # 验证每个订单ID都不同
        assert len(set(order_ids)) == 5

    @pytest.mark.asyncio
    async def test_mock_order_properties(self):
        """测试模拟订单属性"""
        tool = PlaceOrderToolMock()
        order = await tool.execute(
            symbol="000001",
            side="sell",
            quantity=200,
            price=12.50
        )

        assert order.symbol == "000001"
        assert order.side == OrderSide.SELL
        assert order.quantity == 200
        assert order.price == 12.50
        assert order.order_type == OrderType.MARKET  # Mock默认


class TestOrder:
    """测试订单数据"""

    def test_order_creation(self):
        """测试创建订单"""
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1680.0,
            order_type=OrderType.LIMIT
        )

        assert order.order_id == "ord_001"
        assert order.symbol == "600519"
        assert order.side == OrderSide.BUY
        assert order.quantity == 100
        assert order.price == 1680.0
        assert order.order_type == OrderType.LIMIT
        assert order.status == OrderStatus.PENDING

    def test_order_default_values(self):
        """测试订单默认值"""
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100
        )

        assert order.order_type == OrderType.MARKET  # 默认市价单
        assert order.status == OrderStatus.PENDING  # 默认待提交
        assert order.ack_id is None  # 默认未成交


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
