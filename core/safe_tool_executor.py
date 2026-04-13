# -*- coding: utf-8 -*-
"""
安全工具执行器 (Safe Tool Executor)

在执行工具前进行预执行校验，确保资金充足、风控合规、涨跌停等。
"""

import logging
from typing import Optional, Dict, Any

from core.schemas import ToolResult, QuoteData, OrderSide
from core.tool_executor import ToolExecutor

logger = logging.getLogger(__name__)


class SafeToolExecutor:
    """安全的工具执行器，带预执行校验"""

    # 交易工具名称列表
    TRADING_TOOLS = ["place_order", "buy", "sell"]

    def __init__(
        self,
        tool_executor: ToolExecutor,
        account_info_getter,
        policy_validator,
        quote_getter,
    ):
        """
        初始化安全工具执行器

        Args:
            tool_executor: 基础工具执行器
            account_info_getter: 获取账户信息的函数，返回 (available_cash, total_value)
            policy_validator: 风控验证函数，接受 order_kwargs，返回 (approved, reason)
            quote_getter: 获取行情的函数，接受 symbol，返回 QuoteData 或 None
        """
        self.tool_executor = tool_executor
        self.account_info_getter = account_info_getter
        self.policy_validator = policy_validator
        self.quote_getter = quote_getter

    async def execute(
        self,
        tool_name: str,
        **kwargs
    ) -> ToolResult:
        """
        执行工具调用（带校验）

        Args:
            tool_name: 工具名称
            **kwargs: 工具参数

        Returns:
            ToolResult: 执行结果
        """
        # 如果是交易工具，进行预执行校验
        if tool_name in self.TRADING_TOOLS:
            validation_result = self._pre_validate(tool_name, kwargs)
            if validation_result is not None:
                # 校验失败，直接返回
                return validation_result

        # 执行工具
        return await self.tool_executor.execute(tool_name, **kwargs)

    def _pre_validate(
        self,
        tool_name: str,
        kwargs: Dict[str, Any]
    ) -> Optional[ToolResult]:
        """
        预执行校验

        Args:
            tool_name: 工具名称
            kwargs: 工具参数

        Returns:
            Optional[ToolResult]: 校验失败时返回错误结果，通过时返回 None
        """
        # 1. 资金充足性检查（买入操作）
        if tool_name in ["place_order", "buy"]:
            if "quantity" in kwargs and "price" in kwargs:
                quantity = kwargs["quantity"]
                price = kwargs["price"]
                order_value = quantity * price

                # 获取可用资金
                available_cash = self.account_info_getter()

                if order_value > available_cash:
                    logger.warning(
                        f"资金不足：需 ¥{order_value:.2f}，可用 ¥{available_cash:.2f}"
                    )
                    return ToolResult(
                        success=False,
                        error=f"资金不足：需 ¥{order_value:.2f}，可用 ¥{available_cash:.2f}",
                        execution_time=0.0,
                    )

        # 2. 风控规则验证
        approved, reason = self.policy_validator(kwargs)
        if not approved:
            logger.warning(f"风控拒绝：{reason}")
            return ToolResult(
                success=False,
                error=f"风控拒绝：{reason}",
                execution_time=0.0,
            )

        # 3. 涨跌停检查
        if tool_name == "place_order" and "symbol" in kwargs:
            quote = self.quote_getter(kwargs["symbol"])
            if quote is not None:
                side = kwargs.get("side")

                if side == OrderSide.BUY and quote.is_limit_up:
                    logger.warning(f"涨停无法买入：{kwargs['symbol']}")
                    return ToolResult(
                        success=False,
                        error=f"涨停无法买入：{kwargs['symbol']}",
                        execution_time=0.0,
                    )

                if side == OrderSide.SELL and quote.is_limit_down:
                    logger.warning(f"跌停无法卖出：{kwargs['symbol']}")
                    return ToolResult(
                        success=False,
                        error=f"跌停无法卖出：{kwargs['symbol']}",
                        execution_time=0.0,
                    )

        # 所有校验通过
        return None