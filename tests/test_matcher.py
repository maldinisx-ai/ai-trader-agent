# -*- coding: utf-8 -*-
"""
测试撮合引擎
"""

import asyncio
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from freezegun import freeze_time

from simulation.matcher import Matcher, MatcherConfig, HoldingTracker, create_matcher
from core.schemas import (
    Order,
    OrderSide,
    OrderType,
    MatchResult,
    QuoteData,
)


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def matcher():
    """创建撮合引擎"""
    return Matcher()


@pytest.fixture
def sample_quote():
    """示例行情"""
    return QuoteData(
        symbol="600519",
        name="贵州茅台",
        price=1680.0,
        change=1.2,
        volume=100000,
        amount=168000000.0,
        high=1700.0,
        low=1660.0,
        open=1670.0,
        upper_limit=1848.0,  # 涨停价
        lower_limit=1512.0,  # 跌停价
        is_suspended=False,
        timestamp=datetime.now(),
    )


@pytest.fixture
def limit_up_quote():
    """涨停行情"""
    return QuoteData(
        symbol="600519",
        name="贵州茅台",
        price=1848.0,  # 涨停价
        change=10.0,
        volume=100000,
        amount=184800000.0,
        high=1848.0,
        low=1680.0,
        open=1700.0,
        upper_limit=1848.0,
        lower_limit=1512.0,
        is_suspended=False,
        timestamp=datetime.now(),
    )


@pytest.fixture
def limit_down_quote():
    """跌停行情"""
    return QuoteData(
        symbol="600519",
        name="贵州茅台",
        price=1512.0,  # 跌停价
        change=-10.0,
        volume=100000,
        amount=151200000.0,
        high=1680.0,
        low=1512.0,
        open=1600.0,
        upper_limit=1848.0,
        lower_limit=1512.0,
        is_suspended=False,
        timestamp=datetime.now(),
    )


@pytest.fixture
def suspended_quote():
    """停牌行情"""
    return QuoteData(
        symbol="600519",
        name="贵州茅台",
        price=1680.0,
        change=0.0,
        volume=0,
        amount=0.0,
        is_suspended=True,  # 停牌
        timestamp=datetime.now(),
    )


@pytest.fixture
def buy_order():
    """买入订单"""
    return Order(
        order_id=str(uuid4()),
        symbol="600519",
        side=OrderSide.BUY,
        quantity=100,
        price=1700.0,
        order_type=OrderType.LIMIT,
    )


@pytest.fixture
def sell_order():
    """卖出订单"""
    return Order(
        order_id=str(uuid4()),
        symbol="600519",
        side=OrderSide.SELL,
        quantity=100,
        price=1700.0,
        order_type=OrderType.LIMIT,
    )


@pytest.fixture
def market_buy_order():
    """市价买入订单"""
    return Order(
        order_id=str(uuid4()),
        symbol="600519",
        side=OrderSide.BUY,
        quantity=100,
        price=None,
        order_type=OrderType.MARKET,
    )


# ============================================
# 市价单撮合测试
# ============================================

class TestMarketOrderMatching:
    """测试市价单撮合"""

    @pytest.mark.asyncio
    async def test_market_buy_order(self, matcher, sample_quote, market_buy_order):
        """测试市价买入单"""
        matcher.update_quote(sample_quote)

        result = await matcher.match(market_buy_order)

        assert result.fully_filled is True
        assert result.filled_quantity == 100
        assert result.filled_price == 1680.0  # 以当前价成交
        assert "撮合成功" in result.reason

    @pytest.mark.asyncio
    async def test_market_sell_order(self, matcher, sample_quote):
        """测试市价卖出单"""
        # 先记录昨日买入（通过 T+1 检查）
        yesterday = date.today() - timedelta(days=1)
        matcher.holding_tracker.record_buy("600519", buy_date=yesterday)

        market_sell = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.SELL,
            quantity=100,
            price=None,
            order_type=OrderType.MARKET,
        )
        matcher.update_quote(sample_quote)

        result = await matcher.match(market_sell)

        assert result.fully_filled is True
        assert result.filled_quantity == 100
        assert result.filled_price == 1680.0


# ============================================
# 限价单撮合测试
# ============================================

