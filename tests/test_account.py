# -*- coding: utf-8 -*-
"""
测试模拟账户系统
"""

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from simulation.account import Account, FeeConfig
from core.schemas import Order, OrderSide, OrderType, OrderStatus, MatchResult


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def temp_db():
    """临时数据库路径"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # 关闭所有连接后清理
    import gc
    gc.collect()
    try:
        Path(db_path).unlink(missing_ok=True)
    except PermissionError:
        pass  # Windows 上可能无法删除


@pytest.fixture
def account(temp_db):
    """创建测试账户"""
    acc = Account(
        initial_cash=1_000_000.0,
        db_path=temp_db,
    )
    yield acc
    # 清理：关闭数据库连接
    acc.close()


@pytest.fixture
def buy_order():
    """买入订单"""
    return Order(
        order_id=str(uuid4()),
        symbol="600519",
        side=OrderSide.BUY,
        quantity=100,
        price=1680.0,
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
def buy_match_result(buy_order):
    """买入撮合结果"""
    return MatchResult(
        order=buy_order,
        filled_quantity=100,
        filled_price=1680.0,
        fully_filled=True,
        reason="撮合成功",
    )


@pytest.fixture
def sell_match_result(sell_order):
    """卖出撮合结果"""
    return MatchResult(
        order=sell_order,
        filled_quantity=100,
        filled_price=1700.0,
        fully_filled=True,
        reason="撮合成功",
    )


# ============================================
# 账户初始化测试
# ============================================

class TestAccountInit:
    """测试账户初始化"""

    def test_initial_cash(self, account):
        """测试初始资金"""
        assert account.initial_cash == 1_000_000.0
        assert account.cash == 1_000_000.0

    def test_total_value_initial(self, account):
        """测试初始总资产"""
        assert account.total_value == 1_000_000.0
        assert account.position_value == 0.0

    def test_position_value_empty(self, account):
        """测试空仓时持仓市值"""
        assert account.position_value == 0.0
        assert len(account.get_positions()) == 0


# ============================================
# 费用计算测试
# ============================================

class TestFeeCalculation:
    """测试费用计算"""

    def test_calculate_commission_buy(self, account):
        """测试买入佣金计算"""
        amount = 100000  # 10万
        commission = account.calculate_commission(amount, "buy")
        # 10万 * 0.0003 = 30元
        assert abs(commission - 30.0) < 0.01

    def test_calculate_commission_small_amount(self, account):
        """测试小额交易佣金（最低5元）"""
        amount = 1000  # 1千
        commission = account.calculate_commission(amount, "buy")
        # 1千 * 0.0003 = 0.3元 < 5元，取5元
        assert commission == 5.0

    def test_calculate_stamp_duty_buy(self, account):
        """测试买入印花税（不收取）"""
        amount = 100000
        stamp_duty = account.calculate_stamp_duty(amount, "buy")
        assert stamp_duty == 0.0

    def test_calculate_stamp_duty_sell(self, account):
        """测试卖出印花税"""
        amount = 100000
        stamp_duty = account.calculate_stamp_duty(amount, "sell")
        # 10万 * 0.001 = 100元
        assert stamp_duty == 100.0

    def test_calculate_slippage(self, account):
        """测试滑点计算"""
        amount = 100000
        slippage = account.calculate_slippage(amount, "buy")
        # 10万 * 0.0005 = 50元
        assert slippage == 50.0

    def test_calculate_total_fee_buy(self, account):
        """测试买入总费用"""
        amount = 100000
        fees = account.calculate_total_fee(amount, "buy")
        # 佣金30 + 印花税0 + 滑点50 = 80元
        assert abs(fees["commission"] - 30.0) < 0.01
        assert fees["stamp_duty"] == 0.0
        assert abs(fees["slippage"] - 50.0) < 0.01
        assert abs(fees["total"] - 80.0) < 0.01

    def test_calculate_total_fee_sell(self, account):
        """测试卖出总费用"""
        amount = 100000
        fees = account.calculate_total_fee(amount, "sell")
        # 佣金30 + 印花税100 + 滑点50 = 180元
        assert abs(fees["commission"] - 30.0) < 0.01
        assert fees["stamp_duty"] == 100.0
        assert abs(fees["slippage"] - 50.0) < 0.01
        assert abs(fees["total"] - 180.0) < 0.01


# ============================================
# 交易更新测试
# ============================================

class TestTradeUpdate:
    """测试交易更新"""

    def test_update_from_buy_trade(self, account, buy_match_result):
        """测试更新买入交易"""
        result = account.update_from_trade(buy_match_result)

        assert result is True
        assert account.cash < 1_000_000.0  # 现金减少

        # 检查持仓
        positions = account.get_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "600519"
        assert positions[0].shares == 100

    def test_update_from_sell_trade(self, account, buy_match_result, sell_match_result):
        """测试更新卖出交易"""
        # 先买入
        account.update_from_trade(buy_match_result)
        initial_cash = account.cash

        # 再卖出
        result = account.update_from_trade(sell_match_result)

        assert result is True
        assert account.cash > initial_cash  # 现金增加

        # 检查持仓清空
        positions = account.get_positions()
        assert len(positions) == 0

    def test_buy_new_position(self, account, buy_match_result):
        """测试买入新建持仓"""
        account.update_from_trade(buy_match_result)

        position = account.get_position("600519")
        assert position is not None
        assert position.shares == 100
        assert position.avg_cost == 1680.0
        assert position.current_price == 1680.0

    def test_buy_add_to_position(self, account, buy_match_result):
        """测试加仓"""
        # 第一次买入
        account.update_from_trade(buy_match_result)

        # 第二次买入（修改价格）
        buy_order_2 = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=200,
            price=1700.0,
            order_type=OrderType.LIMIT,
        )
        match_result_2 = MatchResult(
            order=buy_order_2,
            filled_quantity=200,
            filled_price=1700.0,
            fully_filled=True,
            reason="撮合成功",
        )
        account.update_from_trade(match_result_2)

        position = account.get_position("600519")
        assert position.shares == 300
        # 平均成本 = (100*1680 + 200*1700) / 300 = 1693.33
        assert abs(position.avg_cost - 1693.33) < 0.01

    def test_sell_partial_position(self, account, buy_match_result):
        """测试部分卖出"""
        # 买入300股
        buy_order_2 = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=300,
            price=1680.0,
            order_type=OrderType.LIMIT,
        )
        match_result_buy = MatchResult(
            order=buy_order_2,
            filled_quantity=300,
            filled_price=1680.0,
            fully_filled=True,
            reason="撮合成功",
        )
        account.update_from_trade(match_result_buy)

        # 卖出100股
        sell_order_100 = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.SELL,
            quantity=100,
            price=1700.0,
            order_type=OrderType.LIMIT,
        )
        match_result_sell = MatchResult(
            order=sell_order_100,
            filled_quantity=100,
            filled_price=1700.0,
            fully_filled=True,
            reason="撮合成功",
        )
        account.update_from_trade(match_result_sell)

        position = account.get_position("600519")
        assert position.shares == 200

    def test_sell_insufficient_shares(self, account, sell_match_result):
        """测试卖出超过持仓"""
        result = account.update_from_trade(sell_match_result)
        assert result is False

    def test_update_partial_fill_skipped(self, account):
        """测试部分成交跳过更新"""
        order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=200,
            price=1680.0,
            order_type=OrderType.LIMIT,
        )
        match_result = MatchResult(
            order=order,
            filled_quantity=100,  # 部分成交
            filled_price=1680.0,
            fully_filled=False,
            reason="部分成交",
        )

        result = account.update_from_trade(match_result)
        assert result is False

    def test_update_without_price_skipped(self, account):
        """测试无价格跳过更新"""
        order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=None,  # 无价格
            order_type=OrderType.MARKET,
        )
        match_result = MatchResult(
            order=order,
            filled_quantity=100,
            filled_price=None,  # 无成交价格
            fully_filled=True,
            reason="撮合成功",
        )

        result = account.update_from_trade(match_result)
        assert result is False


# ============================================
# 持仓查询测试
# ============================================

class TestPositions:
    """测试持仓查询"""

    def test_get_positions_empty(self, account):
        """测试查询空持仓"""
        positions = account.get_positions()
        assert positions == []

    def test_get_position_nonexistent(self, account):
        """测试查询不存在的持仓"""
        position = account.get_position("600519")
        assert position is None

    def test_get_position_after_buy(self, account, buy_match_result):
        """测试买入后查询持仓"""
        account.update_from_trade(buy_match_result)

        position = account.get_position("600519")
        assert position is not None
        assert position.symbol == "600519"
        assert position.shares == 100


# ============================================
# 价格更新测试
# ============================================

class TestPriceUpdate:
    """测试价格更新"""

    def test_update_prices(self, account, buy_match_result):
        """测试批量更新价格"""
        account.update_from_trade(buy_match_result)

        prices = {
            "600519": 1700.0,
            "000001": 15.0,
        }
        account.update_prices(prices)

        position = account.get_position("600519")
        assert position.current_price == 1700.0

    def test_position_value_after_price_update(self, account, buy_match_result):
        """测试价格更新后持仓市值"""
        account.update_from_trade(buy_match_result)

        # 更新价格
        account.update_prices({"600519": 1700.0})

        # 持仓市值 = 100 * 1700 = 170000
        assert account.position_value == 170000.0


# ============================================
# 账户信息测试
# ============================================

class TestAccountInfo:
    """测试账户信息"""

    def test_get_account_info_initial(self, account):
        """测试初始账户信息"""
        info = account.get_account_info()

        assert info["initial_cash"] == 1_000_000.0
        assert info["cash"] == 1_000_000.0
        assert info["total_value"] == 1_000_000.0
        assert info["position_value"] == 0.0
        assert info["profit_loss"] == 0.0
        assert info["profit_loss_ratio"] == 0.0
        assert info["position_count"] == 0

    def test_get_account_info_after_buy(self, account, buy_match_result):
        """测试买入后账户信息"""
        account.update_from_trade(buy_match_result)
        info = account.get_account_info()

        assert info["cash"] < 1_000_000.0
        assert info["position_value"] > 0
        assert info["position_count"] == 1

    def test_get_trades_empty(self, account):
        """测试查询空交易记录"""
        trades = account.get_trades()
        assert trades == []

    def test_get_trades_after_buy(self, account, buy_match_result):
        """测试买入后查询交易记录"""
        account.update_from_trade(buy_match_result)

        trades = account.get_trades()
        assert len(trades) == 1
        assert trades[0]["symbol"] == "600519"
        assert trades[0]["side"] == "buy"
        assert trades[0]["shares"] == 100


# ============================================
# 原子性测试
# ============================================

class TestAtomicity:
    """测试原子性"""

    def test_transaction_rollback_on_error(self, account):
        """测试错误时事务回滚"""
        initial_cash = account.cash

        # 尝试卖出不存在的持仓（应该失败）
        order = Order(
            order_id=str(uuid4()),
            symbol="999999",
            side=OrderSide.SELL,
            quantity=100,
            price=100.0,
            order_type=OrderType.LIMIT,
        )
        match_result = MatchResult(
            order=order,
            filled_quantity=100,
            filled_price=100.0,
            fully_filled=True,
            reason="撮合成功",
        )

        result = account.update_from_trade(match_result)

        # 更新失败
        assert result is False

        # 现金未变
        assert account.cash == initial_cash


# ============================================
# 重置测试
# ============================================

class TestReset:
    """测试账户重置"""

    def test_reset_account(self, account, buy_match_result):
        """测试重置账户"""
        # 先进行交易
        account.update_from_trade(buy_match_result)
        assert account.get_position("600519") is not None

        # 重置
        account.reset()

        # 验证重置
        assert account.cash == 1_000_000.0
        assert len(account.get_positions()) == 0
        assert len(account.get_trades()) == 0


# ============================================
# 数据库测试
# ============================================

class TestDatabase:
    """测试数据库操作"""

    def test_persist_positions_across_instances(self, temp_db):
        """测试持仓跨实例持久化"""
        # 第一个实例买入
        account1 = Account(initial_cash=1_000_000.0, db_path=temp_db)
        order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=1680.0,
            order_type=OrderType.LIMIT,
        )
        match_result = MatchResult(
            order=order,
            filled_quantity=100,
            filled_price=1680.0,
            fully_filled=True,
            reason="撮合成功",
        )
        account1.update_from_trade(match_result)
        account1.close()

        # 第二个实例读取
        account2 = Account(initial_cash=1_000_000.0, db_path=temp_db)
        position = account2.get_position("600519")

        assert position is not None
        assert position.shares == 100
        account2.close()
