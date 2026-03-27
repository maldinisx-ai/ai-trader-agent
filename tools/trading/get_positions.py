# -*- coding: utf-8 -*-
"""
查询持仓工具
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from core.tool_executor import Tool
from core.schemas import Position


class GetPositionsTool(Tool):
    """
    查询持仓工具

    获取当前所有持仓信息。
    """

    def __init__(self, account=None):
        """
        初始化查询持仓工具

        Args:
            account: 账户对象（可选）
        """
        super().__init__()
        self.account = account

    @property
    def name(self) -> str:
        return "get_positions"

    @property
    def description(self) -> str:
        return "查询当前所有持仓，包括股票代码、数量、成本、当前价格等信息"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码（可选，不指定则返回所有持仓）",
                },
            },
        }

    async def _execute(self, **kwargs) -> List[Position]:
        """
        执行查询持仓

        Args:
            symbol: 股票代码（可选）

        Returns:
            List[Position]: 持仓列表
        """
        symbol_filter = kwargs.get("symbol")

        # 如果有账户对象，从账户获取
        if self.account:
            positions = self.account.get_positions()
            if symbol_filter:
                positions = [p for p in positions if p.symbol == symbol_filter]
            return positions

        # 返回模拟数据
        return self._mock_positions(symbol_filter)

    def _mock_positions(self, symbol_filter: Optional[str] = None) -> List[Position]:
        """生成模拟持仓数据"""
        mock_positions = [
            Position(
                symbol="600519",
                shares=300,
                avg_cost=1650.0,
                current_price=1680.0,
                opened_at=datetime.now(),
            ),
            Position(
                symbol="000001",
                shares=1000,
                avg_cost=12.00,
                current_price=12.50,
                opened_at=datetime.now(),
            ),
        ]

        if symbol_filter:
            mock_positions = [p for p in mock_positions if p.symbol == symbol_filter]

        return mock_positions


class GetPositionsToolMock(GetPositionsTool):
    """
    查询持仓工具（模拟版本，用于测试）
    """

    async def _execute(self, **kwargs) -> List[Position]:
        """返回模拟持仓数据"""
        symbol_filter = kwargs.get("symbol")
        return self._mock_positions(symbol_filter)
