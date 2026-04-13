# -*- coding: utf-8 -*-
"""
Safe Tool Executor 单元测试
"""

import pytest

# 确保模块被导入以正确收集覆盖率
import core.safe_tool_executor
import core.schemas
import core.tool_executor
from core.safe_tool_executor import SafeToolExecutor
from core.schemas import ToolResult, OrderSide
from core.tool_executor import ToolExecutor
from unittest.mock import Mock, AsyncMock, MagicMock


class TestSafeToolExecutor:
    """Safe Tool Executor 测试"""

    @pytest.fixture
    def tool_executor(self):
        """创建模拟的工具执行器"""
        executor = ToolExecutor()

        # 创建模拟工具
        def create_tool(name):
            tool = Mock()
            tool.name = name
            tool.description = f"{name} tool"
            tool.parameters_schema = {}
            tool.call_count = 0
            tool.last_called = None

            async def execute(**kwargs):
                tool.call_count += 1
                return ToolResult(
                    success=True,
                    data={"result": f"{name} executed"},
                    execution_time=0.1,
                )

            tool.execute = execute
            return tool

        # 注册工具
        executor.register(create_tool("get_quote"))
        executor.register(create_tool("place_order"))
        executor.register(create_tool("buy"))
        executor.register(create_tool("sell"))

        return executor

    @pytest.fixture
    def safe_executor(self, tool_executor):
        """创建安全工具执行器"""
        return SafeToolExecutor(
            tool_executor=tool_executor,
            account_info_getter=lambda: 100000,  # 可用资金 10 万
            policy_validator=lambda kwargs: (True, ""),
            quote_getter=lambda symbol: None,
        )

    @pytest.mark.asyncio
    async def test_execute_non_trading_tool_passes(self, safe_executor):
        """测试：非交易工具直接通过"""
        result = await safe_executor.execute("get_quote", symbol="600519")

        assert result.success == True
        assert "get_quote" in result.data["result"]

    @pytest.mark.asyncio
    async def test_insufficient_funds_rejects_buy(self, tool_executor):
        """测试：资金不足拒绝买入"""
        # 可用资金只有 1 万，但需要 14 万
        safe_executor = SafeToolExecutor(
            tool_executor=tool_executor,
            account_info_getter=lambda: 10000,
            policy_validator=lambda kwargs: (True, ""),
            quote_getter=lambda symbol: None,
        )

        result = await safe_executor.execute(
            "buy",
            symbol="600519",
            quantity=100,
            price=1412
        )

        assert result.success == False
        assert "资金不足" in result.error
        assert "需 ¥141200.0" in result.error
        assert "可用 ¥10000" in result.error

    @pytest.mark.asyncio
    async def test_sufficient_funds_allows_buy(self, safe_executor):
        """测试：资金充足允许买入"""
        result = await safe_executor.execute(
            "buy",
            symbol="600519",
            quantity=10,
            price=1000
        )

        assert result.success == True

    @pytest.mark.asyncio
    async def test_policy_rejection(self, tool_executor):
        """测试：风控规则拒绝"""
        safe_executor = SafeToolExecutor(
            tool_executor=tool_executor,
            account_info_getter=lambda: 1000000,
            policy_validator=lambda kwargs: (False, "单笔交易金额超过限制"),
            quote_getter=lambda symbol: None,
        )

        result = await safe_executor.execute(
            "buy",
            symbol="600519",
            quantity=100,
            price=1000
        )

        assert result.success == False
        assert "风控拒绝" in result.error
        assert "单笔交易金额超过限制" in result.error

    @pytest.mark.asyncio
    async def test_limit_up_rejects_buy(self, tool_executor):
        """测试：涨停无法买入"""
        from core.schemas import QuoteData

        # 创建模拟的涨停行情
        def create_limit_up_quote(symbol):
            quote = QuoteData(
                symbol=symbol,
                name="贵州茅台",
                price=1800.0,
                change=10.0,
                volume=1000,
                amount=1800000,
                upper_limit=1800.0,  # 涨停价
                lower_limit=1600.0,
                is_limit_up=True,
            )
            return quote

        safe_executor = SafeToolExecutor(
            tool_executor=tool_executor,
            account_info_getter=lambda: 1000000,
            policy_validator=lambda kwargs: (True, ""),
            quote_getter=create_limit_up_quote,
        )

        result = await safe_executor.execute(
            "place_order",
            symbol="600519",
            quantity=100,
            price=1800,
            side=OrderSide.BUY
        )

        assert result.success == False
        assert "涨停无法买入" in result.error
        assert "600519" in result.error

    @pytest.mark.asyncio
    async def test_limit_down_rejects_sell(self, tool_executor):
        """测试：跌停无法卖出"""
        from core.schemas import QuoteData

        # 创建模拟的跌停行情
        def create_limit_down_quote(symbol):
            quote = QuoteData(
                symbol=symbol,
                name="贵州茅台",
                price=1600.0,
                change=-10.0,
                volume=1000,
                amount=1600000,
                upper_limit=1800.0,
                lower_limit=1600.0,  # 跌停价
                is_limit_down=True,
            )
            return quote

        safe_executor = SafeToolExecutor(
            tool_executor=tool_executor,
            account_info_getter=lambda: 1000000,
            policy_validator=lambda kwargs: (True, ""),
            quote_getter=create_limit_down_quote,
        )

        result = await safe_executor.execute(
            "place_order",
            symbol="600519",
            quantity=100,
            price=1600,
            side=OrderSide.SELL
        )

        assert result.success == False
        assert "跌停无法卖出" in result.error
        assert "600519" in result.error

    @pytest.mark.asyncio
    async def test_normal_price_allows_trading(self, tool_executor):
        """测试：正常价格允许交易"""
        from core.schemas import QuoteData

        # 创建正常的行情
        def create_normal_quote(symbol):
            quote = QuoteData(
                symbol=symbol,
                name="贵州茅台",
                price=1700.0,
                change=0.0,
                volume=1000,
                amount=1700000,
                upper_limit=1800.0,
                lower_limit=1600.0,
                is_limit_up=False,
                is_limit_down=False,
            )
            return quote

        safe_executor = SafeToolExecutor(
            tool_executor=tool_executor,
            account_info_getter=lambda: 1000000,
            policy_validator=lambda kwargs: (True, ""),
            quote_getter=create_normal_quote,
        )

        result = await safe_executor.execute(
            "place_order",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1700
        )

        assert result.success == True

    @pytest.mark.asyncio
    async def test_no_quote_info_allows_trading(self, tool_executor):
        """测试：没有行情信息时允许交易（安全第一）"""
        # quote_getter 返回 None
        safe_executor = SafeToolExecutor(
            tool_executor=tool_executor,
            account_info_getter=lambda: 200000,  # 足够资金
            policy_validator=lambda kwargs: (True, ""),
            quote_getter=lambda symbol: None,
        )

        result = await safe_executor.execute(
            "place_order",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1700
        )

        assert result.success == True

    @pytest.mark.asyncio
    async def test_validation_chain_stops_at_first_error(self, tool_executor):
        """测试：验证链在第一个错误停止"""
        from core.schemas import QuoteData

        # 创建涨停行情
        def create_limit_up_quote(symbol):
            quote = QuoteData(
                symbol=symbol,
                name="测试股票",
                price=1800.0,
                change=10.0,
                volume=1000,
                amount=1800000,
                upper_limit=1800.0,
                is_limit_up=True,
            )
            return quote

        safe_executor = SafeToolExecutor(
            tool_executor=tool_executor,
            account_info_getter=lambda: 1000000,  # 资金充足
            policy_validator=lambda kwargs: (False, "风控拒绝"),  # 风控拒绝
            quote_getter=create_limit_up_quote,
        )

        # 资金充足，但风控拒绝，应该在资金检查后停止
        result = await safe_executor.execute(
            "buy",
            symbol="600519",
            quantity=100,
            price=1800
        )

        # 应该在风控检查时拒绝，不会进行涨停检查
        assert result.success == False
        assert "风控拒绝" in result.error

    @pytest.mark.asyncio
    async def test_sell_tool_skips_fund_check(self, safe_executor):
        """测试：卖出工具跳过资金检查"""
        result = await safe_executor.execute(
            "sell",
            symbol="600519",
            quantity=100,
            price=1412
        )

        # 卖出操作不检查资金
        assert result.success == True

    @pytest.mark.asyncio
    async def test_place_order_with_all_checks_pass(self, tool_executor):
        """测试：place_order 所有检查通过"""
        from core.schemas import QuoteData

        def create_normal_quote(symbol):
            return QuoteData(
                symbol=symbol,
                name="测试股票",
                price=1500.0,
                change=0.0,
                volume=1000,
                amount=1500000,
                upper_limit=1650.0,
                lower_limit=1350.0,
                is_limit_up=False,
                is_limit_down=False,
            )

        safe_executor = SafeToolExecutor(
            tool_executor=tool_executor,
            account_info_getter=lambda: 200000,  # 足够资金
            policy_validator=lambda kwargs: (True, ""),  # 风控通过
            quote_getter=create_normal_quote,
        )

        result = await safe_executor.execute(
            "place_order",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1500
        )

        assert result.success == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])