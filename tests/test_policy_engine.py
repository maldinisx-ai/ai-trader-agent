# -*- coding: utf-8 -*-
"""
测试风控引擎

TDD 流程: RED → GREEN → REFACTOR
"""

import pytest
from datetime import datetime, timedelta

from core.schemas import (
    Order, OrderSide, OrderType, OrderStatus,
    PolicyResult, PolicyPriority, SurvivalLevel,
    QuoteData,
)
from core.policy_engine import PolicyEngine, FundCheckPolicy, CircuitBreakerPolicy
from core.policy_engine import BlacklistPolicy, TradingRulesPolicy, PositionLimitPolicy
from core.policy_engine import CooldownPolicy, DailyLimitPolicy


class TestFundCheckPolicy:
    """测试P0: 资金检查"""

    def test_sufficient_funds_allowed(self):
        """测试资金充足时允许"""
        policy = FundCheckPolicy(cash=1000000.0)
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1000.0,  # 总额10万
            order_type=OrderType.LIMIT,
        )
        result = policy.check(order)
        assert result.allowed is True

    def test_insufficient_funds_rejected(self):
        """测试资金不足时拒绝"""
        policy = FundCheckPolicy(cash=50000.0)
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1000.0,  # 总额10万 > 5万
            order_type=OrderType.LIMIT,
        )
        result = policy.check(order)
        assert result.allowed is False
        assert "资金不足" in result.reason

    def test_sell_order_always_allowed(self):
        """测试卖出订单不需要资金检查"""
        policy = FundCheckPolicy(cash=0.0)
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.SELL,
            quantity=100,
            price=1000.0,
            order_type=OrderType.LIMIT,
        )
        result = policy.check(order)
        assert result.allowed is True


class TestCircuitBreakerPolicy:
    """测试P1: 熔断机制"""

    def test_no_circuit_breaker_allowed(self):
        """测试未触发熔断时允许"""
        policy = CircuitBreakerPolicy(
            daily_pnl_ratio=0.03,  # 3% 亏损
            circuit_triggered=False,
        )
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1000.0,
            order_type=OrderType.LIMIT,
        )
        result = policy.check(order)
        assert result.allowed is True

    def test_circuit_breaker_triggered_rejected(self):
        """测试触发熔断时拒绝"""
        policy = CircuitBreakerPolicy(
            daily_pnl_ratio=0.06,  # 6% 亏损 > 5%
            circuit_triggered=True,
        )
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1000.0,
            order_type=OrderType.LIMIT,
        )
        result = policy.check(order)
        assert result.allowed is False
        assert "熔断" in result.reason


class TestBlacklistPolicy:
    """测试P2: 黑名单"""

    def test_normal_stock_allowed(self):
        """测试正常股票允许"""
        policy = BlacklistPolicy()
        order = Order(
            order_id="ord_001",
            symbol="600519",  # 茅台
            side=OrderSide.BUY,
            quantity=100,
            price=1000.0,
            order_type=OrderType.LIMIT,
        )
        result = policy.check(order)
        assert result.allowed is True

    def test_st_stock_rejected(self):
        """测试ST股票拒绝"""
        policy = BlacklistPolicy()
        order = Order(
            order_id="ord_001",
            symbol="ST600519",  # ST股票
            side=OrderSide.BUY,
            quantity=100,
            price=10.0,
            order_type=OrderType.LIMIT,
        )
        result = policy.check(order)
        assert result.allowed is False
        assert "黑名单" in result.reason


class TestTradingRulesPolicy:
    """测试P3: 交易规则"""

    def test_limit_up_buy_rejected(self):
        """测试涨停买入拒绝"""
        policy = TradingRulesPolicy()
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1690.0,  # 委托价高于涨停价
            order_type=OrderType.LIMIT,
        )
        quote = QuoteData(
            symbol="600519",
            name="贵州茅台",
            price=1680.0,
            change=10.0,
            volume=1000,
            amount=100000.0,
            upper_limit=1680.0,  # 涨停价
        )
        result = policy.check(order, quote=quote)
        assert result.allowed is False
        assert "涨停" in result.reason

    def test_limit_down_sell_rejected(self):
        """测试跌停卖出拒绝"""
        policy = TradingRulesPolicy()
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.SELL,
            quantity=100,
            price=1510.0,  # 委托价低于跌停价
            order_type=OrderType.LIMIT,
        )
        quote = QuoteData(
            symbol="600519",
            name="贵州茅台",
            price=1520.0,
            change=-10.0,
            volume=1000,
            amount=100000.0,
            lower_limit=1520.0,  # 跌停价
        )
        result = policy.check(order, quote=quote)
        assert result.allowed is False
        assert "跌停" in result.reason

    def test_suspended_stock_rejected(self):
        """测试停牌股票拒绝"""
        policy = TradingRulesPolicy()
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1680.0,
            order_type=OrderType.LIMIT,
        )
        quote = QuoteData(
            symbol="600519",
            name="贵州茅台",
            price=1680.0,
            change=0.0,
            volume=0,
            amount=0.0,
            is_suspended=True,  # 停牌
        )
        result = policy.check(order, quote=quote)
        assert result.allowed is False
        assert "停牌" in result.reason