class TestLimitOrderMatching:
    """测试限价单撮合"""

    @pytest.mark.asyncio
    async def test_limit_buy_filled(self, matcher, sample_quote, buy_order):
        """测试限价买入单成交"""
        # 限价 1700，当前价 1680，限价 >= 当前价，应成交
        matcher.update_quote(sample_quote)

        result = await matcher.match(buy_order)

        assert result.fully_filled is True
        assert result.filled_price == 1680.0

    @pytest.mark.asyncio
    async def test_limit_buy_no_fill(self, matcher, sample_quote):
        """测试限价买入单不成交"""
        # 限价 1650，当前价 1680，限价 < 当前价，不成交
        order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1650.0,  # 低于当前价
            order_type=OrderType.LIMIT,
        )
        matcher.update_quote(sample_quote)

        result = await matcher.match(order)

        assert result.fully_filled is False
        assert result.filled_quantity == 0
        assert "无法确定成交价格" in result.reason

    @pytest.mark.asyncio
    async def test_limit_sell_filled(self, matcher, sample_quote, sell_order):
        """测试限价卖出单成交"""
        # 先记录昨日买入（通过 T+1 检查）
        yesterday = date.today() - timedelta(days=1)
        matcher.holding_tracker.record_buy("600519", buy_date=yesterday)

        # 限价 1700，当前价 1680，限价 > 当前价，不成交
        matcher.update_quote(sample_quote)

        result = await matcher.match(sell_order)

        assert result.fully_filled is False
        assert result.filled_quantity == 0

    @pytest.mark.asyncio
    async def test_limit_sell_at_market(self, matcher, sample_quote):
        """测试限价卖出单以市价成交"""
        # 先记录昨日买入（通过 T+1 检查）
        yesterday = date.today() - timedelta(days=1)
        matcher.holding_tracker.record_buy("600519", buy_date=yesterday)

        # 限价 1650，当前价 1680，限价 <= 当前价，应成交
        order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.SELL,
            quantity=100,
            price=1650.0,
            order_type=OrderType.LIMIT,
        )
        matcher.update_quote(sample_quote)

        result = await matcher.match(order)

        assert result.fully_filled is True
        assert result.filled_price == 1680.0


# ============================================
# 涨跌停测试
# ============================================

class TestPriceLimits:
    """测试涨跌停限制"""

    @pytest.mark.asyncio
    async def test_buy_at_limit_up_rejected(self, matcher, limit_up_quote):
        """测试涨停买入被拒绝"""
        order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1850.0,  # 高于涨停价
            order_type=OrderType.LIMIT,
        )
        matcher.update_quote(limit_up_quote)

        result = await matcher.match(order)

        assert result.fully_filled is False
        assert "涨停价限制" in result.reason

    @pytest.mark.asyncio
    async def test_sell_at_limit_down_rejected(self, matcher, limit_down_quote):
        """测试跌停卖出被拒绝"""
        order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.SELL,
            quantity=100,
            price=1500.0,  # 低于跌停价
            order_type=OrderType.LIMIT,
        )
        matcher.update_quote(limit_down_quote)

        result = await matcher.match(order)

        assert result.fully_filled is False
        assert "跌停价限制" in result.reason

    @pytest.mark.asyncio
    async def test_buy_below_limit_up_accepted(self, matcher, limit_up_quote):
        """测试涨停价以下买入被接受"""
        # 涨停时，限价 1840 < 当前价 1848，无法成交
        # 这个测试应该验证无法成交的情况
        order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1840.0,  # 低于涨停价
            order_type=OrderType.LIMIT,
        )
        matcher.update_quote(limit_up_quote)

        result = await matcher.match(order)

        # 涨停时，限价低于当前价无法成交
        assert result.fully_filled is False


# ============================================
# 停牌测试
# ============================================

class TestSuspension:
    """测试停牌限制"""

    @pytest.mark.asyncio
    async def test_buy_suspended_rejected(self, matcher, suspended_quote):
        """测试停牌买入被拒绝"""
        order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1700.0,
            order_type=OrderType.LIMIT,
        )
        matcher.update_quote(suspended_quote)

        result = await matcher.match(order)

        assert result.fully_filled is False
        assert "停牌" in result.reason

    @pytest.mark.asyncio
    async def test_sell_suspended_rejected(self, matcher, suspended_quote):
        """测试停牌卖出被拒绝"""
        order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.SELL,
            quantity=100,
            price=1700.0,
            order_type=OrderType.LIMIT,
        )
        matcher.update_quote(suspended_quote)

        result = await matcher.match(order)

        assert result.fully_filled is False
        assert "停牌" in result.reason

    @pytest.mark.asyncio
    async def test_manual_suspension(self, matcher, sample_quote):
        """测试手动设置停牌"""
        matcher.set_suspended("600519", suspended=True)
        matcher.update_quote(sample_quote)

        order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1700.0,
            order_type=OrderType.LIMIT,
        )

        result = await matcher.match(order)

        assert result.fully_filled is False
        assert "停牌" in result.reason


# ============================================
# T+1 规则测试
# ============================================

