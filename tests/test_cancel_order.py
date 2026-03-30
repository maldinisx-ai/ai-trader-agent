# -*- coding: utf-8 -*-
"""
撤单功能测试

测试 Matcher.cancel_order() 和 CancelOrderTool
"""

import pytest
from datetime import datetime

from core.schemas import (
    Order, OrderSide, OrderType, OrderStatus, QuoteData,
)
from simulation.matcher import Matcher
from tools.trading.cancel_order import CancelOrderTool, CancelOrderToolMock
from core.policy_engine import PolicyEngine


@pytest.fixture
def matcher():
    """创建撮合引擎"""
    return Matcher()


@pytest.fixture
def sample_quote():
    """创建示例行情"""
    return QuoteData(
        symbol="600519",
        name="贵州茅台",
        price=1680.00,
        change=1.2,
        volume=1234567,
        amount=2100000000.0,
        high=1695.00,
        low=1675.00,
        upper_limit=1848.00,
        lower_limit=1512.00,
    )


@pytest.fixture
def pending_order():
    """创建待成交订单"""
    return Order(
        order_id="TEST_ORDER_001",
        symbol="600519",
        side=OrderSide.BUY,
        quantity=100,
        price=1680.00,
        order_type=OrderType.MARKET,
        status=OrderStatus.PENDING,
    )


@pytest.fixture
def filled_order():
    """创建已成交订单"""
    return Order(
        order_id="TEST_ORDER_002",
        symbol="600519",
        side=OrderSide.BUY,
        quantity=100,
        price=1680.00,
        order_type=OrderType.MARKET,
        status=OrderStatus.FILLED,
        filled_quantity=100,
        filled_price=1680.00,
        filled_at=datetime.now(),
    )


@pytest.fixture
def policy_engine():
    """创建风控引擎"""
    return PolicyEngine(
        cash=1_000_000.0,
        max_position_ratio=0.30,
    )


class TestMatcherCancelOrder:
    """测试 Matcher.cancel_order()"""

    @pytest.mark.asyncio
    async def test_cancel_pending_order(self, matcher, sample_quote, pending_order):
        """测试撤销待成交订单"""
        # 更新行情
        matcher.update_quote(sample_quote)

        # 模拟订单被追踪（实际在 match() 中完成）
        matcher._active_orders[pending_order.order_id] = pending_order

        # 撤单
        result = await matcher.cancel_order(pending_order.order_id)

        # 验证
        assert result.status == OrderStatus.CANCELLED
        assert result.order_id == pending_order.order_id
        assert pending_order.order_id not in matcher._active_orders

    @pytest.mark.asyncio
    async def test_cancel_partially_filled_order(self, matcher, sample_quote):
        """测试撤销部分成交订单"""
        order = Order(
            order_id="TEST_PARTIAL_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=1000,
            price=1680.00,
            order_type=OrderType.MARKET,
            status=OrderStatus.PARTIALLY_FILLED,
            filled_quantity=500,
        )

        # 更新行情
        matcher.update_quote(sample_quote)
        matcher._active_orders[order.order_id] = order

        # 撤单
        result = await matcher.cancel_order(order.order_id)

        # 验证
        assert result.status == OrderStatus.CANCELLED
        assert result.filled_quantity == 500  # 已成交数量不变

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_order(self, matcher):
        """测试撤销不存在的订单"""
        with pytest.raises(ValueError, match="订单不存在"):
            await matcher.cancel_order("NONEXISTENT_ORDER")

    @pytest.mark.asyncio
    async def test_cancel_filled_order_raises_error(self, matcher, filled_order):
        """测试撤销已成交订单应该抛出异常（Matcher层检查）"""
        # 模拟已成交订单
        filled_order.status = OrderStatus.FILLED
        matcher._active_orders[filled_order.order_id] = filled_order

        # Matcher 会抛出异常
        with pytest.raises(ValueError):
            await matcher.cancel_order(filled_order.order_id)

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled_order_raises_error(self, matcher, pending_order):
        """测试撤销已撤销的订单应该抛出异常"""
        # 设置为已撤销
        pending_order.status = OrderStatus.CANCELLED
        matcher._active_orders[pending_order.order_id] = pending_order

        # 撤单应该抛出异常
        with pytest.raises(ValueError):
            await matcher.cancel_order(pending_order.order_id)


class TestCancelOrderTool:
    """测试 CancelOrderTool"""

    @pytest.mark.asyncio
    async def test_tool_without_matcher(self):
        """测试没有 matcher 的工具（Mock版本）"""
        tool = CancelOrderToolMock()

        result = await tool.execute(order_id="TEST_001")

        assert result.success
        assert result.data.status == OrderStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_tool_with_matcher(self, matcher, sample_quote, pending_order):
        """测试有 matcher 的工具"""
        # 更新行情
        matcher.update_quote(sample_quote)
        matcher._active_orders[pending_order.order_id] = pending_order

        # 创建工具
        tool = CancelOrderTool(matcher=matcher)

        # 撤单
        result = await tool.execute(order_id=pending_order.order_id)

        assert result.success
        assert result.data.status == OrderStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_tool_with_invalid_order_id(self, matcher):
        """测试无效订单 ID"""
        tool = CancelOrderTool(matcher=matcher)

        result = await tool.execute(order_id="INVALID_ID")

        assert result.success
        # 工具返回 REJECTED 状态，包含错误信息
        assert result.data.status == OrderStatus.REJECTED
        assert result.data.reject_reason

    @pytest.mark.asyncio
    async def test_tool_with_empty_order_id(self, matcher):
        """测试空订单 ID"""
        tool = CancelOrderTool(matcher=matcher)

        result = await tool.execute(order_id="")

        assert not result.success
        assert "订单ID不能为空" in result.error

    def test_tool_name_and_schema(self):
        """测试工具元数据"""
        tool = CancelOrderTool()

        assert tool.name == "cancel_order"
        assert "撤销" in tool.description

        schema = tool.parameters_schema
        assert "order_id" in schema["properties"]
        assert schema["required"] == ["order_id"]


