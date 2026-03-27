# -*- coding: utf-8 -*-
"""
测试工具执行器和核心工具
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.tool_executor import Tool, ToolExecutor, register_tool
from core.schemas import ToolResult, QuoteData, Order, Position, OrderSide, OrderType, OrderStatus, PolicyResult
from tools.data.get_quote import GetQuoteTool, GetQuoteToolMock
from tools.trading.place_order import PlaceOrderTool, PlaceOrderToolMock
from tools.trading.get_positions import GetPositionsTool, GetPositionsToolMock


# ============================================
# 测试工具基类
# ============================================

class MockTool(Tool):
    """模拟工具用于测试"""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "模拟工具"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
            },
            "required": ["message"],
        }

    async def _execute(self, **kwargs) -> str:
        return f"执行结果: {kwargs.get('message', '')}"


class FailingTool(Tool):
    """总是失败的工具"""

    @property
    def name(self) -> str:
        return "failing_tool"

    @property
    def description(self) -> str:
        return "总是失败的工具"

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    async def _execute(self, **kwargs) -> str:
        raise ValueError("模拟错误")


# ============================================
# Tool 基类测试
# ============================================

class TestTool:
    """测试 Tool 基类"""

    @pytest.mark.asyncio
    async def test_tool_execute_success(self):
        """测试工具执行成功"""
        tool = MockTool()
        result = await tool.execute(message="测试")

        assert result.success is True
        assert result.data == "执行结果: 测试"
        assert result.execution_time >= 0

    @pytest.mark.asyncio
    async def test_tool_execute_failure(self):
        """测试工具执行失败"""
        tool = FailingTool()
        result = await tool.execute()

        assert result.success is False
        assert "模拟错误" in result.error

    @pytest.mark.asyncio
    async def test_tool_parameter_validation_missing_required(self):
        """测试参数校验 - 缺少必需参数"""
        tool = MockTool()
        result = await tool.execute()  # 缺少 message 参数

        assert result.success is False
        assert "缺少必需参数" in result.error

    @pytest.mark.asyncio
    async def test_tool_call_count(self):
        """测试调用计数"""
        tool = MockTool()
        assert tool.call_count == 0

        await tool.execute(message="测试1")
        assert tool.call_count == 1

        await tool.execute(message="测试2")
        assert tool.call_count == 2

    @pytest.mark.asyncio
    async def test_tool_last_called(self):
        """测试最后调用时间"""
        tool = MockTool()
        assert tool.last_called is None

        await tool.execute(message="测试")
        assert tool.last_called is not None
        assert isinstance(tool.last_called, datetime)

    def test_tool_get_info(self):
        """测试获取工具信息"""
        tool = MockTool()
        info = tool.get_info()

        assert info["name"] == "mock_tool"
        assert info["description"] == "模拟工具"
        assert "parameters" in info
        assert info["call_count"] == 0


# ============================================
# ToolExecutor 测试
# ============================================

class TestToolExecutor:
    """测试 ToolExecutor"""

    def test_register_tool(self):
        """测试注册工具"""
        executor = ToolExecutor()
        tool = MockTool()

        executor.register(tool)

        assert "mock_tool" in executor.list_tools()
        assert executor.get_tool("mock_tool") is tool

    def test_register_duplicate_tool(self):
        """测试注册重复工具"""
        executor = ToolExecutor()
        tool1 = MockTool()
        tool2 = MockTool()

        executor.register(tool1)
        executor.register(tool2)  # 覆盖

        assert executor.get_tool("mock_tool") is tool2

    def test_unregister_tool(self):
        """测试注销工具"""
        executor = ToolExecutor()
        tool = MockTool()

        executor.register(tool)
        assert "mock_tool" in executor.list_tools()

        executor.unregister("mock_tool")
        assert "mock_tool" not in executor.list_tools()

    def test_get_nonexistent_tool(self):
        """测试获取不存在的工具"""
        executor = ToolExecutor()
        assert executor.get_tool("nonexistent") is None

    def test_get_tools_info(self):
        """测试获取所有工具信息"""
        executor = ToolExecutor()
        tool = MockTool()
        executor.register(tool)

        infos = executor.get_tools_info()

        assert len(infos) == 1
        assert infos[0]["name"] == "mock_tool"

    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        """测试执行工具成功"""
        executor = ToolExecutor()
        tool = MockTool()
        executor.register(tool)

        result = await executor.execute("mock_tool", message="测试")

        assert result.success is True
        assert result.data == "执行结果: 测试"

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self):
        """测试执行不存在的工具"""
        executor = ToolExecutor()

        result = await executor.execute("nonexistent")

        assert result.success is False
        assert "不存在" in result.error

    @pytest.mark.asyncio
    async def test_execute_batch(self):
        """测试批量执行"""
        executor = ToolExecutor()
        tool = MockTool()
        executor.register(tool)

        calls = [
            {"tool_name": "mock_tool", "parameters": {"message": "测试1"}},
            {"tool_name": "mock_tool", "parameters": {"message": "测试2"}},
        ]

        results = await executor.execute_batch(calls)

        assert len(results) == 2
        assert all(r.success for r in results)

    def test_get_execution_history(self):
        """测试获取执行历史"""
        executor = ToolExecutor()
        tool = MockTool()
        executor.register(tool)

        # 执行一些工具调用（通过直接添加历史记录模拟）
        executor._execution_history.append({
            "call_id": "1",
            "tool_name": "mock_tool",
            "parameters": {"message": "测试"},
            "success": True,
            "timestamp": "2024-03-23T10:00:00",
        })

        history = executor.get_execution_history()
        assert len(history) == 1
        assert history[0]["tool_name"] == "mock_tool"

    def test_get_execution_history_filter_by_tool(self):
        """测试过滤执行历史"""
        executor = ToolExecutor()
        tool = MockTool()
        executor.register(tool)

        executor._execution_history.extend([
            {
                "call_id": "1",
                "tool_name": "mock_tool",
                "parameters": {},
                "success": True,
                "timestamp": "2024-03-23T10:00:00",
            },
            {
                "call_id": "2",
                "tool_name": "other_tool",
                "parameters": {},
                "success": True,
                "timestamp": "2024-03-23T10:01:00",
            },
        ])

        history = executor.get_execution_history(tool_name="mock_tool")
        assert len(history) == 1
        assert history[0]["tool_name"] == "mock_tool"


# ============================================
# GetQuoteTool 测试
# ============================================

class TestGetQuoteTool:
    """测试 GetQuoteTool"""

    @pytest.mark.asyncio
    async def test_get_quote_tool_name(self):
        """测试工具名称"""
        tool = GetQuoteTool()
        assert tool.name == "get_quote"

    @pytest.mark.asyncio
    async def test_get_quote_tool_schema(self):
        """测试参数模式"""
        tool = GetQuoteTool()
        schema = tool.parameters_schema

        assert "symbol" in schema["properties"]
        assert "symbol" in schema["required"]

    @pytest.mark.asyncio
    async def test_get_quote_mock_tool(self):
        """测试获取行情（模拟版本）"""
        tool = GetQuoteToolMock()
        result = await tool.execute(symbol="600519", mock=True)

        assert result.success is True
        assert isinstance(result.data, QuoteData)
        assert result.data.symbol == "600519"

    @pytest.mark.asyncio
    async def test_get_quote_missing_symbol(self):
        """测试缺少股票代码"""
        tool = GetQuoteToolMock()
        result = await tool.execute()

        assert result.success is False

    @pytest.mark.asyncio
    async def test_get_quote_mock_tool(self):
        """测试获取行情（模拟版本）"""
        tool = GetQuoteToolMock()
        result = await tool.execute(symbol="600519", mock=True)

        assert result.success is True
        assert isinstance(result.data, QuoteData)
        assert result.data.symbol == "600519"

    @pytest.mark.asyncio
    async def test_get_quote_mock_unknown_symbol(self):
        """测试获取未知股票行情（生成随机数据）"""
        tool = GetQuoteToolMock()
        result = await tool.execute(symbol="999999")

        assert result.success is True
        assert isinstance(result.data, QuoteData)
        assert result.data.symbol == "999999"
        assert "股票999999" in result.data.name

    @pytest.mark.asyncio
    async def test_get_quote_real_tool_empty_symbol(self):
        """测试真实工具空股票代码抛出异常"""
        tool = GetQuoteTool()

        result = await tool.execute(symbol="")

        assert result.success is False
        assert "股票代码不能为空" in result.error

    @pytest.mark.asyncio
    async def test_get_quote_mock_tool_all_known_symbols(self):
        """测试所有已知模拟股票"""
        tool = GetQuoteToolMock()

        known_symbols = ["600519", "000001", "000002"]
        for symbol in known_symbols:
            result = await tool.execute(symbol=symbol)
            assert result.success is True
            assert result.data.symbol == symbol

    @pytest.mark.asyncio
    async def test_get_quote_mock_data_completeness(self):
        """测试模拟数据完整性"""
        tool = GetQuoteToolMock()
        result = await tool.execute(symbol="600519")

        quote = result.data
        assert quote.symbol == "600519"
        assert quote.name == "贵州茅台"
        assert quote.price == 1680.00
        assert quote.change == 1.2
        assert quote.volume == 100000
        assert quote.high == 1680.00 * 1.05
        assert quote.low == 1680.00 * 0.95

    @pytest.mark.asyncio
    async def test_get_quote_mock_tool_direct_execute(self):
        """测试 mock 工具直接调用 _execute"""
        tool = GetQuoteToolMock()
        result = await tool._execute(symbol="000001")

        assert result.symbol == "000001"
        assert result.name == "平安银行"
        assert result.price == 12.50
        assert result.change == -0.5

    @pytest.mark.asyncio
    async def test_get_quote_mock_random_data_structure(self):
        """测试随机生成数据结构正确"""
        tool = GetQuoteToolMock()
        result = await tool.execute(symbol="123456")

        quote = result.data
        # 验证数据结构
        assert quote.symbol == "123456"
        assert quote.name == "股票123456"
        assert isinstance(quote.price, float)
        assert isinstance(quote.change, float)
        assert isinstance(quote.volume, int)
        assert isinstance(quote.amount, (int, float))
        # 验证范围（允许一些宽松范围）
        assert 10 <= quote.price <= 100
        assert -10 <= quote.change <= 10
        assert quote.volume > 0


# ============================================
# PlaceOrderTool 测试
# ============================================

class TestPlaceOrderTool:
    """测试 PlaceOrderTool"""

    @pytest.mark.asyncio
    async def test_place_order_tool_name(self):
        """测试工具名称"""
        tool = PlaceOrderTool()
        assert tool.name == "place_order"

    @pytest.mark.asyncio
    async def test_place_order_tool_schema(self):
        """测试参数模式"""
        tool = PlaceOrderTool()
        schema = tool.parameters_schema

        assert "symbol" in schema["required"]
        assert "side" in schema["required"]
        assert "quantity" in schema["required"]

    @pytest.mark.asyncio
    async def test_place_order_mock_buy(self):
        """测试模拟买入订单"""
        tool = PlaceOrderToolMock()
        result = await tool.execute(
            symbol="600519",
            side="buy",
            quantity=100,
            price=1680.0,
        )

        assert result.success is True
        assert isinstance(result.data, Order)
        assert result.data.symbol == "600519"
        assert result.data.side == OrderSide.BUY
        assert result.data.quantity == 100

    @pytest.mark.asyncio
    async def test_place_order_mock_sell(self):
        """测试模拟卖出订单"""
        tool = PlaceOrderToolMock()
        result = await tool.execute(
            symbol="600519",
            side="sell",
            quantity=100,
        )

        assert result.success is True
        assert result.data.side == OrderSide.SELL

    @pytest.mark.asyncio
    async def test_place_order_mock_with_price(self):
        """测试带价格的模拟订单"""
        tool = PlaceOrderToolMock()
        result = await tool.execute(
            symbol="600519",
            side="buy",
            quantity=100,
            price=1680.0,
        )

        assert result.success is True
        assert result.data.price == 1680.0

    @pytest.mark.asyncio
    async def test_place_order_limit_order_type(self):
        """测试限价单类型"""
        # Mock 工具总是返回 MARKET，所以测试实际工具
        real_tool = PlaceOrderTool()
        result = await real_tool.execute(
            symbol="600519",
            side="buy",
            quantity=100,
            order_type="limit",
        )

        assert result.success is True
        assert result.data.order_type == OrderType.LIMIT

    @pytest.mark.asyncio
    async def test_place_order_missing_required_params(self):
        """测试缺少必需参数"""
        tool = PlaceOrderToolMock()
        result = await tool.execute(symbol="600519")  # 缺少 side 和 quantity

        assert result.success is False
        assert "缺少必需参数" in result.error

    @pytest.mark.asyncio
    async def test_place_order_without_price(self):
        """测试不带价格的订单（市价单）"""
        tool = PlaceOrderToolMock()
        result = await tool.execute(
            symbol="600519",
            side="buy",
            quantity=100,
        )

        assert result.success is True
        assert result.data.price is None

    @pytest.mark.asyncio
    async def test_place_order_order_status_pending(self):
        """测试订单状态为 PENDING"""
        tool = PlaceOrderToolMock()
        result = await tool.execute(
            symbol="600519",
            side="buy",
            quantity=100,
        )

        assert result.success is True
        assert result.data.status == OrderStatus.PENDING

    @pytest.mark.asyncio
    async def test_place_order_order_id_generation(self):
        """测试订单 ID 生成"""
        tool = PlaceOrderToolMock()
        result1 = await tool.execute(symbol="600519", side="buy", quantity=100)
        result2 = await tool.execute(symbol="600519", side="buy", quantity=100)

        assert result1.data.order_id != result2.data.order_id
        assert result1.data.order_id.startswith(("urn:uuid:", ""))

    @pytest.mark.asyncio
    async def test_place_order_with_policy_engine_rejected(self):
        """测试风控引擎拒绝订单"""
        from core.policy_engine import PolicyEngine
        from core.schemas import PolicyResult

        # 创建总是拒绝的风控引擎
        class RejectPolicyEngine(PolicyEngine):
            def __init__(self):
                super().__init__(cash=100000)  # 必需参数

            async def check(self, order: Order) -> PolicyResult:
                return PolicyResult(allowed=False, reason="测试拒绝")

        policy_engine = RejectPolicyEngine()
        tool = PlaceOrderTool(policy_engine=policy_engine)
        result = await tool.execute(
            symbol="600519",
            side="buy",
            quantity=100,
        )

        assert result.success is True
        assert result.data.status == OrderStatus.REJECTED
        assert "测试拒绝" in result.data.reject_reason

    @pytest.mark.asyncio
    async def test_place_order_with_policy_engine_allowed(self):
        """测试风控引擎允许订单"""
        from core.policy_engine import PolicyEngine
        from core.schemas import PolicyResult

        # 创建总是允许的风控引擎
        class AllowPolicyEngine(PolicyEngine):
            def __init__(self):
                super().__init__(cash=100000)

            async def check(self, order: Order) -> PolicyResult:
                return PolicyResult(allowed=True)

        policy_engine = AllowPolicyEngine()
        tool = PlaceOrderTool(policy_engine=policy_engine)
        result = await tool.execute(
            symbol="600519",
            side="buy",
            quantity=100,
        )

        assert result.success is True
        assert result.data.status == OrderStatus.PENDING

    @pytest.mark.asyncio
    async def test_place_order_policy_check_exception(self):
        """测试风控检查异常"""
        # 创建抛出异常的风控引擎
        class ErrorPolicyEngine:
            async def check(self, order: Order) -> PolicyResult:
                raise RuntimeError("风控错误")

        policy_engine = ErrorPolicyEngine()
        tool = PlaceOrderTool(policy_engine=policy_engine)
        result = await tool.execute(
            symbol="600519",
            side="buy",
            quantity=100,
        )

        assert result.success is True
        assert result.data.status == OrderStatus.REJECTED
        assert "风控检查异常" in result.data.reject_reason

    @pytest.mark.asyncio
    async def test_place_order_without_policy_engine(self):
        """测试无风控引擎的情况"""
        tool = PlaceOrderTool(policy_engine=None)
        result = await tool.execute(
            symbol="600519",
            side="buy",
            quantity=100,
        )

        assert result.success is True
        assert result.data.status == OrderStatus.PENDING

    @pytest.mark.asyncio
    async def test_place_order_check_policy_none_engine(self):
        """测试 _check_policy 方法当 engine 为 None"""
        tool = PlaceOrderTool(policy_engine=None)

        order = Order(
            order_id="test_id",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1680.0,
            order_type=OrderType.MARKET,
            status=OrderStatus.PENDING,
        )

        result = await tool._check_policy(order)
        assert result.allowed is True

    def test_place_order_tool_initialization(self):
        """测试工具初始化"""
        policy_engine = None
        tool = PlaceOrderTool(policy_engine=policy_engine)
        assert tool.policy_engine is policy_engine


# ============================================
# GetPositionsTool 测试
# ============================================

class TestGetPositionsTool:
    """测试 GetPositionsTool"""

    @pytest.mark.asyncio
    async def test_get_positions_tool_name(self):
        """测试工具名称"""
        tool = GetPositionsTool()
        assert tool.name == "get_positions"

    @pytest.mark.asyncio
    async def test_get_positions_tool_schema(self):
        """测试参数模式"""
        tool = GetPositionsTool()
        schema = tool.parameters_schema

        # symbol 不是必需参数
        assert "symbol" not in schema.get("required", [])

    @pytest.mark.asyncio
    async def test_get_positions_mock_all(self):
        """测试获取所有持仓"""
        tool = GetPositionsToolMock()
        result = await tool.execute()

        assert result.success is True
        assert isinstance(result.data, list)
        assert len(result.data) > 0
        assert all(isinstance(p, Position) for p in result.data)

    @pytest.mark.asyncio
    async def test_get_positions_mock_filter(self):
        """测试过滤持仓"""
        tool = GetPositionsToolMock()
        result = await tool.execute(symbol="600519")

        assert result.success is True
        positions = result.data
        assert all(p.symbol == "600519" for p in positions)

    @pytest.mark.asyncio
    async def test_get_positions_mock_all(self):
        """测试获取所有持仓"""
        tool = GetPositionsToolMock()
        result = await tool.execute()

        assert result.success is True
        assert isinstance(result.data, list)
        assert len(result.data) > 0
        assert all(isinstance(p, Position) for p in result.data)

    @pytest.mark.asyncio
    async def test_get_positions_mock_filter_nonexistent(self):
        """测试过滤不存在的股票"""
        tool = GetPositionsToolMock()
        result = await tool.execute(symbol="999999")

        assert result.success is True
        assert result.data == []

    @pytest.mark.asyncio
    async def test_get_positions_with_account(self):
        """测试使用账户对象获取持仓"""
        from simulation.account import Account

        account = Account(initial_cash=100000)
        # 账户刚创建时无持仓
        tool = GetPositionsTool(account=account)
        result = await tool.execute()

        assert result.success is True
        assert isinstance(result.data, list)
        assert len(result.data) == 0

    @pytest.mark.asyncio
    async def test_get_positions_mock_positions_completeness(self):
        """测试模拟持仓数据完整性"""
        tool = GetPositionsToolMock()
        result = await tool.execute()

        positions = result.data
        for pos in positions:
            assert hasattr(pos, 'symbol')
            assert hasattr(pos, 'shares')
            assert hasattr(pos, 'avg_cost')
            assert hasattr(pos, 'current_price')
            assert hasattr(pos, 'opened_at')
            assert pos.shares > 0
            assert pos.avg_cost > 0
            assert pos.current_price > 0

    @pytest.mark.asyncio
    async def test_get_positions_mock_specific_symbol(self):
        """测试获取指定股票的模拟持仓"""
        tool = GetPositionsToolMock()
        result1 = await tool.execute(symbol="600519")
        result2 = await tool.execute(symbol="000001")

        assert result1.success is True
        assert result2.success is True
        assert len(result1.data) == 1
        assert len(result2.data) == 1
        assert result1.data[0].symbol == "600519"
        assert result2.data[0].symbol == "000001"

    @pytest.mark.asyncio
    async def test_get_positions_tool_initialization(self):
        """测试工具初始化"""
        tool1 = GetPositionsTool()
        assert tool1.account is None

        from simulation.account import Account
        account = Account(initial_cash=100000)
        tool2 = GetPositionsTool(account=account)
        assert tool2.account is account

    @pytest.mark.asyncio
    async def test_get_positions_with_account_and_filter(self):
        """测试使用账户对象并过滤持仓"""
        from simulation.account import Account

        account = Account(initial_cash=100000)
        tool = GetPositionsTool(account=account)
        result = await tool.execute(symbol="600519")

        assert result.success is True
        assert isinstance(result.data, list)
        # 空账户，过滤后仍为空
        assert len(result.data) == 0


# ============================================
# 工具装饰器测试
# ============================================

class TestToolDecorator:
    """测试工具装饰器"""

    def test_register_tool_decorator(self):
        """测试 @register_tool 装饰器"""
        executor = ToolExecutor()

        @register_tool(executor)
        class DecoratedTool(Tool):
            @property
            def name(self) -> str:
                return "decorated_tool"

            @property
            def description(self) -> str:
                return "装饰器注册的工具"

            @property
            def parameters_schema(self) -> dict:
                return {"type": "object", "properties": {}}

            async def _execute(self, **kwargs) -> str:
                return "结果"

        assert "decorated_tool" in executor.list_tools()