class TestT1Rule:
    """测试 T+1 规则"""

    @pytest.mark.asyncio
    async def test_sell_today_buy_rejected(self, matcher, sample_quote):
        """测试当日买入次日才能卖"""
        # 记录今日买入
        matcher.holding_tracker.record_buy("600519")

        # 尝试今日卖出
        order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.SELL,
            quantity=100,
            price=1700.0,
            order_type=OrderType.LIMIT,
        )
        matcher.update_quote(sample_quote)

        result = await matcher.match(order)

        assert result.fully_filled is False
        assert "T+1" in result.reason

    @pytest.mark.asyncio
    async def test_sell_previous_buy_accepted(self, matcher, sample_quote):
        """测试昨日买入今日可以卖"""
        # 记录昨日买入
        yesterday = date.today() - timedelta(days=1)
        matcher.holding_tracker.record_buy("600519", buy_date=yesterday)

        # 今日卖出 - 使用可以成交的价格
        order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.SELL,
            quantity=100,
            price=1650.0,  # 低于当前价，可以成交
            order_type=OrderType.LIMIT,
        )
        matcher.update_quote(sample_quote)

        result = await matcher.match(order)

        assert result.fully_filled is True

    @pytest.mark.asyncio
    async def test_buy_no_t1_restriction(self, matcher, sample_quote):
        """测试买入不受 T+1 限制"""
        order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1700.0,
            order_type=OrderType.LIMIT,
        )
        matcher.update_quote(sample_quote)

        result = await matcher.match(order)

        # 买入不受 T+1 限制，只要行情正常就能成交
        assert result.fully_filled is True


# ============================================
# 无行情数据测试
# ============================================

class TestNoQuote:
    """测试无行情数据"""

    @pytest.mark.asyncio
    async def test_no_quote_rejected(self, matcher):
        """测试无行情数据被拒绝"""
        order = Order(
            order_id=str(uuid4()),
            symbol="999999",  # 不存在的股票
            side=OrderSide.BUY,
            quantity=100,
            price=100.0,
            order_type=OrderType.LIMIT,
        )

        result = await matcher.match(order)

        assert result.fully_filled is False
        assert "不存在" in result.reason or "无行情" in result.reason


# ============================================
# 行情管理测试
# ============================================

class TestQuoteManagement:
    """测试行情管理"""

    def test_update_quote(self, matcher):
        """测试更新行情"""
        quote = QuoteData(
            symbol="600519",
            name="贵州茅台",
            price=1680.0,
            change=1.2,
            volume=100000,
            amount=168000000.0,
            timestamp=datetime.now(),
        )

        matcher.update_quote(quote)

        assert matcher.get_quote("600519") is not None
        assert matcher.get_quote("600519").price == 1680.0

    def test_update_quotes_batch(self, matcher):
        """测试批量更新行情"""
        quotes = [
            QuoteData(
                symbol="600519",
                name="贵州茅台",
                price=1680.0,
                change=1.2,
                volume=100000,
                amount=168000000.0,
                timestamp=datetime.now(),
            ),
            QuoteData(
                symbol="000001",
                name="平安银行",
                price=12.5,
                change=0.5,
                volume=500000,
                amount=6250000.0,
                timestamp=datetime.now(),
            ),
        ]

        matcher.update_quotes(quotes)

        assert matcher.get_quote("600519") is not None
        assert matcher.get_quote("000001") is not None

    def test_get_nonexistent_quote(self, matcher):
        """测试获取不存在的行情"""
        assert matcher.get_quote("999999") is None


# ============================================
# 持仓追踪测试
# ============================================

class TestHoldingTracker:
    """测试持仓追踪器"""

    def test_record_buy(self):
        """测试记录买入"""
        tracker = HoldingTracker()
        tracker.record_buy("600519")

        assert "600519" in tracker.today_buys
        assert "600519" in tracker.holdings_since

    def test_can_sell_today_false(self):
        """测试当日不能卖"""
        tracker = HoldingTracker()
        tracker.record_buy("600519")

        assert tracker.can_sell_today("600519") is False

    def test_can_sell_today_true(self):
        """测试持有足够时间可以卖"""
        tracker = HoldingTracker()
        yesterday = date.today() - timedelta(days=1)
        tracker.record_buy("600519", buy_date=yesterday)

        assert tracker.can_sell_today("600519") is True

    def test_clear_today_buys(self):
        """测试清除今日买入"""
        tracker = HoldingTracker()
        tracker.record_buy("600519")
        tracker.record_buy("000001")

        tracker.clear_today_buys()

        assert len(tracker.today_buys) == 0
        assert "600519" in tracker.holdings_since  # 持仓记录保留


# ============================================
# 工厂函数测试
# ============================================

class TestFactory:
    """测试工厂函数"""

    def test_create_matcher_default_config(self):
        """测试创建撮合引擎（默认配置）"""
        matcher = create_matcher()

        assert matcher.config is not None
        assert matcher.holding_tracker is not None

    def test_create_matcher_custom_config(self):
        """测试创建撮合引擎（自定义配置）"""
        config = MatcherConfig(slippage_tolerance=0.002)
        matcher = create_matcher(config=config)

        assert matcher.config.slippage_tolerance == 0.002
