# -*- coding: utf-8 -*-
"""
测试查询持仓工具
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock

# 确保模块被导入以正确收集覆盖率
import tools.trading.get_positions
from core.schemas import Position
from tools.trading.get_positions import GetPositionsTool, GetPositionsToolMock


class TestGetPositionsTool:
    """测试查询持仓工具"""

    def test_init_default(self):
        """测试默认初始化"""
        tool = GetPositionsTool()
        assert tool.name == "get_positions"
        assert tool.account is None

    def test_init_with_account(self):
        """测试带账户初始化"""
        mock_account = Mock()
        tool = GetPositionsTool(account=mock_account)
        assert tool.account == mock_account

    def test_parameters_schema(self):
        """测试参数模式"""
        tool = GetPositionsTool()
        schema = tool.parameters_schema

        assert schema["type"] == "object"
        assert "symbol" in schema["properties"]
        assert schema["properties"]["symbol"]["type"] == "string"
        assert "symbol" not in schema["required"]  # 可选

    @pytest.mark.asyncio
    async def test_execute_all_positions(self):
        """测试获取所有持仓"""
        tool = GetPositionsToolMock()
        positions = await tool.execute()

        assert isinstance(positions, list)
        assert len(positions) == 2

    @pytest.mark.asyncio
    async def test_execute_filter_by_symbol(self):
        """测试按股票代码过滤"""
        tool = GetPositionsToolMock()
        positions = await tool.execute(symbol="600519")

        assert len(positions) == 1
        assert positions[0].symbol == "600519"

    @pytest.mark.asyncio
    async def test_execute_nonexistent_symbol(self):
        """测试获取不存在的股票持仓"""
        tool = GetPositionsToolMock()
        positions = await tool.execute(symbol="999999.SH")

        assert len(positions) == 0

    @pytest.mark.asyncio
    async def test_execute_with_account(self):
        """测试使用账户对象获取持仓"""
        mock_account = Mock()
        mock_positions = [
            Position(
                symbol="600519",
                shares=300,
                avg_cost=1650.0,
                current_price=1680.0,
                opened_at=datetime.now()
            )
        ]
        mock_account.get_positions = Mock(return_value=mock_positions)

        tool = GetPositionsTool(account=mock_account)
        positions = await tool.execute()

        assert len(positions) == 1
        assert positions[0].symbol == "600519"


class TestGetPositionsToolMock:
    """测试模拟查询持仓工具"""

    def test_mock_positions_structure(self):
        """测试模拟持仓数据结构"""
        tool = GetPositionsToolMock()
        positions = tool._mock_positions()

        assert len(positions) == 2
        for pos in positions:
            assert isinstance(pos, Position)
            assert pos.symbol
            assert pos.shares > 0
            assert pos.avg_cost > 0
            assert pos.current_price > 0
            assert isinstance(pos.opened_at, datetime)

    @pytest.mark.asyncio
    async def test_execute_all(self):
        """测试执行获取所有持仓"""
        tool = GetPositionsToolMock()
        positions = await tool.execute()

        assert len(positions) == 2
        assert positions[0].symbol == "600519"
        assert positions[1].symbol == "000001"

    @pytest.mark.asyncio
    async def test_execute_with_filter(self):
        """测试执行带过滤器"""
        tool = GetPositionsToolMock()
        positions = await tool.execute(symbol="000001")

        assert len(positions) == 1
        assert positions[0].symbol == "000001"

    @pytest.mark.asyncio
    async def test_execute_empty_filter(self):
        """测试空过滤器结果"""
        tool = GetPositionsToolMock()
        positions = await tool.execute(symbol="999999.SH")

        assert len(positions) == 0


class TestPosition:
    """测试持仓数据"""

    def test_position_creation(self):
        """测试创建持仓"""
        position = Position(
            symbol="600519",
            shares=300,
            avg_cost=1650.0,
            current_price=1680.0,
            opened_at=datetime.now()
        )

        assert position.symbol == "600519"
        assert position.shares == 300
        assert position.avg_cost == 1650.0
        assert position.current_price == 1680.0

    def test_position_pnl(self):
        """测试持仓盈亏"""
        position = Position(
            symbol="600519",
            shares=300,
            avg_cost=1650.0,
            current_price=1680.0,
            opened_at=datetime.now()
        )

        expected_pnl = (1680.0 - 1650.0) * 300
        assert position.pnl == expected_pnl

    def test_position_pnl_pct(self):
        """测试持仓盈亏百分比"""
        position = Position(
            symbol="600519",
            shares=300,
            avg_cost=1650.0,
            current_price=1680.0,
            opened_at=datetime.now()
        )

        assert position.pnl_pct > 0 0  # 盈利为正

    def test_position_value(self):
        """测试持仓市值"""
        position = Position(
            symbol="600519",
            shares=300,
            avg_cost=1650.0,
            current_price=1680.0,
            opened_at=datetime.now()
        )

        expected_value = 1680.0 * 300
        assert position.value == expected_value

    def test_position_holding_days(self):
        """测试持仓天数"""
        now = datetime.now()
        yesterday = now - datetime.timedelta(days=1)

        position = Position(
            symbol="600519",
            shares=300,
            avg_cost=1650.0,
            current_price=1680.0,
            opened_at=yesterday
        )

        assert position.holding_days >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
