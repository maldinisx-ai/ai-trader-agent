# -*- coding: utf-8 -*-
"""
风险前置拦截层 (Risk Guard)

在 Agent 思考和决策之前进行风险检查，禁止高风险场景下的交易。
"""

import logging
from datetime import datetime, time
from typing import Optional
from pydantic import BaseModel

from core.schemas import MarketState

logger = logging.getLogger(__name__)


class RiskDecision(BaseModel):
    """风险检查结果"""
    forbid: bool  # 是否禁止交易
    reason: str   # 禁止原因或通过说明


class RiskGuard:
    """风险前置拦截层"""

    def __init__(
        self,
        daily_loss_threshold: float = 0.05,
        volatility_threshold: float = 0.05,
        max_consecutive_errors: int = 3,
    ):
        """
        初始化风险拦截器

        Args:
            daily_loss_threshold: 单日亏损阈值（如 0.05 表示 5%）
            volatility_threshold: 市场波动率阈值（如 0.05 表示 5%）
            max_consecutive_errors: 最大连续错误次数
        """
        self.daily_loss_threshold = daily_loss_threshold
        self.volatility_threshold = volatility_threshold
        self.max_consecutive_errors = max_consecutive_errors
        self.consecutive_errors = 0
        self.last_trade_time = None

    def check(
        self,
        account_state: "AccountState",
        market_state: MarketState,
        current_time: Optional[datetime] = None,
    ) -> RiskDecision:
        """
        执行风险检查

        Args:
            account_state: 账户状态
            market_state: 市场状态
            current_time: 当前时间（可选）

        Returns:
            RiskDecision: 风险检查结果
        """
        try:
            # 1. 检查单日亏损
            daily_loss_ratio = self._get_daily_loss_ratio(account_state)
            if daily_loss_ratio is not None and daily_loss_ratio > self.daily_loss_threshold:
                return RiskDecision(
                    forbid=True,
                    reason=f"单日亏损 {daily_loss_ratio:.1%} 超过阈值 {self.daily_loss_threshold:.0%}"
                )

            # 2. 检查市场波动率
            if market_state.volatility > self.volatility_threshold:
                return RiskDecision(
                    forbid=True,
                    reason=f"市场波动率 {market_state.volatility:.1%} 过高（阈值 {self.volatility_threshold:.0%}）"
                )

            # 3. 检查连续错误
            if self.consecutive_errors >= self.max_consecutive_errors:
                return RiskDecision(
                    forbid=True,
                    reason=f"连续 {self.max_consecutive_errors} 次错误决策，进入冷却"
                )

            # 4. 检查交易时间
            if not self._is_trading_time(current_time):
                now = current_time or datetime.now()
                return RiskDecision(
                    forbid=True,
                    reason=f"当前不在交易时段 ({now.strftime('%H:%M')})"
                )

            # 所有检查通过
            return RiskDecision(forbid=False, reason="风险检查通过")

        except Exception as e:
            logger.error(f"风险检查异常: {e}", exc_info=True)
            # 发生异常时默认禁止交易，安全第一
            return RiskDecision(
                forbid=True,
                reason=f"风险检查异常: {str(e)}"
            )

    def record_error(self):
        """记录错误决策"""
        self.consecutive_errors += 1
        logger.warning(f"记录错误决策，连续错误次数: {self.consecutive_errors}")

    def record_success(self):
        """记录成功决策，重置错误计数器"""
        if self.consecutive_errors > 0:
            logger.info(f"成功决策，重置连续错误计数器（之前: {self.consecutive_errors}）")
        self.consecutive_errors = 0

    def _get_daily_loss_ratio(self, account_state: "AccountState") -> Optional[float]:
        """
        获取当日亏损比例

        Args:
            account_state: 账户状态

        Returns:
            Optional[float]: 亏损比例（0-1），如果无法计算则返回 None
        """
        try:
            # 尝试从 account_state 获取 daily_loss_ratio
            if hasattr(account_state, 'daily_loss_ratio'):
                loss_ratio = account_state.daily_loss_ratio
                if loss_ratio is not None:
                    return loss_ratio

            # 如果没有该字段或值为 None，从 total_value 和 initial_cash 计算
            if hasattr(account_state, 'total_value') and hasattr(account_state, 'initial_cash'):
                initial = account_state.initial_cash
                current = account_state.total_value
                if initial > 0:
                    loss_ratio = (initial - current) / initial
                    return max(0, loss_ratio)

            return None
        except Exception as e:
            logger.warning(f"计算单日亏损比例失败: {e}")
            return None

    def _is_trading_time(self, current_time: Optional[datetime] = None) -> bool:
        """
        检查当前是否在交易时间内

        交易时间: 9:30-11:30, 13:00-15:00

        Args:
            current_time: 当前时间（可选）

        Returns:
            bool: 是否在交易时间
        """
        now = current_time or datetime.now()
        hour = now.hour
        minute = now.minute

        # 开盘前 9:30 前
        if hour < 9 or (hour == 9 and minute < 30):
            return False

        # 收盘后 15:00 后
        if hour >= 15:
            return False

        # 中午休 11:30-13:00
        if hour == 11 and minute >= 30:
            return False
        if hour == 12:
            return False
        if hour == 13 and minute == 0:
            return False

        return True