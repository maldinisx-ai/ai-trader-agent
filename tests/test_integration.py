# -*- coding: utf-8 -*-
"""
集成测试

端到端集成测试，验证完整交易流程。
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.schemas import (
    AgentContext,
    Decision,
    Order,
    QuoteData,
    Position,
    SurvivalLevel,
    MarketRegime,
    PolicyResult,
    OrderSide,
    OrderType,
    Trade,
    MatchResult,
)
from core.survival_rules import SurvivalRules
from core.policy_engine import PolicyEngine
from simulation.account import Account
from simulation.matcher import Matcher


# ============================================
# Fixtures - 集成测试专有
# ============================================

@pytest.fixture
def temp_db():
    """临时数据库文件（每个测试独立）"""
    # 使用UUID确保每个测试使用独立的数据库
    temp_dir = Path("D:/projects/ai-trader-agent/data/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    db_path = temp_dir / f"test_{uuid.uuid4().hex}.db"
    yield str(db_path)
    # 清理
    if db_path.exists():
        try:
            db_path.unlink()
        except:
            pass  # Windows 文件锁定可能失败


@pytest.fixture
def integration_account(temp_db):
    """集成测试账户"""
    return Account(initial_cash=1_000_000.0, db_path=temp_db)


@pytest.fixture
def integration_matcher():
    """集成测试撮合引擎"""
    return Matcher()


@pytest.fixture
def sample_quote_data():
    """示例行情数据"""
    return QuoteData(
        symbol="600519",
        name="贵州茅台",
        price=1680.00,
        change=1.2,
        volume=1234567,
        amount=2100000000.0,
        high=1695.00,
        low=1675.00,
        open=1680.00,
        upper_limit=1688.00,
        lower_limit=1672.00,
        is_suspended=False,
    )


@pytest.fixture
def policy_engine():
    """风控引擎"""
    return PolicyEngine(
        cash=1_000_000.0,
        daily_pnl_ratio=0.0,
        circuit_triggered=False,
    )


@pytest.fixture
def survival_rules():
    """生存规则"""
    return SurvivalRules(initial_cash=1_000_000.0)


# ============================================
# 集成测试：完整交易流程
# ============================================

@pytest.mark.asyncio
async def test_buy_order_full_flow(
    integration_account,
    integration_matcher,
    policy_engine,
    sample_quote_data,
):
    """
    完整买入流程测试:
    1. 创建买入订单
    2. 风控检查通过
    3. 撮合引擎撮合
    4. 更新账户（原子性）
    5. 验证持仓和资金
    """
    # 步骤1: 更新撮合引擎的行情数据
    integration_matcher.update_quote(sample_quote_data)

    # 步骤2: 创建买入订单
    order = Order(
        order_id="TEST001",
        symbol="600519",
        side=OrderSide.BUY,
        quantity=100,
        price=1680.00,
        order_type=OrderType.MARKET,
    )

    # 步骤3: 风控检查
    policy_result = policy_engine.validate_order(order, quote=sample_quote_data)
    assert policy_result.allowed, "风控应该通过"

    # 步骤4: 撮合
    match_result = await integration_matcher.match(order)
    assert match_result.fully_filled, "订单应该完全成交"

    # 步骤5: 更新账户
    success = integration_account.update_from_trade(match_result)
    assert success, "账户更新应该成功"

    # 步骤6: 验证结果
    assert integration_account.cash < 1_000_000.0, "现金应该减少"
    positions = integration_account.get_positions()
    assert len(positions) == 1, "应该有持仓"
    assert positions[0].symbol == "600519"
    assert positions[0].shares == 100


@pytest.mark.asyncio
async def test_sell_order_with_t1_rule(
    integration_account,
    integration_matcher,
    sample_quote_data,
):
    """
    T+1 规则测试:
    1. 当日买入股票
    2. 当日卖出应该被拒绝
    3. 次日卖出应该成功
    """
    # 更新行情数据
    integration_matcher.update_quote(sample_quote_data)

    # 步骤1: 买入股票
    buy_order = Order(
        order_id="BUY001",
        symbol="600519",
        side=OrderSide.BUY,
        quantity=100,
        price=1680.00,
        order_type=OrderType.MARKET,
    )

    buy_match = await integration_matcher.match(buy_order)
    integration_account.update_from_trade(buy_match)

    # 记录买入（用于T+1规则）
    integration_matcher.holding_tracker.record_buy("600519")

    # 步骤2: 当日尝试卖出（应该被拒绝）
    sell_order = Order(
        order_id="SELL001",
        symbol="600519",
        side=OrderSide.SELL,
        quantity=100,
        price=1690.00,
        order_type=OrderType.MARKET,
    )

    sell_match = await integration_matcher.match(sell_order)

    # T+1 规则应该拒绝
    assert not sell_match.fully_filled, "T+1 规则应该拒绝当日卖出"
    assert "T+1" in sell_match.reason


@pytest.mark.asyncio
async def test_complete_trading_round_trip(
    integration_account,
    integration_matcher,
    sample_quote_data,
):
    """
    完整交易往返测试:
    1. 买入 100 股
    2. 持仓检查
    3. 次日卖出
    4. 计算盈亏
    5. 验证手续费
    """
    initial_cash = integration_account.cash

    # 更新行情数据
    integration_matcher.update_quote(sample_quote_data)

    # 步骤1: 买入
    buy_order = Order(
        order_id="RT_BUY001",
        symbol="600519",
        side=OrderSide.BUY,
        quantity=100,
        price=1680.00,
        order_type=OrderType.MARKET,
    )

    buy_match = await integration_matcher.match(buy_order)
    integration_account.update_from_trade(buy_match)

    # 记录买入（用于T+1规则）
    integration_matcher.holding_tracker.record_buy("600519")

    # 步骤2: 验证持仓
    positions = integration_account.get_positions()
    assert len(positions) == 1
    assert positions[0].shares == 100

    # 步骤3: 模拟次日卖出
    with patch('simulation.matcher.date') as mock_date:
        # 模拟次日
        tomorrow = datetime.now().date() + timedelta(days=1)
        mock_date.today.return_value = tomorrow
        mock_date.side_effect = lambda *args, **kw: datetime.now().date()

        # 更新行情价格为卖出价
        sell_quote = QuoteData(
            symbol="600519",
            name="贵州茅台",
            price=1690.00,  # 上涨10元
            change=0.6,
            volume=1000000,
            amount=1690000000.0,
        )
        integration_matcher.update_quote(sell_quote)

        sell_order = Order(
            order_id="RT_SELL001",
            symbol="600519",
            side=OrderSide.SELL,
            quantity=100,
            price=1690.00,
            order_type=OrderType.MARKET,
        )

        sell_match = await integration_matcher.match(sell_order)
        assert sell_match.fully_filled, "次日卖出应该成功"
        integration_account.update_from_trade(sell_match)

    # 步骤4: 验证结果
    final_cash = integration_account.cash
    pnl = final_cash - initial_cash

    # 验证交易往返完成
    expected_gross = (1690.00 - 1680.00) * 100  # 1000元
    assert pnl < expected_gross, "净利润应该低于毛利润（扣除手续费）"
    assert pnl > 0, "应该仍有净利润（上涨10元足够覆盖手续费）"


# ============================================
# 集成测试：风控拒绝场景
# ============================================

@pytest.mark.asyncio
async def test_insufficient_fund_rejection(
    integration_account,
    policy_engine,
    sample_quote_data,
):
    """
    资金不足拒绝测试
    """
    order = Order(
        order_id="TEST001",
        symbol="600519",
        side=OrderSide.BUY,
        quantity=10000,  # 10000股需要约1680万
        price=1680.00,
        order_type=OrderType.MARKET,
    )

    result = policy_engine.validate_order(order, quote=sample_quote_data)

    assert not result.allowed
    assert result.priority.value == 0  # P0 优先级
    assert "资金不足" in result.reason


@pytest.mark.asyncio
async def test_limit_up_buy_rejection(
    integration_matcher,
    sample_quote_data,
):
    """
    涨停买入拒绝测试
    """
    # 创建涨停价订单
    limit_up_quote = QuoteData(
        symbol="600519",
        name="贵州茅台",
        price=1688.00,  # 涨停价
        change=10.0,
        volume=1234567,
        amount=2100000000.0,
        upper_limit=1688.00,
        lower_limit=1672.00,
    )

    integration_matcher.update_quote(limit_up_quote)

    order = Order(
        order_id="TEST001",
        symbol="600519",
        side=OrderSide.BUY,
        quantity=100,
        price=1689.00,  # 高于涨停价
        order_type=OrderType.LIMIT,
    )

    match_result = await integration_matcher.match(order)

    assert not match_result.fully_filled
    assert "涨停" in match_result.reason


@pytest.mark.asyncio
async def test_blacklist_rejection(
    policy_engine,
):
    """
    黑名单股票拒绝测试
    """
    # ST 股在黑名单中
    order = Order(
        order_id="TEST001",
        symbol="ST0001",
        side=OrderSide.BUY,
        quantity=100,
        price=10.00,
        order_type=OrderType.MARKET,
    )

    quote = QuoteData(
        symbol="ST0001",
        name="ST股票",
        price=10.00,
        change=0.0,
        volume=100000,
        amount=1000000.0,
    )

    result = policy_engine.validate_order(order, quote=quote)

    assert not result.allowed
    assert "黑名单" in result.reason


# ============================================
# 集成测试：生存等级切换
# ============================================

def test_survival_level_upgrade(survival_rules):
    """
    生存等级升级测试:
    1. 初始状态 normal
    2. 回撤达到12%
    3. 验证切换到 low_compute
    4. 验证交易频率和最大仓位降低
    """
    # 步骤1: 获取初始状态
    initial_state = survival_rules.get_current_state()
    assert initial_state.level == SurvivalLevel.NORMAL
    assert initial_state.max_position == 0.30

    # 步骤2: 模拟回撤达到12%（当前总资产88万）
    current_value = 880_000.0
    survival_rules.update_level(current_value)

    # 步骤3: 验证升级
    new_state = survival_rules.get_current_state()
    assert new_state.level == SurvivalLevel.LOW_COMPUTE
    assert new_state.drawdown >= 0.10
    assert new_state.max_position == 0.20  # 降低到20%
    assert new_state.trading_interval == 300  # 5分钟


def test_survival_level_critical(survival_rules):
    """
    生存等级危急状态测试:
    1. 回撤达到25%
    2. 验证切换到 critical
    3. 验证最大仓位降低到10%
    """
    # 回撤25%
    survival_rules.update_level(750_000.0)

    state = survival_rules.get_current_state()
    assert state.level == SurvivalLevel.CRITICAL
    assert state.max_position == 0.10
    assert state.trading_interval == 600  # 10分钟


# ============================================
# 集成测试：错误恢复
# ============================================

@pytest.mark.asyncio
async def test_invalid_price_rejection(
    integration_account,
    integration_matcher,
    sample_quote_data,
):
    """
    无效价格拒绝测试
    """
    integration_matcher.update_quote(sample_quote_data)
    initial_cash = integration_account.cash

    # 创建一个会导致验证错误的订单（价格太低无法成交）
    order = Order(
        order_id="TEST001",
        symbol="600519",
        side=OrderSide.BUY,
        quantity=100,
        price=1000.00,  # 远低于当前价
        order_type=OrderType.LIMIT,
    )

    # 撮合应该失败
    match_result = await integration_matcher.match(order)

    # 账户不应该更新
    assert not match_result.fully_filled
    assert integration_account.cash == initial_cash


@pytest.mark.asyncio
async def test_concurrent_order_handling(
    integration_account,
    integration_matcher,
    sample_quote_data,
):
    """
    并发订单处理测试
    """
    integration_matcher.update_quote(sample_quote_data)

    orders = [
        Order(
            order_id=f"CON{i:03d}",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1680.00,
            order_type=OrderType.MARKET,
        )
        for i in range(5)
    ]

    # 并发撮合
    tasks = [integration_matcher.match(order) for order in orders]
    results = await asyncio.gather(*tasks)

    # 所有订单都应该成功
    for result in results:
        assert result.fully_filled

    # 更新账户
    for result in results:
        integration_account.update_from_trade(result)

    # 验证持仓
    positions = integration_account.get_positions()
    assert len(positions) == 1
    assert positions[0].shares == 500


# ============================================
# 集成测试：数据一致性
# ============================================

def test_account_persistence(temp_db):
    """
    账户持久化测试
    """
    # 创建账户并交易
    account1 = Account(initial_cash=1_000_000.0, db_path=temp_db)

    # 获取初始状态
    initial_cash1 = account1.cash

    # 模拟交易
    match_result = MatchResult(
        order=Order(
            order_id="TEST001",
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1680.00,
            order_type=OrderType.MARKET,
        ),
        filled_quantity=100,
        filled_price=1680.00,
        fully_filled=True,
        reason="成交",
    )

    account1.update_from_trade(match_result)

    # 关闭账户
    del account1

    # 重新加载账户
    account2 = Account(initial_cash=1_000_000.0, db_path=temp_db)

    # 验证数据一致
    assert account2.cash < initial_cash1
    positions = account2.get_positions()
    assert len(positions) == 1
    assert positions[0].shares == 100


# ============================================
# 性能测试
# ============================================

@pytest.mark.asyncio
async def test_large_order_performance(
    integration_matcher,
):
    """
    大订单性能测试
    """
    large_quote = QuoteData(
        symbol="600519",
        name="贵州茅台",
        price=1680.00,
        change=0.0,
        volume=123456789,
        amount=210000000000.0,
    )

    integration_matcher.update_quote(large_quote)

    large_order = Order(
        order_id="LARGE001",
        symbol="600519",
        side=OrderSide.BUY,
        quantity=10000,  # 大单
        price=1680.00,
        order_type=OrderType.MARKET,
    )

    import time
    start_time = time.time()

    # 执行撮合
    match_result = await integration_matcher.match(large_order)

    end_time = time.time()
    execution_time = end_time - start_time

    # 验证性能
    assert execution_time < 1.0, "大单处理应该在1秒内完成"
    assert match_result.fully_filled


# ============================================
# 边界测试
# ============================================

@pytest.mark.asyncio
async def test_limit_order_price_comparison(
    integration_matcher,
):
    """
    限价单价格比较测试
    """
    quote = QuoteData(
        symbol="600519",
        name="贵州茅台",
        price=1680.00,
        change=0.0,
        volume=1000000,
        amount=1680000000.0,
    )

    integration_matcher.update_quote(quote)

    # 买入：限价高于当前价，应该成交
    buy_order = Order(
        order_id="TEST001",
        symbol="600519",
        side=OrderSide.BUY,
        quantity=100,
        price=1700.00,  # 高于当前价
        order_type=OrderType.LIMIT,
    )

    result = await integration_matcher.match(buy_order)
    assert result.fully_filled

    # 买入：限价低于当前价，不应成交
    buy_order_low = Order(
        order_id="TEST002",
        symbol="600519",
        side=OrderSide.BUY,
        quantity=100,
        price=1600.00,  # 低于当前价
        order_type=OrderType.LIMIT,
    )

    result = await integration_matcher.match(buy_order_low)
    assert not result.fully_filled

    # 卖出：限价低于当前价，应该成交
    # 先设置持仓
    integration_matcher.holding_tracker.holdings_since["600519"] = (
        datetime.now().date() - timedelta(days=1)
    )

    sell_order = Order(
        order_id="TEST003",
        symbol="600519",
        side=OrderSide.SELL,
        quantity=100,
        price=1650.00,  # 低于当前价
        order_type=OrderType.LIMIT,
    )

    result = await integration_matcher.match(sell_order)
    assert result.fully_filled


@pytest.mark.asyncio
async def test_suspended_stock_rejection(
    integration_matcher,
    sample_quote_data,
):
    """
    停牌股票拒绝测试
    """
    # 设置停牌
    suspended_quote = QuoteData(
        symbol="600519",
        name="贵州茅台",
        price=1680.00,
        change=0.0,
        volume=0,
        amount=0.0,
        is_suspended=True,
    )

    integration_matcher.update_quote(suspended_quote)

    order = Order(
        order_id="TEST001",
        symbol="600519",
        side=OrderSide.BUY,
        quantity=100,
        price=1680.00,
        order_type=OrderType.MARKET,
    )

    match_result = await integration_matcher.match(order)

    assert not match_result.fully_filled
    assert "停牌" in match_result.reason