class TestCancelOrderPolicy:
    """测试撤单风控"""

    def test_allow_cancel_pending_order(self, policy_engine, pending_order):
        """测试允许撤销待成交订单"""
        result = policy_engine.validate_cancel_order(pending_order)

        assert result.allowed
        assert result.reason is None

    def test_reject_cancel_filled_order(self, policy_engine, filled_order):
        """测试拒绝撤销已成交订单"""
        result = policy_engine.validate_cancel_order(filled_order)

        assert not result.allowed
        assert "已成交" in result.reason

    def test_reject_cancel_rejected_order(self, policy_engine):
        """测试拒绝撤销已拒绝订单"""
        order = Order(
            order_id="TEST_003",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1680.00,
            order_type=OrderType.MARKET,
            status=OrderStatus.REJECTED,
            reject_reason="资金不足",
        )

        result = policy_engine.validate_cancel_order(order)

        assert not result.allowed
        assert "拒绝" in result.reason

    def test_reject_cancel_already_cancelled_order(self, policy_engine):
        """测试拒绝撤销已撤销订单"""
        order = Order(
            order_id="TEST_004",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1680.00,
            order_type=OrderType.MARKET,
            status=OrderStatus.CANCELLED,
        )

        result = policy_engine.validate_cancel_order(order)

        assert not result.allowed
        assert "已撤销" in result.reason

    def test_allow_cancel_partially_filled_order(self, policy_engine):
        """测试允许撤销部分成交订单"""
        order = Order(
            order_id="TEST_005",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=1000,
            price=1680.00,
            order_type=OrderType.MARKET,
            status=OrderStatus.PARTIALLY_FILLED,
            filled_quantity=500,
        )

        result = policy_engine.validate_cancel_order(order)

        assert result.allowed


class TestCancelOrderIntegration:
    """撤单集成测试"""

    @pytest.mark.asyncio
    async def test_full_cancel_flow(self, matcher, sample_quote, policy_engine):
        """测试完整撤单流程：下单 -> 追踪 -> 撤单"""
        # 1. 创建订单
        order = Order(
            order_id="INTEGRATION_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1680.00,
            order_type=OrderType.MARKET,
            status=OrderStatus.PENDING,
        )

        # 2. 更新行情
        matcher.update_quote(sample_quote)

        # 3. 模拟撮合
        match_result = await matcher.match(order)
        assert match_result.fully_filled

        # 4. 创建新订单进行撤单测试
        order2 = Order(
            order_id="INTEGRATION_002",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1680.00,
            order_type=OrderType.LIMIT,
            status=OrderStatus.PENDING,
        )
        matcher._active_orders[order2.order_id] = order2

        # 5. 风控检查
        policy_result = policy_engine.validate_cancel_order(order2)
        assert policy_result.allowed

        # 6. 撤单
        cancelled_order = await matcher.cancel_order(order2.order_id)
        assert cancelled_order.status == OrderStatus.CANCELLED

        # 7. 验证订单不再在活跃列表中
        assert order2.order_id not in matcher._active_orders

    @pytest.mark.asyncio
    async def test_cancel_with_policy_engine(self, matcher, sample_quote, policy_engine):
        """测试通过风控引擎撤单"""
        # 创建工具（传入 matcher 和 policy_engine）
        tool = CancelOrderTool(
            matcher=matcher,
            policy_engine=policy_engine,
        )

        # 创建订单
        order = Order(
            order_id="POLICY_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1680.00,
            order_type=OrderType.MARKET,
            status=OrderStatus.PENDING,
        )

        # 更新行情并追踪订单
        matcher.update_quote(sample_quote)
        matcher._active_orders[order.order_id] = order

        # 执行撤单
        result = await tool.execute(order_id=order.order_id)

        # 验证
        assert result.success
        assert result.data.status == OrderStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_filled_order_blocked_by_policy(self, matcher, sample_quote, policy_engine):
        """测试已成交订单被风控拒绝"""
        # 创建工具
        tool = CancelOrderTool(
            matcher=matcher,
            policy_engine=policy_engine,
        )

        # 创建已成交订单
        order = Order(
            order_id="POLICY_FILLED_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1680.00,
            order_type=OrderType.MARKET,
            status=OrderStatus.FILLED,
            filled_quantity=100,
            filled_price=1680.00,
        )

        # 更新行情并追踪订单
        matcher.update_quote(sample_quote)
        matcher._active_orders[order.order_id] = order

        # 执行撤单
        result = await tool.execute(order_id=order.order_id)

        # 验证被风控拒绝
        assert result.success
        assert result.data.status == OrderStatus.REJECTED
        assert "已成交" in result.data.reject_reason