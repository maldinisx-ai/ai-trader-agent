# -*- coding: utf-8 -*-
"""
撮合引擎

模拟订单撮合逻辑，处理涨跌停、停牌和 T+1 规则。
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, Optional, List, Set
from decimal import Decimal

from core.schemas import (
    Order,
    OrderSide,
    OrderType,
    MatchResult,
    QuoteData,
)


# ============================================
# 日志配置
# ============================================

logger = logging.getLogger(__name__)


# ============================================
# 撮合配置
# ============================================

@dataclass
class MatcherConfig:
    """撮合配置"""
    # 滑点容忍度（成交价格与委托价格的偏差）
    slippage_tolerance: float = 0.001  # 0.1%

    # 部分成交允许的最小比例
    min_fill_ratio: float = 0.0

    # 价格精度
    price_precision: int = 2


# 默认配置
DEFAULT_CONFIG = MatcherConfig()


# ============================================
# 持仓追踪（用于 T+1 规则）
# ============================================

@dataclass
class HoldingTracker:
    """持仓追踪器，用于 T+1 规则"""

    # 记录当日买入的股票（symbol -> 买入日期）
    today_buys: Dict[str, date] = field(default_factory=dict)

    # 记录持仓的最早买入日期（symbol -> 日期）
    holdings_since: Dict[str, date] = field(default_factory=dict)

    def record_buy(self, symbol: str, buy_date: Optional[date] = None) -> None:
        """记录买入"""
        if buy_date is None:
            buy_date = date.today()

        self.today_buys[symbol] = buy_date

        # 更新持仓起始日期
        if symbol not in self.holdings_since:
            self.holdings_since[symbol] = buy_date

    def can_sell_today(self, symbol: str) -> bool:
        """检查是否可以今日卖出"""
        if symbol not in self.holdings_since:
            return False  # 没有持仓

        # 检查是否是今天之前买入的
        holding_date = self.holdings_since[symbol]
        return holding_date < date.today()

    def clear_today_buys(self) -> None:
        """清除今日买入记录（新交易日调用）"""
        self.today_buys.clear()


# ============================================
# 撮合引擎
# ============================================

class Matcher:
    """
    撮合引擎

    模拟订单撮合逻辑，支持市价单和限价单。
    处理涨跌停、停牌、T+1 等交易规则。
    """

    def __init__(
        self,
        config: Optional[MatcherConfig] = None,
        holding_tracker: Optional[HoldingTracker] = None,
    ):
        """
        初始化撮合引擎

        Args:
            config: 撮合配置
            holding_tracker: 持仓追踪器（用于 T+1 规则）
        """
        self.config = config or DEFAULT_CONFIG
        self.holding_tracker = holding_tracker or HoldingTracker()

        # 模拟行情数据（symbol -> QuoteData）
        self._quotes: Dict[str, QuoteData] = {}

        # 模拟停牌状态（symbol -> bool）
        self._suspended: Set[str] = set()

    # ============================================
    # 行情管理
    # ============================================

    def update_quote(self, quote: QuoteData) -> None:
        """
        更新行情数据

        Args:
            quote: 行情数据
        """
        self._quotes[quote.symbol] = quote

    def update_quotes(self, quotes: List[QuoteData]) -> None:
        """
        批量更新行情数据

        Args:
            quotes: 行情数据列表
        """
        for quote in quotes:
            self.update_quote(quote)

    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        获取行情数据

        Args:
            symbol: 股票代码

        Returns:
            Optional[QuoteData]: 行情数据，不存在返回 None
        """
        return self._quotes.get(symbol)

    # ============================================
    # 停牌管理
    # ============================================

    def set_suspended(self, symbol: str, suspended: bool = True) -> None:
        """
        设置停牌状态

        Args:
            symbol: 股票代码
            suspended: 是否停牌
        """
        if suspended:
            self._suspended.add(symbol)
        else:
            self._suspended.discard(symbol)

    def is_suspended(self, symbol: str) -> bool:
        """
        检查是否停牌

        Args:
            symbol: 股票代码

        Returns:
            bool: 是否停牌
        """
        return symbol in self._suspended

    # ============================================
    # 撮合主流程
    # ============================================

    async def match(self, order: Order) -> MatchResult:
        """
        撮合订单

        Args:
            order: 订单对象

        Returns:
            MatchResult: 撮合结果
        """
        try:
            # 1. 获取实时行情
            quote = self.get_quote(order.symbol)
            if quote is None:
                return self._reject(order, "股票不存在或无行情数据")

            # 2. 检查停牌状态
            if quote.is_suspended or self.is_suspended(order.symbol):
                return self._reject(order, "股票停牌，禁止交易")

            # 3. 检查涨跌停限制
            limit_check = self._check_price_limit(order, quote)
            if limit_check:
                return self._reject(order, limit_check)

            # 4. 检查 T+1 规则
            t1_check = self._check_t1_rule(order)
            if t1_check:
                return self._reject(order, t1_check)

            # 5. 确定成交价格
            fill_price = self._determine_fill_price(order, quote)
            if fill_price is None:
                return self._reject(order, "无法确定成交价格")

            # 6. 计算成交数量
            fill_quantity = self._calculate_fill_quantity(order, quote)

            # 7. 返回撮合结果
            return MatchResult(
                order=order,
                filled_quantity=fill_quantity,
                filled_price=fill_price,
                fully_filled=(fill_quantity == order.quantity),
                reason="撮合成功",
            )

        except Exception as e:
            logger.error(f"[Matcher] 撮合异常: {e}", exc_info=True)
            return self._reject(order, f"撮合异常: {str(e)}")

    def _reject(self, order: Order, reason: str) -> MatchResult:
        """
        拒绝订单

        Args:
            order: 订单对象
            reason: 拒绝原因

        Returns:
            MatchResult: 拒绝结果
        """
        return MatchResult(
            order=order,
            filled_quantity=0,
            filled_price=None,
            fully_filled=False,
            reason=reason,
        )

    # ============================================
    # 检查规则
    # ============================================

    def _check_price_limit(self, order: Order, quote: QuoteData) -> Optional[str]:
        """
        检查涨跌停限制

        Args:
            order: 订单对象
            quote: 行情数据

        Returns:
            Optional[str]: 拒绝原因，None 表示通过检查
        """
        if order.side == OrderSide.BUY:
            # 买入：检查涨停
            if quote.upper_limit and order.price:
                if order.price >= quote.upper_limit:
                    return f"涨停价限制（涨停价 {quote.upper_limit:.2f}）"
        else:
            # 卖出：检查跌停
            if quote.lower_limit and order.price:
                if order.price <= quote.lower_limit:
                    return f"跌停价限制（跌停价 {quote.lower_limit:.2f}）"

        return None

    def _check_t1_rule(self, order: Order) -> Optional[str]:
        """
        检查 T+1 规则

        Args:
            order: 订单对象

        Returns:
            Optional[str]: 拒绝原因，None 表示通过检查
        """
        if order.side == OrderSide.SELL:
            # 卖出：检查是否持有足够时间
            if not self.holding_tracker.can_sell_today(order.symbol):
                return "T+1 规则限制（当日买入次日才能卖）"

        return None

    # ============================================
    # 价格确定
    # ============================================

    def _determine_fill_price(
        self,
        order: Order,
        quote: QuoteData,
    ) -> Optional[float]:
        """
        确定成交价格

        Args:
            order: 订单对象
            quote: 行情数据

        Returns:
            Optional[float]: 成交价格，无法确定返回 None
        """
        if order.order_type == OrderType.MARKET:
            # 市价单：以当前价成交
            return quote.price
        else:
            # 限价单
            if order.price is None:
                return None

            if order.side == OrderSide.BUY:
                # 买入：限价 >= 当前价时，以当前价成交
                if order.price >= quote.price:
                    return quote.price
                # 限价 < 当前价：无法成交
                return None
            else:
                # 卖出：限价 <= 当前价时，以当前价成交
                if order.price <= quote.price:
                    return quote.price
                # 限价 > 当前价：无法成交
                return None

    # ============================================
    # 数量计算
    # ============================================

    def _calculate_fill_quantity(self, order: Order, quote: QuoteData) -> int:
        """
        计算成交数量

        Args:
            order: 订单对象
            quote: 行情数据

        Returns:
            int: 成交数量
        """
        # 简单实现：全部成交
        # 实际中应该考虑流动性、涨跌停等因素
        return order.quantity


# ============================================
# 工厂函数
# ============================================

def create_matcher(
    config: Optional[MatcherConfig] = None,
) -> Matcher:
    """
    创建撮合引擎

    Args:
        config: 撮合配置

    Returns:
        Matcher: 撮合引擎实例
    """
    return Matcher(config=config)
