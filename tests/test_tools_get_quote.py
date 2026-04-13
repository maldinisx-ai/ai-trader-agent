# -*- coding: utf-8 -*-
"""
测试获取行情工具
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
import asyncio

# 确保模块被导入以正确收集覆盖率
import tools.data.get_quote
from core.schemas import QuoteData
from tools.data.get_quote import GetQuoteTool, GetQuoteToolMock


class TestGetQuoteTool:
    """测试获取行情工具"""

    def test_init_default(self):
        """测试默认初始化"""
        tool = GetQuoteTool()
        assert tool.name == "get_quote"
        assert tool.use_real_data is False
        assert tool._data_manager is None

    def test_init_with_real_data(self):
        """测试使用真实数据初始化"""
        tool = GetQuoteTool(use_real_data=True)
        assert tool.use_real_data is True

    def test_parameters_schema(self):
        """测试参数模式"""
        tool = GetQuoteTool()
        schema = tool.parameters_schema

        assert schema["type"] == "object"
        assert "symbol" in schema["properties"]
        assert schema["properties"]["symbol"]["type"] == "string"
        assert "symbol" in schema["required"]

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """测试成功执行"""
        tool = GetQuoteToolMock()
        result = await tool.execute(symbol="600519")

        assert isinstance(result, QuoteData)
        assert result.symbol == "600519"
        assert result.name == "贵州茅台"
        assert result.price == 1680.00

    @pytest.mark.asyncio
    async def test_execute_with_mock_parameter(self):
        """测试使用模拟参数"""
        tool = GetQuoteTool()
        # 真实工具不支持 mock 参数，使用 Mock 版本
        mock_tool = GetQuoteToolMock()
        result = await mock_tool.execute(symbol="999999.SH", _mock=True)

        assert result.symbol == "999999.SH"
        assert "股票" in result.name

    @pytest.mark.asyncio
    async def test_execute_empty_symbol(self):
        """测试空股票代码"""
        tool = GetQuoteTool()
        with pytest.raises(ValueError):
            await tool.execute(symbol="")

    @pytest.mark.asyncio
    async def test_execute_akshare_error(self):
        """测试 AkShare 错误处理"""
        tool = GetQuoteTool()
        with patch('tools.data.get_quote.ak') as mock_akshare:
            import pandas as pd
            mock_akshare.stock_zh_a_spot_em = Mock(side_effect=ImportError())
            with pytest.raises(ValueError):
                await tool.execute(symbol="600519")


class TestGetQuoteToolMock:
    """测试模拟获取行情工具"""

    def test_mock_quote_known_stock(self):
        """测试已知股票的模拟数据"""
        tool = GetQuoteToolMock()
        quote = tool._mock_quote("600519")

        assert quote.symbol == "600519"
        assert quote.name == "贵州茅台"
        assert quote.price == 1680.00
        assert quote.change == 1.2

    def test_mock_quote_different_stock(self):
        """测试不同股票的模拟数据"""
        tool = GetQuoteToolMock()
        quote1 = tool._mock_quote("000001")
        quote2 = tool._mock_quote("000002")

        assert quote1.name == "平安银行"
        assert quote2.name == "万科A"

    def test_mock_quote_structure(self):
        """测试模拟数据结构"""
        tool = GetQuoteToolMock()
        quote = tool._mock_quote("600519")

        assert quote.high > quote.price
        assert quote.low < quote.price
        assert quote.amount > 0
        assert quote.volume > 0
        assert quote.is_suspended is False
        assert isinstance(quote.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_execute_multiple_times(self):
        """测试多次执行"""
        tool = GetQuoteToolMock()

        result1 = await tool.execute(symbol="600519")
        result2 = await tool.execute(symbol="000001")
        result3 = await tool.execute(symbol="600519")

        assert result1.price == result3.price  # 相同股票返回相同价格


class TestQuoteData:
    """测试行情数据"""

    def test_quote_data_properties(self):
        """测试行情数据属性"""
        quote = QuoteData(
            symbol="600519",
            name="贵州茅台",
            price=1680.00,
            change=1.2,
            volume=100000,
            amount=168000000.0,
            high=1700.00,
            low=1660.00,
            open=1670.00,
            upper_limit=1700.00,
            lower_limit=1660.00,
            is_suspended=False,
            timestamp=datetime.now()
        )

        assert quote.symbol == "600519"
        assert quote.name == "贵州茅台"
        assert quote.high == 1700.00
        assert quote.low == 1660.00
        assert quote.change_pct == quote.change / quote.price * 100

    def test_quote_data_default_values(self):
        """测试行情数据默认值"""
        quote = QuoteData(
            symbol="600519",
            name="贵州茅台",
            price=1680.00,
            change=1.2
        )

        assert quote.volume == 0
        assert quote.amount.amount == 0
        assert quote.high is None
        assert quote.low is None
        assert quote.open is None
        assert quote.upper_limit is None
        assert quote.lower_limit is None
        assert quote.is_suspended is False
