# -*- coding: utf-8 -*-
"""
测试生存等级系统

TDD 流程: RED → GREEN → REFACTOR
"""

import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time

from core.schemas import SurvivalLevel, SurvivalState
from core.survival_rules import SurvivalRules

import core.survival_rules


class TestSurvivalRules:
    """测试生存等级系统"""

    def test_initial_state(self):
        """测试初始状态为 normal"""
        rules = SurvivalRules(initial_cash=1000000.0)
        state = rules.get_current_state()
        assert state.level == SurvivalLevel.NORMAL
        assert state.drawdown == 0.0

    def test_normal_to_low_compute_upgrade(self):
        """测试 normal → low_compute 升级（立即）"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # 回撤达到12%（>10%），立即切换到 low_compute
        state = rules.update_level(current_value=880000.0)  # 12% 回撤
        assert state.level == SurvivalLevel.LOW_COMPUTE
        assert state.max_position == 0.20
        assert state.trading_interval == 300

    def test_low_compute_to_critical_upgrade(self):
        """测试 low_compute → critical 升级（立即）"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # 回撤达到25%（>20%），立即切换到 critical
        state = rules.update_level(current_value=750000.0)
        assert state.level == SurvivalLevel.CRITICAL
        assert state.max_position == 0.10
        assert state.trading_interval == 600

    def test_critical_to_dead_upgrade(self):
        """测试 critical → dead 升级（立即）"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # 回撤超过30%，立即切换到 dead
        state = rules.update_level(current_value=690000.0)
        assert state.level == SurvivalLevel.DEAD
        assert state.max_position == 0.0

    def test_low_compute_to_normal_recovery(self):
        """测试 low_compute → normal 恢复（需要持续时间）"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # 使用连续时间线测试
        base_time = datetime(2024, 3, 23, 10, 0, 0)

        # 先升级到 low_compute
        with freeze_time(base_time):
            state = rules.update_level(current_value=880000.0)  # 12% 回撤
            assert state.level == SurvivalLevel.LOW_COMPUTE

        # 回撤回落到8%（<10%），开始记录时间
        recovery_start = base_time + timedelta(minutes=2)
        with freeze_time(recovery_start):
            state = rules.update_level(current_value=920000.0)  # 8% 回撤
            assert state.level == SurvivalLevel.LOW_COMPUTE
            assert rules._below_threshold_since is not None

        # 5分钟后（从记录时间算起），恢复到 normal
        recovery_end = recovery_start + timedelta(minutes=5, seconds=1)
        with freeze_time(recovery_end):
            state = rules.update_level(current_value=920000.0)  # 8% 回撤
            assert state.level == SurvivalLevel.NORMAL

    def test_critical_to_normal_recovery(self):
        """测试 critical → normal 恢复（需要10分钟持续时间）"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # 使用连续时间线测试
        base_time = datetime(2024, 3, 23, 10, 0, 0)

        # 先升级到 critical
        with freeze_time(base_time):
            state = rules.update_level(current_value=750000.0)  # 25% 回撤
            assert state.level == SurvivalLevel.CRITICAL

        # 回撤回落到8%（<10%），开始记录时间
        recovery_start = base_time + timedelta(minutes=5)
        with freeze_time(recovery_start):
            state = rules.update_level(current_value=920000.0)
            assert state.level == SurvivalLevel.CRITICAL

        # 10分钟后（从记录时间算起），恢复到 normal
        recovery_end = recovery_start + timedelta(minutes=10, seconds=1)
        with freeze_time(recovery_end):
            state = rules.update_level(current_value=920000.0)
            assert state.level == SurvivalLevel.NORMAL

    def test_dead_requires_manual_restart(self):
        """测试 dead 状态需要手动重启"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # 进入 dead 状态
        state = rules.update_level(current_value=690000.0)
        assert state.level == SurvivalLevel.DEAD

        # 即使回撤回落，仍然是 dead（需要手动重启）
        state = rules.update_level(current_value=950000.0)
        assert state.level == SurvivalLevel.DEAD

    def test_manual_restart_from_dead(self):
        """测试从 dead 手动重启"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # 进入 dead 状态
        state = rules.update_level(current_value=690000.0)
        assert state.level == SurvivalLevel.DEAD

        # 手动重启
        rules.restart()
        state = rules.get_current_state()

        # 重启后从 low_compute 开始，给一次改过机会
        assert state.level == SurvivalLevel.LOW_COMPUTE

    def test_no_upgrade_when_stable(self):
        """测试回撤稳定时保持当前等级"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # normal 状态，回撤5%
        state = rules.update_level(current_value=950000.0)
        assert state.level == SurvivalLevel.NORMAL

        # 回撤7%，仍在 normal 范围内
        state = rules.update_level(current_value=930000.0)
        assert state.level == SurvivalLevel.NORMAL

    def test_level_config_mapping(self):
        """测试等级配置映射"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # normal
        state = rules.update_level(current_value=950000.0)
        assert state.max_position == 0.30
        assert state.trading_interval == 60

        # low_compute
        state = rules.update_level(current_value=850000.0)
        assert state.max_position == 0.20
        assert state.trading_interval == 300

        # critical
        state = rules.update_level(current_value=750000.0)
        assert state.max_position == 0.10
        assert state.trading_interval == 600

    def test_drawdown_calculation(self):
        """测试回撤率计算"""
        rules = SurvivalRules(initial_cash=1000000.0)

        state = rules.update_level(current_value=900000.0)
        assert state.drawdown == 0.10  # 10% 回撤

        state = rules.update_level(current_value=800000.0)
        assert state.drawdown == 0.20  # 20% 回撤

        state = rules.update_level(current_value=700000.0)
        assert state.drawdown == 0.30  # 30% 回撤

    def test_profit_no_drawdown(self):
        """测试盈利时回撤为0"""
        rules = SurvivalRules(initial_cash=1000000.0)

        state = rules.update_level(current_value=1100000.0)
        assert state.drawdown == 0.0
        assert state.level == SurvivalLevel.NORMAL


class TestClassConstants:
    """测试类常量"""

    def test_level_config(self):
        """测试等级配置"""
        config = SurvivalRules.LEVEL_CONFIG
        assert SurvivalLevel.NORMAL in config
        assert SurvivalLevel.LOW_COMPUTE in config
        assert SurvivalLevel.CRITICAL in config
        assert SurvivalLevel.DEAD in config

    def test_thresholds(self):
        """测试阈值常量"""
        assert SurvivalRules.THRESHOLD_NORMAL == 0.10
        assert SurvivalRules.THRESHOLD_LOW_COMPUTE == 0.20
        assert SurvivalRules.THRESHOLD_CRITICAL == 0.30

    def test_recovery_durations(self):
        """测试恢复持续时间"""
        assert SurvivalRules.RECOVERY_DURATION_LOW_COMPUTE.total_seconds() == 300  # 5分钟
        assert SurvivalRules.RECOVERY_DURATION_CRITICAL.total_seconds() == 600  # 10分钟


class TestCheckUpgrade:
    """测试升级检查"""

    def test_check_upgrade_dead(self):
        """测试升级到 dead"""
        rules = SurvivalRules(initial_cash=1000000.0)
        rules.current_state.level = SurvivalLevel.CRITICAL

        new_level = rules._check_upgrade(0.31)  # 31% 回撤
        assert new_level == SurvivalLevel.DEAD

    def test_check_upgrade_critical(self):
        """测试升级到 critical"""
        rules = SurvivalRules(initial_cash=1000000.0)
        rules.current_state.level = SurvivalLevel.NORMAL

        new_level = rules._check_upgrade(0.22)  # 22% 回撤
        assert new_level == SurvivalLevel.CRITICAL

    def test_check_upgrade_low_compute(self):
        """测试升级到 low_compute"""
        rules = SurvivalRules(initial_cash=1000000.0)
        rules.current_state.level = SurvivalLevel.NORMAL

        new_level = rules._check_upgrade(0.12)  # 12% 回撤
        assert new_level == SurvivalLevel.LOW_COMPUTE

    def test_check_upgrade_no_change(self):
        """测试保持当前等级"""
        rules = SurvivalRules(initial_cash=1000000.0)
        rules.current_state.level = SurvivalLevel.NORMAL

        new_level = rules._check_upgrade(0.05)  # 5% 回撤
        assert new_level == SurvivalLevel.NORMAL

    def test_check_upgrade_dead_stays_dead(self):
        """测试 dead 状态保持 dead"""
        rules = SurvivalRules(initial_cash=1000000.0)
        rules.current_state.level = SurvivalLevel.DEAD

        # 即使回撤为0，dead状态也不能自动恢复
        new_level = rules._check_upgrade(0.0)
        assert new_level == SurvivalLevel.DEAD


class TestCreateState:
    """测试创建状态"""

    def test_create_state_normal(self):
        """测试创建 normal 状态"""
        rules = SurvivalRules(initial_cash=1000000.0)

        state = rules._create_state(SurvivalLevel.NORMAL, 0.05)
        assert state.level == SurvivalLevel.NORMAL
        assert state.drawdown == 0.05
        assert state.max_position == 0.30
        assert state.trading_interval == 60

    def test_create_state_low_compute(self):
        """测试创建 low_compute 状态"""
        rules = SurvivalRules(initial_cash=1000000.0)

        state = rules._create_state(SurvivalLevel.LOW_COMPUTE, 0.15)
        assert state.level == SurvivalLevel.LOW_COMPUTE
        assert state.drawdown == 0.15
        assert state.max_position == 0.20
        assert state.trading_interval == 300

    def test_create_state_critical(self):
        """测试创建 critical 状态"""
        rules = SurvivalRules(initial_cash=1000000.0)

        state = rules._create_state(SurvivalLevel.CRITICAL, 0.25)
        assert state.level == SurvivalLevel.CRITICAL
        assert state.drawdown == 0.25
        assert state.max_position == 0.10
        assert state.trading_interval == 600

    def test_create_state_dead(self):
        """测试创建 dead 状态"""
        rules = SurvivalRules(initial_cash=1000000.0)

        state = rules._create_state(SurvivalLevel.DEAD, 0.35)
        assert state.level == SurvivalLevel.DEAD
        assert state.drawdown == 0.35
        assert state.max_position == 0.0
        assert state.trading_interval == 0


class TestIsTradingAllowed:
    """测试交易许可检查"""

    def test_trading_allowed_normal(self):
        """测试 normal 状态允许交易"""
        rules = SurvivalRules(initial_cash=1000000.0)

        assert rules.is_trading_allowed() is True

    def test_trading_allowed_low_compute(self):
        """测试 low_compute 状态允许交易"""
        rules = SurvivalRules(initial_cash=1000000.0)
        rules.update_level(850000.0)  # 进入 low_compute

        assert rules.is_trading_allowed() is True

    def test_trading_allowed_critical(self):
        """测试 critical 状态允许交易"""
        rules = SurvivalRules(initial_cash=1000000.0)
        rules.update_level(750000.0)  # 进入 critical

        assert rules.is_trading_allowed() is True

    def test_trading_not_allowed_dead(self):
        """测试 dead 状态不允许交易"""
        rules = SurvivalRules(initial_cash=1000000.0)
        rules.update_level(690000.0)  # 进入 dead

        assert rules.is_trading_allowed() is False


class TestGetMaxPosition:
    """测试获取最大仓位"""

    def test_get_max_position_current_level(self):
        """测试获取当前等级的最大仓位"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # normal
        assert rules.get_max_position() == 0.30

        # 切换到 low_compute
        rules.update_level(850000.0)
        assert rules.get_max_position() == 0.20

    def test_get_max_position_explicit_level(self):
        """测试获取指定等级的最大仓位"""
        rules = SurvivalRules(initial_cash=1000000.0)

        assert rules.get_max_position(SurvivalLevel.NORMAL) == 0.30
        assert rules.get_max_position(SurvivalLevel.LOW_COMPUTE) == 0.20
        assert rules.get_max_position(SurvivalLevel.CRITICAL) == 0.10
        assert rules.get_max_position(SurvivalLevel.DEAD) == 0.0


