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
