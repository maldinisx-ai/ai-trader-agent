# -*- coding: utf-8 -*-
"""
获取股票列表工具
"""

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime

import akshare as ak

from core.tool_executor import Tool
from core.schemas import ToolResult

logger = logging.getLogger(__name__)


class GetStockListTool(Tool):
    """
    获取股票列表工具

    从数据库或 AkShare 获取所有可交易的股票列表。
    """

    def __init__(self, use_real_data: bool = True):
        """
        初始化股票列表工具

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
                logger.warning("无法导入数据管理器，将使用 AkShare")

    @property
    def name(self) -> str:
        return "get_stock_list"

    @property
    def description(self) -> str:
        return "获取所有可交易的 A 股股票列表，包括股票代码、名称、最新价、涨跌幅等信息"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "market": {
                    "type": "string",
                    "description": "市场类型 (sh/sz/all，默认 all)",
                    "enum": ["sh", "sz", "all"],
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量限制（默认全部返回）",
                },
            },
        }

    async def _execute(self, **kwargs) -> ToolResult:
        """
        执行获取股票列表

        Args:
            market: 市场类型
            limit: 数量限制

        Returns:
            ToolResult: 股票列表结果
        """
        market = kwargs.get("market", "all")
        limit = kwargs.get("limit")

        start_time = datetime.now()

        try:
            # 使用真实数据
            if self.use_real_data and self._data_manager:
                try:
                    stocks = await self._data_manager.get_stock_list(market=market, limit=limit)
                    return ToolResult(
                        success=True,
                        data={"stocks": stocks, "count": len(stocks)},
                        execution_time=(datetime.now() - start_time).total_seconds(),
                    )
                except Exception as e:
                    logger.warning(f"从数据库获取股票列表失败，使用 AkShare: {e}")

            # 使用 AkShare 获取实时数据
            loop = asyncio.get_event_loop()
            stock_zh_a_spot_em = await loop.run_in_executor(
                None, ak.stock_zh_a_spot_em
            )

            # 筛选市场
            if market == "sh":
                stocks_df = stock_zh_a_spot_em[stock_zh_a_spot_em['代码'].str.startswith('6')]
            elif market == "sz":
                stocks_df = stock_zh_a_spot_em[stock_zh_a_spot_em['代码'].str.startswith(('0', '3'))]
            else:
                stocks_df = stock_zh_a_spot_em

            # 应用数量限制
            if limit:
                stocks_df = stocks_df.head(limit)

            # 转换为字典列表
            stocks = []
            for _, row in stocks_df.iterrows():
                stocks.append({
                    "symbol": row['代码'],
                    "name": row['名称'],
                    "price": float(row['最新价']),
                    "change": float(row['涨跌幅']),
                    "volume": int(row['成交量']),
                    "amount": float(row['成交额']),
                    "high": float(row['最高']),
                    "low": float(row['最低']),
                    "open": float(row['今开']),
                })

            return ToolResult(
                success=True,
                data={
                    "stocks": stocks,
                    "count": len(stocks),
                    "market": market,
                },
                execution_time=(datetime.now() - start_time).total_seconds(),
            )

        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=(datetime.now() - start_time).total_seconds(),
            )


class GetStockListToolMock(GetStockListTool):
    """
    获取股票列表工具（模拟版本）
    """

    async def _execute(self, **kwargs) -> ToolResult:
        """返回模拟股票列表"""
        mock_stocks = [
            {"symbol": "600519", "name": "贵州茅台", "price": 1680.00, "change": 1.2, "volume": 100000},
            {"symbol": "000001", "name": "平安银行", "price": 12.50, "change": -0.5, "volume": 500000},
            {"symbol": "000002", "name": "万科A", "price": 8.80, "change": 0.3, "volume": 800000},
            {"symbol": "600036", "name": "招商银行", "price": 32.50, "change": 0.8, "volume": 600000},
            {"symbol": "000858", "name": "五粮液", "price": 145.00, "change": -0.2, "volume": 300000},
            {"symbol": "601318", "name": "中国平安", "price": 42.30, "change": 1.5, "volume": 400000},
            {"symbol": "600276", "name": "恒瑞医药", "price": 45.60, "change": -1.2, "volume": 200000},
            {"symbol": "002594", "name": "比亚迪", "price": 220.00, "change": 2.3, "volume": 350000},
            {"symbol": "601012", "name": "隆基绿能", "price": 25.80, "change": -0.8, "volume": 700000},
            {"symbol": "300750", "name": "宁德时代", "price": 185.00, "change": 1.8, "volume": 450000},
        ]

        limit = kwargs.get("limit")
        if limit:
            mock_stocks = mock_stocks[:limit]

        return ToolResult(
            success=True,
            data={
                "stocks": mock_stocks,
                "count": len(mock_stocks),
                "market": kwargs.get("market", "all"),
            },
            execution_time=0.1,
        )
