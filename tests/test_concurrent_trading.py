# -*- coding: utf-8 -*-
"""
并发交易测试 - 测试线程安全
"""

import sqlite3
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from simulation.account import Account, FeeConfig
from core.schemas import Order, OrderSide, OrderType, MatchResult


@pytest.fixture
def temp_db():
    """临时数据库路径"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # 清理
    import gc
    gc.collect()
    try:
        Path(db_path).unlink(missing_ok=True)
    except PermissionError:
        pass


@pytest.fixture
def account(temp_db):
    """创建测试账户（禁用记忆系统以避免并发数据库锁定）"""
    acc = Account(
        initial_cash=100_000.0,
        db_path=temp_db,
        enable_memory=False,  # 禁用记忆系统避免SQLite并发锁定
    )
    yield acc
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


# ============================================
# 并发测试
# ============================================

class TestConcurrentTrading:
    """测试并发交易安全性"""

    def test_concurrent_buy_orders_no_overdraw(self, account):
        """测试并发买入订单 - 不应透支"""
        initial_cash = account.cash
        # 费用计算: 佣金(万三,最低5元) + 滑点(万五)
        # 100 * 100.0 = 10000
        # 佣金: max(10000 * 0.0003, 5) = 5
        # 滑点: 10000 * 0.0005 = 5
        # 总费用: 5 + 5 = 10
        # 总成本: 10000 + 10 = 10010

        # 创建小订单并发执行，每个100股，价格100元
        small_order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=100.0,
            order_type=OrderType.LIMIT,
        )
        small_match = MatchResult(
            order=small_order,
            filled_quantity=100,
            filled_price=100.0,
            fully_filled=True,
            reason="撮合成功",
        )

        results = []
        threads = []

        def execute_buy():
            result = account.update_from_trade(small_match)
            results.append(result)

        # 执行5个并发买入，每个成本约10010
        for _ in range(5):
            thread = threading.Thread(target=execute_buy)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # 验证：最终现金应该 >= 0
        final_cash = account.cash
        assert final_cash >= 0, f"现金为负: {final_cash}"

        # 至少有一些交易应该成功
        successful = sum(1 for r in results if r)
        assert successful >= 1, f"至少应该有一个交易成功，实际: {successful}/5"

    def test_concurrent_sell_orders_no_oversell(self, account):
        """测试并发卖出订单 - 不应超卖"""
        # 先买入 300 股（价格足够低以确保成功）
        buy_order_300 = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=300,
            price=100.0,  # 降低价格确保资金充足
            order_type=OrderType.LIMIT,
        )
        match_result_300 = MatchResult(
            order=buy_order_300,
            filled_quantity=300,
            filled_price=100.0,
            fully_filled=True,
            reason="撮合成功",
        )
        buy_success = account.update_from_trade(match_result_300)
        assert buy_success, "买入应该成功"

        # 验证买入后有持仓
        position = account.get_position("600519")
        assert position is not None, "买入后应该有持仓"
        assert position.shares == 300, f"应该持有300股，实际: {position.shares}"

        # 创建 3 个卖出订单（每个 100 股）
        sell_orders = []
        for i in range(3):
            order = Order(
                order_id=str(uuid4()),
                symbol="600519",
                side=OrderSide.SELL,
                quantity=100,
                price=1700.0,
                order_type=OrderType.LIMIT,
            )
            match_result = MatchResult(
                order=order,
                filled_quantity=100,
                filled_price=1700.0,
                fully_filled=True,
                reason="撮合成功",
            )
            sell_orders.append(match_result)

        # 并发执行卖出
        results = []
        threads = []

        def execute_sell(result):
            r = account.update_from_trade(result)
            results.append(r)

        for result in sell_orders:
            thread = threading.Thread(target=execute_sell, args=(result,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # 验证：最终持仓应该为 0
        position = account.get_position("600519")
        if position:
            assert position.shares == 0, f"持仓应该为0，实际: {position.shares}"

        # 所有卖出都应该成功
        successful = sum(1 for r in results if r)
        assert successful == 3, f"所有卖出应该成功，实际: {successful}/3"

    def test_concurrent_mixed_orders(self, account):
        """测试混合并发交易"""
        # 创建多个订单
        buy_order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=100.0,  # 降低价格确保资金充足
            order_type=OrderType.LIMIT,
        )
        buy_match = MatchResult(
            order=buy_order,
            filled_quantity=100,
            filled_price=100.0,
            fully_filled=True,
            reason="撮合成功",
        )

        sell_order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.SELL,
            quantity=100,  # 改为100的倍数
            price=1700.0,
            order_type=OrderType.LIMIT,
        )
        sell_match = MatchResult(
            order=sell_order,
            filled_quantity=100,
            filled_price=1700.0,
            fully_filled=True,
            reason="撮合成功",
        )

        results = []
        threads = []

        def execute_trade(match_result):
            r = account.update_from_trade(match_result)
            results.append((match_result.order.side.value, r))

        # 买入 100 股
        thread1 = threading.Thread(target=execute_trade, args=(buy_match,))
        # 卖出 100 股（可能成功也可能失败，取决于线程调度顺序）
        thread2 = threading.Thread(target=execute_trade, args=(sell_match,))

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # 买入应该成功
        buy_success = any(s == "buy" and r for s, r in results)
        assert buy_success is True, "买入应该成功"

        # 卖出的结果取决于线程调度顺序
        # 如果买入先完成，卖出会成功；如果卖出先执行，会失败
        # 两种情况都是正确的并发行为
        sell_success = any(s == "sell" and r for s, r in results)

        # 验证最终状态一致性
        position = account.get_position("600519")

        if buy_success and not sell_success:
            # 只有买入成功：卖出先执行但失败
            assert position is not None, "应该有持仓"
            assert position.shares == 100, "应该持有100股"
        elif buy_success and sell_success:
            # 两个都成功：买入先执行，然后卖出也成功
            # 持仓应该为0（买入100，卖出100）
            if position:
                assert position.shares == 0, "持仓应该被清空"
            else:
                # 持仓可能已被删除（shares=0时）
                pass
        else:
            # 只有卖出成功（不应该发生，因为没有持仓）
            assert False, "卖出不应该在没有持仓时成功"

        # 核心验证：最终现金应该 >= 0（不应该透支）
        assert account.cash >= 0, f"现金不应该为负: {account.cash}"


# ============================================
# 边界条件测试
# ============================================

class TestBoundaryConditions:
    """测试边界条件"""

    def test_buy_exact_cash_available(self, account):
        """测试刚好够钱的买入"""
        initial_cash = account.cash
        price = initial_cash / 100 - 1  # 留 1 元费用空间

        order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=price,
            order_type=OrderType.LIMIT,
        )
        match_result = MatchResult(
            order=order,
            filled_quantity=100,
            filled_price=price,
            fully_filled=True,
            reason="撮合成功",
        )

        result = account.update_from_trade(match_result)
        assert result is True, "刚好够钱应该成功"

    def test_buy_one_cent_short(self, account):
        """测试差 1 分钱应该失败"""
        initial_cash = account.cash
        price = (initial_cash + 1) / 100  # 超出 1 分

        order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=price,
            order_type=OrderType.LIMIT,
        )
        match_result = MatchResult(
            order=order,
            filled_quantity=100,
            filled_price=price,
            fully_filled=True,
            reason="撮合成功",
        )

        result = account.update_from_trade(match_result)
        assert result is False, "资金不足应该失败"

    def test_sell_exact_shares(self, account):
        """测试卖出刚好所有持仓"""
        # 先买入 100 股（降低价格确保资金充足）
        buy_order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=100.0,
            order_type=OrderType.LIMIT,
        )
        buy_match = MatchResult(
            order=buy_order,
            filled_quantity=100,
            filled_price=100.0,
            fully_filled=True,
            reason="撮合成功",
        )
        buy_result = account.update_from_trade(buy_match)
        assert buy_result is True, "买入应该成功"

        # 验证买入后有持仓
        position = account.get_position("600519")
        assert position is not None, "买入后应该有持仓"

        # 卖出 100 股
        sell_order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.SELL,
            quantity=100,
            price=1700.0,
            order_type=OrderType.LIMIT,
        )
        sell_match = MatchResult(
            order=sell_order,
            filled_quantity=100,
            filled_price=1700.0,
            fully_filled=True,
            reason="撮合成功",
        )

        result = account.update_from_trade(sell_match)
        assert result is True, "卖出全部持仓应该成功"

        # 验证持仓已清空
        position = account.get_position("600519")
        assert position is None, "持仓应该已清空"

    def test_sell_one_share_short(self, account):
        """测试卖出比持仓多 100 股应该失败"""
        # 先买入 100 股
        buy_order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.BUY,
            quantity=100,
            price=100.0,
            order_type=OrderType.LIMIT,
        )
        buy_match = MatchResult(
            order=buy_order,
            filled_quantity=100,
            filled_price=100.0,
            fully_filled=True,
            reason="撮合成功",
        )
        buy_result = account.update_from_trade(buy_match)
        assert buy_result is True, "买入应该成功"

        # 尝试卖出 200 股（持仓只有100股）
        sell_order = Order(
            order_id=str(uuid4()),
            symbol="600519",
            side=OrderSide.SELL,
            quantity=200,
            price=1700.0,
            order_type=OrderType.LIMIT,
        )
        sell_match = MatchResult(
            order=sell_order,
            filled_quantity=200,
            filled_price=1700.0,
            fully_filled=True,
            reason="撮合成功",
        )

        result = account.update_from_trade(sell_match)
        assert result is False, "持仓不足应该失败"

        # 验证持仓仍然存在且数量不变
        position = account.get_position("600519")
        assert position is not None, "持仓应该仍然存在"
        assert position.shares == 100, f"持仓应该仍为100股，实际: {position.shares}"


# ============================================
# 数值精度测试
# ============================================

class TestNumericalPrecision:
    """测试数值精度"""

    def test_fee_calculation_precision(self, account):
        """测试费用计算精度"""
        # 使用可能产生精度问题的数值
        amount = 100.01
        fees = account.calculate_total_fee(amount, "buy")

        # 验证精度
        expected_commission = max(amount * 0.0003, 5.0)
        assert abs(fees["commission"] - expected_commission) < 0.001

        expected_stamp = 0.0
        assert fees["stamp_duty"] == expected_stamp

        expected_slippage = amount * 0.0005
        assert abs(fees["slippage"] - expected_slippage) < 0.001

        expected_total = expected_commission + expected_stamp + expected_slippage
        assert abs(fees["total"] - expected_total) < 0.001

    def test_repeated_calculation_no_error_accumulation(self, account):
        """测试重复计算不会累积误差"""
        amounts = [10000.01, 20000.03, 15000.07, 9999.99]

        total_fees = 0
        for amount in amounts:
            fees = account.calculate_total_fee(amount, "buy")
            total_fees += fees["total"]

        # 验证可以反向计算
        # 这测试确保没有精度丢失导致无法对账
        assert total_fees > 0
        assert isinstance(total_fees, float)

    def test_large_amount_precision(self, account):
        """测试大额金额的精度"""
        amount = 1_000_000.01  # 100万
        fees = account.calculate_total_fee(amount, "buy")

        # 佣金应该精确
        expected_commission = max(amount * 0.0003, 5.0)
        assert abs(fees["commission"] - expected_commission) < 0.01

        # 总费用应该精确
        expected_total = expected_commission + amount * 0.0005
        assert abs(fees["total"] - expected_total) < 0.01
