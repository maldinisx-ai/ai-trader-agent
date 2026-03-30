# -*- coding: utf-8 -*-
"""
测试获取股票列表工具
"""

import pytest
from unittest.mock import patch, AsyncMock
import asyncio

# 确保模块被导入以正确收集覆盖率
import tools.data.get_stock_list
from core.schemas import ToolResult
from tools.data.get_stock_list import GetStockListTool, GetStockListToolMock


class TestGetStockListTool:
    """测试获取股票列表工具"""

    def test_init_default(self):
        """测试默认初始化"""
        tool = GetStockListTool()
        assert tool.name == "get_stock_list"
        assert tool.use_real_data is True

    def test_init_with_real_data_false(self):
        """测试不使用真实数据初始化"""
        tool = GetStockListTool(use_real_data=False)
        assert tool.use_real_data is False

    def test_parameters_schema(self):
        """测试参数模式"""
        tool = GetStockListTool()
        schema = tool.parameters_schema

        assert schema["type"] == "object"
        assert "market" in schema["properties"]
        assert "limit" in schema["properties"]
        assert schema["properties"]["market"]["enum"] == ["sh", "sz", "all"]

    @pytest.mark.asyncio
    async def test_execute_all_market(self):
        """测试获取所有市场"""
        tool = GetStockListToolMock()
        result = await tool.execute(market="all")

        assert result.success is True
        assert isinstance(result.data, dict)
        assert "stocks" in result.data
        assert "count" in result.data
        assert result.execution_time >= 0

    @pytest.mark.asyncio
    async def test_execute_sh_market(self):
        """测试获取上海市场"""
        tool = GetStockListToolMock()
        result = await tool.execute(market="sh")

        assert result.success is True
        assert result.data["market"] == "sh"
        # 验证股票代码都从6开头
        for stock in result.data["stocks"]:
            assert stock["symbol"].startswith("6")

    @pytest.mark.asyncio
    async def test_execute_sz_market(self):
        """测试获取深圳市场"""
        tool = GetStockListToolMock()
        result = await tool.execute(market="sz")

        assert result.success is True
        assert result.data["market"] == "sz"
        # 验证股票代码都从0或3开头
        for stock in result.data["stocks"]:
            code = stock["symbol"]
            assert code.startswith("0") or code.startswith("3")

    @pytest.mark.asyncio
    async def test_execute_with_limit(self):
        """测试带数量限制"""
        tool = GetStockListToolMock()
        result = await tool.execute(market="all", limit=3)

        assert result.success is True
        assert result.data["count"] == 3
        assert len(result.data["stocks"]) == 3

    @pytest.mark.asyncio
    async def test_execute_with_large_limit(self):
        """测试限制大于可用数量"""
        tool = GetStockListToolMock()
        result = await tool.execute(market="all", limit=1000)

        assert result.success is True
        # 应该返回所有可用股票
        assert result.data["count"] <= 10


class TestGetStockListToolMock:
    """测试模拟获取股票列表工具"""

    def test_mock_data_structure(self):
        """测试模拟数据结构"""
        tool = GetStockListToolMock()
        result = tool._execute_sync()

        assert isinstance(result.data, dict)
        assert "stocks" in result.data
        assert len(result.data["stocks"]) == 10

        # 验证第一个股票
        stock = result.data["stocks"][0]
        assert "symbol" in stock
        assert "name" in stock
        assert "price" in stock
        assert "change" in stock
        assert "volume" in stock

    def test_mock_data_stocks(self):
        """测试模拟数据包含的股票"""
        tool = GetStockListToolMock()
        result = tool._execute_sync()

        stock_symbols = [s["symbol"] for s in result.data["stocks"]]
        assert "600519" in stock_symbols
        assert "000001" in stock_symbols
        assert "000002" in stock_symbols

    def test_mock_execution_time(self):
        """测试模拟执行时间"""
        tool = GetStockListToolMock()
        result = tool._execute_sync()

        assert result.execution_time == 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
