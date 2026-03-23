# -*- coding: utf-8 -*-
"""
生存等级系统

根据账户回撤率自动调整策略和模型。

等级定义:
- normal: 回撤 <10%，融合双模型，最大仓位30%，交易频率1分钟
- low_compute: 回撤 10-20%，仅本地模型，最大仓位20%，交易频率5分钟
- critical: 回撤 20-30%，仅本地模型，最大仓位10%，交易频率10分钟
- dead: 回撤 >30%，停止运行
"""

from datetime import datetime, timedelta
from typing import Optional

from core.schemas import SurvivalLevel, SurvivalState


class SurvivalRules:
    """
    生存等级管理

    转换规则:
    - normal → low_compute: 回撤≥10%（立即）
    - low_compute → critical: 回撤≥20%（立即）
    - critical → dead: 回撤>30%（立即）
    - low_compute → normal: 回撤<10%持续5分钟
    - critical → normal: 回撤<10%持续10分钟
    - dead → low_compute: 用户手动重启
    """

    # 等级配置
    LEVEL_CONFIG = {
        SurvivalLevel.NORMAL: {
            "max_position": 0.30,
            "trading_interval": 60,  # 1分钟
        },
        SurvivalLevel.LOW_COMPUTE: {
            "max_position": 0.20,
            "trading_interval": 300,  # 5分钟
        },
        SurvivalLevel.CRITICAL: {
            "max_position": 0.10,
            "trading_interval": 600,  # 10分钟
        },
        SurvivalLevel.DEAD: {
            "max_position": 0.0,
            "trading_interval": 0,
        },
    }

    # 回撤阈值
    THRESHOLD_NORMAL = 0.10  # 10%
    THRESHOLD_LOW_COMPUTE = 0.20  # 20%
    THRESHOLD_CRITICAL = 0.30  # 30%

    # 恢复持续时间
    RECOVERY_DURATION_LOW_COMPUTE = timedelta(minutes=5)
    RECOVERY_DURATION_CRITICAL = timedelta(minutes=10)

    def __init__(self, initial_cash: float):
        """
        初始化生存等级系统

        Args:
            initial_cash: 初始资金
        """
        self.initial_cash = initial_cash
        self._below_threshold_since: Optional[datetime] = None
        self.current_state = SurvivalState(
            level=SurvivalLevel.NORMAL,
            drawdown=0.0,
            max_position=self.LEVEL_CONFIG[SurvivalLevel.NORMAL]["max_position"],
            trading_interval=self.LEVEL_CONFIG[SurvivalLevel.NORMAL]["trading_interval"],
            last_update=self._now(),
        )

    def get_current_state(self) -> SurvivalState:
        """获取当前状态"""
        return self.current_state

    def _now(self) -> datetime:
        """获取当前时间（兼容freezegun测试）"""
        return datetime.now()

    def update_level(self, current_value: float) -> SurvivalState:
        """
        根据当前总资产更新生存等级

        Args:
            current_value: 当前总资产

        Returns:
            更新后的状态
        """
        # 计算回撤率
        if current_value >= self.initial_cash:
            drawdown = 0.0
        else:
            drawdown = (self.initial_cash - current_value) / self.initial_cash

        current_level = self.current_state.level

        # dead 状态不能自动恢复
        if current_level == SurvivalLevel.DEAD:
            self.current_state.drawdown = drawdown
            self.current_state.last_update = datetime.now()
            return self.current_state

        # 检查是否需要升级到更危急状态（立即）
        if drawdown > self.THRESHOLD_CRITICAL:
            self._below_threshold_since = None
            self.current_state = self._create_state(SurvivalLevel.DEAD, drawdown)
            return self.current_state
        elif drawdown >= self.THRESHOLD_LOW_COMPUTE and current_level != SurvivalLevel.CRITICAL:
            # 升级到 CRITICAL（如果还不是）
            if current_level != SurvivalLevel.CRITICAL:
                self._below_threshold_since = None
                self.current_state = self._create_state(SurvivalLevel.CRITICAL, drawdown)
                return self.current_state
        elif drawdown >= self.THRESHOLD_NORMAL and current_level == SurvivalLevel.NORMAL:
            # 升级到 LOW_COMPUTE
            self._below_threshold_since = None
            self.current_state = self._create_state(SurvivalLevel.LOW_COMPUTE, drawdown)
            return self.current_state

        # 检查是否可以恢复到正常状态（需要持续时间）
        now = self._now()
        if current_level in [SurvivalLevel.LOW_COMPUTE, SurvivalLevel.CRITICAL]:
            if drawdown < self.THRESHOLD_NORMAL:
                # 回撤回落到阈值以下
                if self._below_threshold_since is None:
                    self._below_threshold_since = now
                else:
                    # 检查持续时间
                    duration = now - self._below_threshold_since
                    required_duration = (
                        self.RECOVERY_DURATION_CRITICAL
                        if current_level == SurvivalLevel.CRITICAL
                        else self.RECOVERY_DURATION_LOW_COMPUTE
                    )

                    if duration >= required_duration:
                        # 恢复到 normal
                        self._below_threshold_since = None
                        self.current_state = self._create_state(SurvivalLevel.NORMAL, drawdown)
                        return self.current_state
            else:
                # 回撤仍在阈值以上，重置计时
                self._below_threshold_since = None

        # 更新回撤率和时间
        self.current_state.drawdown = drawdown
        self.current_state.last_update = now
        return self.current_state

    def _check_upgrade(self, drawdown: float) -> SurvivalLevel:
        """
        检查是否需要升级到更危急状态

        Args:
            drawdown: 当前回撤率

        Returns:
            新的等级（如果需要升级）或当前等级
        """
        current_level = self.current_state.level

        # dead 状态不能自动恢复
        if current_level == SurvivalLevel.DEAD:
            return SurvivalLevel.DEAD

        # 检查升级条件
        if drawdown > self.THRESHOLD_CRITICAL:
            return SurvivalLevel.DEAD
        elif drawdown >= self.THRESHOLD_LOW_COMPUTE:
            return SurvivalLevel.CRITICAL
        elif drawdown >= self.THRESHOLD_NORMAL:
            return SurvivalLevel.LOW_COMPUTE

        # 保持当前等级
        return current_level

    def _create_state(self, level: SurvivalLevel, drawdown: float) -> SurvivalState:
        """创建新的状态"""
        config = self.LEVEL_CONFIG[level]
        return SurvivalState(
            level=level,
            drawdown=drawdown,
            max_position=config["max_position"],
            trading_interval=config["trading_interval"],
            last_update=self._now(),
        )

    def restart(self):
        """
        手动重启（从 dead 状态恢复）

        重启后从 low_compute 开始，给一次改过机会
        """
        self._below_threshold_since = None
        self.current_state = self._create_state(SurvivalLevel.LOW_COMPUTE, 0.0)

    def is_trading_allowed(self) -> bool:
        """检查是否允许交易"""
        return self.current_state.level != SurvivalLevel.DEAD

    def get_max_position(self, current_level: Optional[SurvivalLevel] = None) -> float:
        """获取最大仓位比例"""
        level = current_level or self.current_state.level
        return self.LEVEL_CONFIG[level]["max_position"]

    def get_trading_interval(self, current_level: Optional[SurvivalLevel] = None) -> int:
        """获取交易间隔（秒）"""
        level = current_level or self.current_state.level
        return self.LEVEL_CONFIG[level]["trading_interval"]