class TestGetTradingInterval:
    """测试获取交易间隔"""

    def test_get_trading_interval_current_level(self):
        """测试获取当前等级的交易间隔"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # normal
        assert rules.get_trading_interval() == 60

        # 切换到 low_compute
        rules.update_level(850000.0)
        assert rules.get_trading_interval() == 300

    def test_get_trading_interval_explicit_level(self):
        """测试获取指定等级的交易间隔"""
        rules = SurvivalRules(initial_cash=1000000.0)

        assert rules.get_trading_interval(SurvivalLevel.NORMAL) == 60
        assert rules.get_trading_interval(SurvivalLevel.LOW_COMPUTE) == 300
        assert rules.get_trading_interval(SurvivalLevel.CRITICAL) == 600
        assert rules.get_trading_interval(SurvivalLevel.DEAD) == 0


class TestThresholdBoundaries:
    """测试阈值边界"""

    def test_threshold_normal_exact(self):
        """测试正好10%阈值"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # 正好10%，应该升级到 low_compute
        state = rules.update_level(900000.0)
        assert state.level == SurvivalLevel.LOW_COMPUTE

    def test_threshold_normal_below(self):
        """测试略低于10%阈值"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # 9.9%，应该保持 normal
        state = rules.update_level(901000.0)
        assert state.level == SurvivalLevel.NORMAL

    def test_threshold_low_compute_exact(self):
        """测试正好20%阈值"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # 正好20%，应该升级到 critical
        state = rules.update_level(800000.0)
        assert state.level == SurvivalLevel.CRITICAL

    def test_threshold_critical_exact(self):
        """测试正好30%阈值"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # 正好30%，应该保持 critical（不是dead）
        state = rules.update_level(700000.0)
        assert state.level == SurvivalLevel.CRITICAL

    def test_threshold_critical_above(self):
        """测试略高于30%阈值"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # 30.1%，应该升级到 dead
        state = rules.update_level(699000.0)
        assert state.level == SurvivalLevel.DEAD