class TestPositionLimitPolicy:
    """测试P4: 仓位限制"""

    def test_within_limit_allowed(self):
        """测试仓位在限制内允许"""
        policy = PositionLimitPolicy(
            max_position_ratio=0.30,
            total_value=1000000.0,
        )
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1000.0,  # 10万，占总资产10%
            order_type=OrderType.LIMIT,
        )
        result = policy.check(order)
        assert result.allowed is True

    def test_exceed_limit_rejected(self):
        """测试超过仓位限制拒绝"""
        policy = PositionLimitPolicy(
            max_position_ratio=0.30,
            total_value=1000000.0,
        )
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=500,
            price=1000.0,  # 50万，占总资产50% > 30%
            order_type=OrderType.LIMIT,
        )
        result = policy.check(order)
        assert result.allowed is False
        assert "仓位" in result.reason


class TestCooldownPolicy:
    """测试P5: 冷却机制"""

    def test_no_cooldown_allowed(self):
        """测试无冷却时允许"""
        policy = CooldownPolicy(cooldown_minutes=30)
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.SELL,  # 与上次交易反向
            quantity=100,
            price=1000.0,
            order_type=OrderType.LIMIT,
        )
        result = policy.check(order, last_trade_time=None, last_trade_side="buy")
        assert result.allowed is True

    def test_in_cooldown_rejected(self):
        """测试冷却期内拒绝"""
        policy = CooldownPolicy(cooldown_minutes=30)
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.SELL,
            quantity=100,
            price=1000.0,
            order_type=OrderType.LIMIT,
        )
        last_trade_time = datetime.now() - timedelta(minutes=15)  # 15分钟前
        result = policy.check(order, last_trade_time=last_trade_time, last_trade_side="buy")
        assert result.allowed is False
        assert "冷却" in result.reason


class TestDailyLimitPolicy:
    """测试P6: 单日限额"""

    def test_under_limit_allowed(self):
        """测试低于单日限额允许"""
        policy = DailyLimitPolicy(max_daily_trades=10)
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1000.0,
            order_type=OrderType.LIMIT,
        )
        result = policy.check(order, daily_trade_count=5)
        assert result.allowed is True

    def test_exceed_limit_rejected(self):
        """测试超过单日限额拒绝"""
        policy = DailyLimitPolicy(max_daily_trades=10)
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1000.0,
            order_type=OrderType.LIMIT,
        )
        result = policy.check(order, daily_trade_count=10)
        assert result.allowed is False
        assert "单日限额" in result.reason


class TestPolicyEngine:
    """测试风控引擎集成"""

    def test_policies_executed_in_priority_order(self):
        """测试策略按优先级顺序执行"""
        engine = PolicyEngine(
            cash=1000000.0,
            max_position_ratio=0.30,
            total_value=1000000.0,
        )

        # P0 资金不足应该最先触发
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=2000,  # 200万 > 100万资金
            price=1000.0,
            order_type=OrderType.LIMIT,
        )
        result = engine.validate_order(order)
        assert result.allowed is False
        assert result.priority == PolicyPriority.P0_FUND_CHECK

    def test_all_policies_pass_allowed(self):
        """测试所有策略通过时允许"""
        engine = PolicyEngine(
            cash=1000000.0,
            max_position_ratio=0.30,
            total_value=1000000.0,
        )

        order = Order(
            order_id="ord_001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1000.0,
            order_type=OrderType.LIMIT,
        )
        result = engine.validate_order(order)
        assert result.allowed is True
