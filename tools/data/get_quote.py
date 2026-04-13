# -*- coding: utf-8 -*-
"""
获取股票实时行情工具
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

import akshare as ak

from core.tool_executor import Tool
from core.schemas import QuoteData


logger = logging.getLogger(__name__)


class GetQuoteTool(Tool):
    """
    获取股票实时行情

    使用 AkShare 获取 A 股实时行情数据。
    """

    def __init__(self, use_real_data: bool = False):
        """
        初始化行情工具

        Args:
            use_real_data: 是否使用真实数据源
        """
        super().__init__()
        self.use_real_data = use_real_data
        self._data_manager = None

        if use_real_data:
            try:
                from src.data_manager import get_data_manager
                self._data_manager = get_data_manager()
            except ImportError:
                logger.warning("无法导入数据管理器，将使用模拟数据")

    @property
    def name(self) -> str:
        return "get_quote"

    @property
    def description(self) -> str:
        return "获取 A 股股票实时行情数据，包括最新价、涨跌幅、成交量等信息"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码（如 600519 或 000001）",
                },
            },
            "required": ["symbol"],
        }

    async def _execute(self, **kwargs) -> QuoteData:
        """
        执行获取行情

        Args:
            symbol: 股票代码

        Returns:
            QuoteData: 行情数据
        """
        symbol = kwargs.get("symbol", "")

        if not symbol:
            raise ValueError("股票代码不能为空")

        # 使用真实数据
        if self.use_real_data and self._data_manager:
            try:
                return await self._data_manager.get_quote(symbol)
            except Exception as e:
                logger.warning(f"获取真实行情失败，使用模拟数据: {e}")

        # 使用 AkShare 获取实时行情
        try:
            # 在线程池中执行（因为 AkShare 是同步的）
            loop = asyncio.get_event_loop()
            stock_zh_a_spot_em = await loop.run_in_executor(
                None, ak.stock_zh_a_spot_em
            )

            # 查找目标股票
            stock_info = stock_zh_a_spot_em[
                stock_zh_a_spot_em['代码'] == symbol
            ]

            if stock_info.empty:
                raise ValueError(f"未找到股票代码: {symbol}")

            row = stock_info.iloc[0]

            # 构建行情数据
            quote = QuoteData(
                symbol=row['代码'],
                name=row['名称'],
                price=float(row['最新价']),
                change=float(row['涨跌幅']),
                volume=int(row['成交量'] / 100),  # 转换为手
                amount=float(row['成交额']),
                high=float(row['最高']),
                low=float(row['最低']),
                open=float(row['今开']),
                upper_limit=float(row['最高']) if row['涨跌幅'] >= 9.9 else None,
                lower_limit=float(row['最低']) if row['涨跌幅'] <= -9.9 else None,
                is_suspended=False,
                timestamp=datetime.now(),
            )

            return quote

        except Exception as e:
            # 如果实时获取失败，返回模拟数据（用于测试）
            if "模拟" in str(kwargs) or kwargs.get("mock"):
                return self._mock_quote(symbol)
            raise


# 导入 logger
import logging
logger = logging.getLogger(__name__)


class GetQuoteToolMock(GetQuoteTool):
    """
    获取行情工具（模拟版本，用于测试）
    """

    def _mock_quote(self, symbol: str) -> QuoteData:
        """生成模拟行情数据"""
        mock_data = {
            "600519": {"name": "贵州茅台", "price": 1680.00, "change": 1.2},
            "000001": {"name": "平安银行", "price": 12.50, "change": -0.5},
            "000002": {"name": "万科A", "price": 8.80, "change": 0.3},
        }

        if symbol not in mock_data:
            # 生成随机数据
            import random
            base_price = random.uniform(10, 100)
            return QuoteData(
                symbol=symbol,
                name=f"股票{symbol}",
                price=base_price,
                change=random.uniform(-5, 5),
                volume=random.randint(10000, 1000000),
                amount=base_price * random.randint(10000, 1000000),
            )

        data = mock_data[symbol]
        return QuoteData(
            symbol=symbol,
            name=data["name"],
            price=data["price"],
            change=data["change"],
            volume=100000,
            amount=data["price"] * 100000,
            high=data["price"] * 1.05,
            low=data["price"] * 0.95,
        )

    async def _execute(self, **kwargs) -> QuoteData:
        """返回模拟数据"""
        symbol = kwargs.get("symbol", "")
        return self._mock_quote(symbol)