class TestRecoveryInterruption:
    """测试恢复中断"""

    def test_recovery_interrupted_by_drawdown_increase(self):
        """测试恢复过程中回撤增加会重置计时"""
        rules = SurvivalRules(initial_cash=1000000.0)

        base_time = datetime(2024, 3, 23, 10, 0, 0)

        # 升级到 low_compute
        with freeze_time(base_time):
            state = rules.update_level(850000.0)  # 15% 回撤
            assert state.level == SurvivalLevel.LOW_COMPUTE

        # 回撤回落到8%，开始计时
        recovery_start = base_time + timedelta(minutes=2)
        with freeze_time(recovery_start):
            state = rules.update_level(920000.0)  # 8% 回撤
            assert rules._below_threshold_since is not None

        # 3分钟后，回撤又增加到11%，重置计时
        interruption_time = recovery_start + timedelta(minutes=3)
        with freeze_time(interruption_time):
            state = rules.update_level(890000.0)  # 11% 回撤
            assert state.level == SurvivalLevel.LOW_COMPUTE
            assert rules._below_threshold_since is None  # 计时被重置

        # 回撤回到8%，重新开始计时
        new_recovery_start = interruption_time + timedelta(minutes=1)
        with freeze_time(new_recovery_start):
            state = rules.update_level(920000.0)  # 8% 回撤
            assert state.level == SurvivalLevel.LOW_COMPUTE
            assert rules._below_threshold_since is not None  # 重新开始计时

        # 从新的开始时间，5分钟后恢复
        final_recovery = new_recovery_start + timedelta(minutes=5, seconds=1)
        with freeze_time(final_recovery):
            state = rules.update_level(920000.0)  # 8% 回撤
            assert state.level == SurvivalLevel.NORMAL


