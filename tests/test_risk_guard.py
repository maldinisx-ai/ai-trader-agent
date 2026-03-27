# -*- coding: utf-8 -*-
"""
Risk Guard 单元测试
"""

import pytest
from datetime import datetime
from core.risk_guard import RiskGuard, RiskDecision
from core.schemas import AccountState, MarketState, MarketRegime


# Helper function to create test data
def create_account_state(daily_loss_ratio=None, total_value=97000, initial_cash=100000, available_cash=97000):
    """创建测试账户状态"""
    kwargs = {
        "total_value": total_value,
        "initial_cash": initial_cash,
        "available_cash": available_cash,
    }
    # 只有在显式提供时才添加 daily_loss_ratio
    if daily_loss_ratio is not None:
        kwargs["daily_loss_ratio"] = daily_loss_ratio

    return AccountState(**kwargs)


def create_market_state(volatility=0.02):
    """创建测试市场状态"""
    return MarketState(
        regime=MarketRegime.SIDEWAYS,
        confidence=0.5,
        max_position_ratio=0.3,
        volatility=volatility
    )


class TestRiskGuard:
    """Risk Guard 测试"""

    def test_risk_guard_daily_loss_within_limit(self):
        """测试：单日亏损在限制内"""
        guard = RiskGuard()
        account_state = create_account_state(0.03)  # 3%
        market_state = create_market_state(0.02)

        # 10:00 AM（交易时间内）
        now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        result = guard.check(account_state, market_state, current_time=now)

        assert result.forbid == False
        assert "风险检查通过" in result.reason

    def test_risk_guard_daily_loss_exceeds_limit(self):
        """测试：单日亏损超过阈值"""
        guard = RiskGuard()
        account_state = create_account_state(0.06)  # 6% > 5%
        market_state = create_market_state(0.02)

        # 10:00 AM（交易时间内）
        now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        result = guard.check(account_state, market_state, current_time=now)

        assert result.forbid == True
        assert "单日亏损" in result.reason
        # 检查包含 6 或 6.0
        assert "6" in result.reason

    def test_risk_guard_high_volatility(self):
        """测试：市场波动率过高"""
        guard = RiskGuard()
        account_state = create_account_state(0.03)
        market_state = create_market_state(0.06)  # 6% > 5%

        # 10:00 AM（交易时间内）
        now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        result = guard.check(account_state, market_state, current_time=now)

        assert result.forbid == True
        assert "波动率" in result.reason
        # 检查包含 6 或 6.0
        assert "6" in result.reason

    def test_risk_guard_consecutive_errors_within_limit(self):
        """测试：连续错误次数在限制内"""
        guard = RiskGuard()
        account_state = create_account_state(0.03)
        market_state = create_market_state(0.02)

        # 10:00 AM（交易时间内）
        now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)

        # 记录 2 次错误
        guard.record_error()
        guard.record_error()

        result = guard.check(account_state, market_state, current_time=now)

        assert result.forbid == False

    def test_risk_guard_consecutive_errors_exceeds_limit(self):
        """测试：连续错误次数超过阈值"""
        guard = RiskGuard()
        account_state = create_account_state(0.03)
        market_state = create_market_state(0.02)

        # 10:00 AM（交易时间内）
        now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)

        # 记录 3 次错误
        guard.record_error()
        guard.record_error()
        guard.record_error()

        result = guard.check(account_state, market_state, current_time=now)

        assert result.forbid == True
        assert "连续 3 次" in result.reason

    def test_risk_guard_success_resets_counter(self):
        """测试：成功决策重置计数器"""
        guard = RiskGuard()
        account_state = create_account_state(0.03)
        market_state = create_market_state(0.02)

        # 10:00 AM（交易时间内）
        now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)

        # 先记录错误
        guard.record_error()
        assert guard.consecutive_errors == 1

        # 记录成功
        guard.record_success()
        assert guard.consecutive_errors == 0

        result = guard.check(account_state, market_state, current_time=now)

        assert result.forbid == False

    def test_risk_guard_trading_time_valid(self):
        """测试：在交易时间内"""
        guard = RiskGuard()
        account_state = create_account_state(0.03)
        market_state = create_market_state(0.02)

        # 10:00 AM（交易时间内）
        now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        result = guard.check(account_state, market_state, current_time=now)

        assert result.forbid == False

    def test_risk_guard_trading_time_invalid_before_open(self):
        """测试：开盘前"""
        guard = RiskGuard()
        account_state = create_account_state(0.03)
        market_state = create_market_state(0.02)

        # 9:00 AM（开盘前）
        now = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        result = guard.check(account_state, market_state, current_time=now)

        assert result.forbid == True
        assert "交易时段" in result.reason

    def test_risk_guard_trading_time_invalid_after_close(self):
        """测试：收盘后"""
        guard = RiskGuard()
        account_state = create_account_state(0.03)
        market_state = create_market_state(0.02)

        # 15:30 PM（收盘后）
        now = datetime.now().replace(hour=15, minute=30, second=0, microsecond=0)
        result = guard.check(account_state, market_state, current_time=now)

        assert result.forbid == True
        assert "交易时段" in result.reason

    def test_risk_guard_all_checks_pass(self):
        """测试：所有检查都通过"""
        guard = RiskGuard()
        account_state = create_account_state(0.03)
        market_state = create_market_state(0.02)

        # 10:00 AM（交易时间内）
        now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        result = guard.check(account_state, market_state, current_time=now)

        assert result.forbid == False
        assert result.reason == "风险检查通过"

    def test_risk_decision_model(self):
        """测试：RiskDecision 模型"""
        decision = RiskDecision(forbid=True, reason="测试原因")

        assert decision.forbid == True
        assert decision.reason == "测试原因"

        decision2 = RiskDecision(forbid=False, reason="通过")

        assert decision2.forbid == False
        assert decision2.reason == "通过"

    def test_risk_guard_account_without_daily_loss_ratio(self):
        """测试：账户状态没有 daily_loss_ratio 字段"""
        guard = RiskGuard()
        # 创建没有 daily_loss_ratio 的账户状态
        account_state = AccountState(
            total_value=97000,
            initial_cash=100000,
            available_cash=97000
        )
        market_state = create_market_state(0.02)

        # 10:00 AM（交易时间内）
        now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        result = guard.check(account_state, market_state, current_time=now)

        # 应该通过，因为从 total_value 和 initial_cash 计算得到亏损 3%
        assert result.forbid == False

    def test_risk_guard_trading_time_boundary_11_30(self):
        """测试：交易时间边界 - 11:30 正好收盘"""
        guard = RiskGuard()
        account_state = create_account_state(0.03)
        market_state = create_market_state(0.02)

        # 11:30 AM（中午收盘）
        now = datetime.now().replace(hour=11, minute=30, second=0, microsecond=0)
        result = guard.check(account_state, market_state, current_time=now)

        assert result.forbid == True
        assert "交易时段" in result.reason

    def test_risk_guard_trading_time_boundary_12_00(self):
        """测试：交易时间边界 - 12:00 中午休市"""
        guard = RiskGuard()
        account_state = create_account_state(0.03)
        market_state = create_market_state(0.02)

        # 12:00 PM（中午休市）
        now = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
        result = guard.check(account_state, market_state, current_time=now)

        assert result.forbid == True
        assert "交易时段" in result.reason

    def test_risk_guard_trading_time_boundary_13_00(self):
        """测试：交易时间边界 - 13:00 开盘"""
        guard = RiskGuard()
        account_state = create_account_state(0.03)
        market_state = create_market_state(0.02)

        # 13:00 PM（下午开盘）
        now = datetime.now().replace(hour=13, minute=0, second=0, microsecond=0)
        result = guard.check(account_state, market_state, current_time=now)

        assert result.forbid == True
        assert "交易时段" in result.reason

    def test_risk_guard_account_calculation_from_total_value(self):
        """测试：从 total_value 和 initial_cash 计算亏损比例"""
        guard = RiskGuard()

        # 创建初始资金 100000，当前价值 95000（亏损 5%，刚好到阈值）
        account_state = AccountState(
            total_value=95000,
            initial_cash=100000,
            available_cash=95000
        )
        market_state = create_market_state(0.02)

        # 10:00 AM（交易时间内）
        now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        result = guard.check(account_state, market_state, current_time=now)

        # 刚好 5%，应该通过
        assert result.forbid == False

    def test_risk_guard_account_calculation_exceeds_threshold(self):
        """测试：从 total_value 和 initial_cash 计算亏损比例超过阈值"""
        guard = RiskGuard()

        # 创建初始资金 100000，当前价值 94000（亏损 6%，超过阈值）
        account_state = AccountState(
            total_value=94000,
            initial_cash=100000,
            available_cash=94000
        )
        market_state = create_market_state(0.02)

        # 10:00 AM（交易时间内）
        now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        result = guard.check(account_state, market_state, current_time=now)

        # 超过 5% 阈值
        assert result.forbid == True
        assert "单日亏损" in result.reason

    def test_risk_guard_account_profit_no_forbid(self):
        """测试：盈利时不会触发亏损拦截"""
        guard = RiskGuard()

        # 创建初始资金 100000，当前价值 105000（盈利 5%）
        account_state = AccountState(
            total_value=105000,
            initial_cash=100000,
            available_cash=105000
        )
        market_state = create_market_state(0.02)

        # 10:00 AM（交易时间内）
        now = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        result = guard.check(account_state, market_state, current_time=now)

        # 盈利时应该通过
        assert result.forbid == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])