class TestStateTransitions:
    """测试状态转换边界情况"""

    def test_direct_normal_to_critical(self):
        """测试从 normal 直接到 critical（跳过 low_compute）"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # 25% 回撤，直接到 critical
        state = rules.update_level(750000.0)
        assert state.level == SurvivalLevel.CRITICAL

    def test_direct_normal_to_dead(self):
        """测试从 normal 直接到 dead（跳过中间状态）"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # 35% 回撤，直接到 dead
        state = rules.update_level(650000.0)
        assert state.level == SurvivalLevel.DEAD

    def test_critical_stays_critical_on_same_drawdown(self):
        """测试 critical 状态在相同回撤时保持 critical"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # 进入 critical
        state = rules.update_level(750000.0)
        assert state.level == SurvivalLevel.CRITICAL

        # 保持相同回撤
        state = rules.update_level(750000.0)
        assert state.level == SurvivalLevel.CRITICAL

    def test_low_compute_to_critical_on_threshold_cross(self):
        """测试 low_compute 在达到20%时升级到 critical"""
        rules = SurvivalRules(initial_cash=1000000.0)

        # 进入 low_compute
        state = rules.update_level(880000.0)
        assert state.level == SurvivalLevel.LOW_COMPUTE

        # 回撤增加到22%，升级到 critical
        state = rules.update_level(780000.0)
        assert state.level == SurvivalLevel.CRITICAL


class TestCurrentState:
    """测试当前状态"""

    def test_get_current_state_returns_same_instance(self):
        """测试获取当前状态返回相同实例"""
        rules = SurvivalRules(initial_cash=1000000.0)

        state1 = rules.get_current_state()
        state2 = rules.get_current_state()

        assert state1 is state2

    def test_current_state_updated_on_level_change(self):
        """测试等级改变时当前状态更新"""
        rules = SurvivalRules(initial_cash=1000000.0)

        initial_state = rules.get_current_state()
        assert initial_state.level == SurvivalLevel.NORMAL

        new_state = rules.update_level(850000.0)
        assert new_state.level == SurvivalLevel.LOW_COMPUTE

        # get_current_state 返回更新后的状态
        current = rules.get_current_state()
        assert current.level == SurvivalLevel.LOW_COMPUTE
        assert current is new_state
