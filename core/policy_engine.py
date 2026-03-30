# -*- coding: utf-8 -*-
"""
风控引擎

多层风险控制机制（含优先级）。

风控规则优先级（从高到低）:
- P0: 资金检查
- P1: 熔断机制
- P2: 黑名单
- P3: 交易时间/涨跌停/停牌
- P4: 仓位限制
- P5: 冷却机制
- P6: 单日限额
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Optional, Dict

from core.schemas import (
    Order, QuoteData, PolicyResult, PolicyPriority,
    OrderSide, SurvivalLevel, OrderStatus,
)


class BasePolicy(ABC):
    """风控策略基类"""

    def __init__(self, priority: PolicyPriority):
        self.priority = priority

    @abstractmethod
    def check(self, order: Order, **kwargs) -> PolicyResult:
        """
        检查订单是否符合此策略

        Args:
            order: 待检查订单
            **kwargs: 额外参数（如 quote, last_trade_time 等）

        Returns:
            PolicyResult: 检查结果
        """
        pass


class FundCheckPolicy(BasePolicy):
    """
    P0: 资金检查

    规则: 买入金额 < 可用资金
    """

    def __init__(self, cash: float):
        super().__init__(PolicyPriority.P0_FUND_CHECK)
        self.cash = cash

    def check(self, order: Order, **kwargs) -> PolicyResult:
        if order.side == OrderSide.SELL:
            return PolicyResult(allowed=True, priority=self.priority)

        required = order.quantity * order.price
        if required > self.cash:
            return PolicyResult(
                allowed=False,
                reason=f"资金不足: 需要 {required:.2f}，可用 {self.cash:.2f}",
                policy="FundCheckPolicy",
                priority=self.priority,
            )

        return PolicyResult(allowed=True, priority=self.priority)


class CircuitBreakerPolicy(BasePolicy):
    """
    P1: 熔断机制

    规则: 单日亏损>5%或触发熔断时暂停交易1小时
    """

    def __init__(self, daily_pnl_ratio: float, circuit_triggered: bool,
                 circuit_pause_until: Optional[datetime] = None):
        super().__init__(PolicyPriority.P1_CIRCUIT_BREAKER)
        self.daily_pnl_ratio = daily_pnl_ratio
        self.circuit_triggered = circuit_triggered
        self.circuit_pause_until = circuit_pause_until

    def check(self, order: Order, **kwargs) -> PolicyResult:
        # 检查是否在熔断暂停期
        if self.circuit_pause_until and datetime.now() < self.circuit_pause_until:
            return PolicyResult(
                allowed=False,
                reason=f"熔断暂停中，直至 {self.circuit_pause_until.strftime('%H:%M:%S')}",
                policy="CircuitBreakerPolicy",
                priority=self.priority,
            )

        # 检查单日亏损是否触发熔断
        if self.circuit_triggered or self.daily_pnl_ratio < -0.05:  # 亏损超过5%
            return PolicyResult(
                allowed=False,
                reason=f"触发熔断: 单日亏损 {self.daily_pnl_ratio:.1%}",
                policy="CircuitBreakerPolicy",
                priority=self.priority,
            )

        return PolicyResult(allowed=True, priority=self.priority)


class BlacklistPolicy(BasePolicy):
    """
    P2: 黑名单

    规则: ST股、*ST股禁止买入
    """

    def __init__(self):
        super().__init__(PolicyPriority.P2_BLACKLIST)

    def check(self, order: Order, **kwargs) -> PolicyResult:
        # 卖出不受限制
        if order.side == OrderSide.SELL:
            return PolicyResult(allowed=True, priority=self.priority)

        symbol = order.symbol.upper()

        # 检查ST标记
        if "ST" in symbol or "*" in symbol:
            return PolicyResult(
                allowed=False,
                reason=f"黑名单股票: {symbol}（ST股票禁止买入）",
                policy="BlacklistPolicy",
                priority=self.priority,
            )

        return PolicyResult(allowed=True, priority=self.priority)


class TradingRulesPolicy(BasePolicy):
    """
    P3: 交易规则

    规则:
    - 交易时间: 9:30-15:00
    - 涨跌停: 涨停禁止买入、跌停禁止卖出
    - 停牌: 停牌股票禁止交易
    """

    TRADING_START = datetime.strptime("09:30:00", "%H:%M:%S").time()
    TRADING_END = datetime.strptime("15:00:00", "%H:%M:%S").time()

    def __init__(self):
        super().__init__(PolicyPriority.P3_TRADING_RULES)

    def check(self, order: Order, quote: Optional[QuoteData] = None, **kwargs) -> PolicyResult:
        # 检查交易时间（如果提供当前时间）
        current_time = kwargs.get("current_time")
        if current_time:
            if not (self.TRADING_START <= current_time <= self.TRADING_END):
                # 非交易时间
                return PolicyResult(
                    allowed=False,
                    reason=f"非交易时间: {current_time}（需在 09:30-15:00）",
                    policy="TradingRulesPolicy",
                    priority=self.priority,
                )

        # 检查停牌
        if quote and quote.is_suspended:
            return PolicyResult(
                allowed=False,
                reason=f"股票停牌: {quote.name}",
                policy="TradingRulesPolicy",
                priority=self.priority,
            )

        # 检查涨跌停
        if quote and order.price:
            if order.side == OrderSide.BUY and quote.upper_limit:
                if order.price >= quote.upper_limit:
                    return PolicyResult(
                        allowed=False,
                        reason=f"涨停无法买入: 涨停价 {quote.upper_limit}",
                        policy="TradingRulesPolicy",
                        priority=self.priority,
                    )
            elif order.side == OrderSide.SELL and quote.lower_limit:
                if order.price <= quote.lower_limit:
                    return PolicyResult(
                        allowed=False,
                        reason=f"跌停无法卖出: 跌停价 {quote.lower_limit}",
                        policy="TradingRulesPolicy",
                        priority=self.priority,
                    )

        return PolicyResult(allowed=True, priority=self.priority)


class PositionLimitPolicy(BasePolicy):
    """
    P4: 仓位限制

    规则: 单只股票不超过最大仓位比例
    """

    def __init__(self, max_position_ratio: float, total_value: float,
                 current_positions: Optional[dict] = None):
        super().__init__(PolicyPriority.P4_POSITION_LIMIT)
        self.max_position_ratio = max_position_ratio
        self.total_value = total_value
        self.current_positions = current_positions or {}

    def check(self, order: Order, **kwargs) -> PolicyResult:
        # 卖出不受仓位限制
        if order.side == OrderSide.SELL:
            return PolicyResult(allowed=True, priority=self.priority)

        # 计算订单金额
        order_value = order.quantity * order.price

        # 计算当前持仓该股票的市值
        current_position_value = self.current_positions.get(order.symbol, 0)

        # 计算新仓位
        new_position_value = current_position_value + order_value
        new_position_ratio = new_position_value / self.total_value if self.total_value > 0 else 0

        if new_position_ratio > self.max_position_ratio:
            return PolicyResult(
                allowed=False,
                reason=f"超过仓位限制: 新仓位 {new_position_ratio:.1%} > 最大 {self.max_position_ratio:.1%}",
                policy="PositionLimitPolicy",
                priority=self.priority,
            )

        return PolicyResult(allowed=True, priority=self.priority)


class CooldownPolicy(BasePolicy):
    """
    P5: 冷却机制

    规则: 同一股票30分钟内不能反向交易
    """

    def __init__(self, cooldown_minutes: int = 30):
        super().__init__(PolicyPriority.P5_COOLDOWN)
        self.cooldown_duration = timedelta(minutes=cooldown_minutes)

    def check(self, order: Order, last_trade_time: Optional[datetime] = None,
             last_trade_side: Optional[OrderSide] = None, **kwargs) -> PolicyResult:
        if not last_trade_time or not last_trade_side:
            return PolicyResult(allowed=True, priority=self.priority)

        # 检查是否是同一股票
        # (在实际实现中，需要跟踪每只股票的最后交易时间)

        # 检查是否反向交易
        is_reverse = (
            (order.side == OrderSide.BUY and last_trade_side == OrderSide.SELL) or
            (order.side == OrderSide.SELL and last_trade_side == OrderSide.BUY)
        )

        if is_reverse:
            time_since_last = datetime.now() - last_trade_time
            if time_since_last < self.cooldown_duration:
                remaining = self.cooldown_duration - time_since_last
                return PolicyResult(
                    allowed=False,
                    reason=f"冷却期内: 需等待 {remaining.seconds // 60} 分钟",
                    policy="CooldownPolicy",
                    priority=self.priority,
                )

        return PolicyResult(allowed=True, priority=self.priority)


class DailyLimitPolicy(BasePolicy):
    """
    P6: 单日限额

    规则: 每日最多10笔交易
    """

    def __init__(self, max_daily_trades: int = 10):
        super().__init__(PolicyPriority.P6_DAILY_LIMIT)
        self.max_daily_trades = max_daily_trades

    def check(self, order: Order, daily_trade_count: int = 0, **kwargs) -> PolicyResult:
        if daily_trade_count >= self.max_daily_trades:
            return PolicyResult(
                allowed=False,
                reason=f"超过单日限额: 已交易 {daily_trade_count} 笔，最大 {self.max_daily_trades} 笔",
                policy="DailyLimitPolicy",
                priority=self.priority,
            )

        return PolicyResult(allowed=True, priority=self.priority)


class ScoreThresholdPolicy(BasePolicy):
    """
    P7: 评分阈值拦截

    规则: 评分低于30分的股票禁止买入（防止AI严重幻觉）
    """

    def __init__(self, min_score: int = 30):
        super().__init__(PolicyPriority.P7_SCORE_THRESHOLD)
        self.min_score = min_score

    def check(self, order: Order, stock_score: Optional[int] = None, **kwargs) -> PolicyResult:
        # 卖出不受评分限制
        if order.side == OrderSide.SELL:
            return PolicyResult(allowed=True, priority=self.priority)

        # 如果没有提供评分，跳过检查
        if stock_score is None:
            return PolicyResult(allowed=True, priority=self.priority)

        # 检查评分是否低于阈值
        if stock_score < self.min_score:
            return PolicyResult(
                allowed=False,
                reason=f"评分过低: {stock_score} 分 < 最低 {self.min_score} 分（可能存在严重风险）",
                policy="ScoreThresholdPolicy",
                priority=self.priority,
            )

        return PolicyResult(allowed=True, priority=self.priority)


class CancelOrderPolicy(BasePolicy):
    """
    撤单风控策略

    规则:
    - 已成交订单不能撤单
    - 已拒绝订单不能撤单
    - 已撤销订单不能重复撤单
    """

    def __init__(self):
        super().__init__(priority=PolicyPriority.P3_TRADING_RULES)

    def check(self, order: Order, **kwargs) -> PolicyResult:
        # 检查订单状态
        if order.status == OrderStatus.FILLED:
            return PolicyResult(
                allowed=False,
                reason=f"订单已成交，无法撤单",
                policy="CancelOrderPolicy",
                priority=self.priority,
            )

        if order.status == OrderStatus.REJECTED:
            return PolicyResult(
                allowed=False,
                reason=f"订单已被拒绝，无法撤单",
                policy="CancelOrderPolicy",
                priority=self.priority,
            )

        if order.status == OrderStatus.CANCELLED:
            return PolicyResult(
                allowed=False,
                reason=f"订单已撤销，无需重复撤单",
                policy="CancelOrderPolicy",
                priority=self.priority,
            )

        return PolicyResult(allowed=True, priority=self.priority)


class PolicyEngine:
    """
    风控引擎

    所有风控规则按优先级顺序执行，任何规则失败立即拒绝。
    """

    def __init__(
        self,
        cash: float,
        max_position_ratio: float = 0.30,
        total_value: Optional[float] = None,
        daily_pnl_ratio: float = 0.0,
        circuit_triggered: bool = False,
        circuit_pause_until: Optional[datetime] = None,
        cooldown_minutes: int = 30,
        max_daily_trades: int = 10,
        min_score_threshold: int = 30,
    ):
        """
        初始化风控引擎

        Args:
            cash: 可用资金
            max_position_ratio: 最大仓位比例
            total_value: 总资产
            daily_pnl_ratio: 单日盈亏比例
            circuit_triggered: 是否触发熔断
            circuit_pause_until: 熔断暂停截止时间
            cooldown_minutes: 冷却时间（分钟）
            max_daily_trades: 最大单日交易笔数
            min_score_threshold: 最低评分阈值（P7拦截）
        """
        self.cash = cash
        self.total_value = total_value or cash
        self.max_position_ratio = max_position_ratio
        self.daily_pnl_ratio = daily_pnl_ratio
        self.circuit_triggered = circuit_triggered
        self.circuit_pause_until = circuit_pause_until
        self.cooldown_minutes = cooldown_minutes
        self.max_daily_trades = max_daily_trades

        # 初始化策略
        self.policies: List[BasePolicy] = [
            FundCheckPolicy(cash),
            CircuitBreakerPolicy(daily_pnl_ratio, circuit_triggered, circuit_pause_until),
            BlacklistPolicy(),
            TradingRulesPolicy(),
            PositionLimitPolicy(max_position_ratio, self.total_value),
            CooldownPolicy(cooldown_minutes),
            DailyLimitPolicy(max_daily_trades),
            ScoreThresholdPolicy(min_score_threshold),
        ]

        # 状态跟踪
        self.daily_trade_count = 0
        self.last_trades: dict[str, tuple[datetime, OrderSide]] = {}  # symbol -> (time, side)
        self.stock_scores: dict[str, int] = {}  # symbol -> score (新增)

    def validate_order(
        self,
        order: Order,
        quote: Optional[QuoteData] = None,
        current_time: Optional[datetime.time] = None,
    ) -> PolicyResult:
        """
        按优先级顺序验证订单

        Args:
            order: 待验证订单
            quote: 行情数据（用于涨跌停检查）
            current_time: 当前时间（用于交易时间检查）

        Returns:
            PolicyResult: 验证结果
        """
        # 获取该股票的最后交易信息
        last_trade = self.last_trades.get(order.symbol)
        last_trade_time = last_trade[0] if last_trade else None
        last_trade_side = last_trade[1] if last_trade else None

        # 按优先级执行所有策略
        for policy in sorted(self.policies, key=lambda p: p.priority):
            # 获取股票评分（用于P7拦截）
            stock_score = self.stock_scores.get(order.symbol)

            result = policy.check(
                order,
                quote=quote,
                current_time=current_time,
                last_trade_time=last_trade_time,
                last_trade_side=last_trade_side,
                daily_trade_count=self.daily_trade_count,
                stock_score=stock_score,
            )

            if not result.allowed:
                return result

        return PolicyResult(allowed=True)

    def record_trade(self, order: Order, filled_time: datetime):
        """
        记录已成交的交易

        Args:
            order: 订单
            filled_time: 成交时间
        """
        self.daily_trade_count += 1
        self.last_trades[order.symbol] = (filled_time, order.side)

        # 更新资金和持仓（需要外部调用）
        # 这里只更新计数，实际资金/持仓由 Account 管理

    def update_state(
        self,
        cash: Optional[float] = None,
        total_value: Optional[float] = None,
        daily_pnl_ratio: Optional[float] = None,
        reset_daily_count: bool = False,
    ):
        """
        更新风控引擎状态

        Args:
            cash: 新的资金余额
            total_value: 新的总资产
            daily_pnl_ratio: 新的单日盈亏比例
            reset_daily_count: 是否重置单日计数
        """
        if cash is not None:
            self.cash = cash
            for policy in self.policies:
                if isinstance(policy, FundCheckPolicy):
                    policy.cash = cash

        if total_value is not None:
            self.total_value = total_value
            for policy in self.policies:
                if isinstance(policy, PositionLimitPolicy):
                    policy.total_value = total_value

        if daily_pnl_ratio is not None:
            self.daily_pnl_ratio = daily_pnl_ratio
            for policy in self.policies:
                if isinstance(policy, CircuitBreakerPolicy):
                    policy.daily_pnl_ratio = daily_pnl_ratio

        if reset_daily_count:
            self.daily_trade_count = 0
            self.last_trades.clear()

    def update_stock_scores(self, scores: Dict[str, int]):
        """
        更新股票评分

        Args:
            scores: 股票评分字典 {symbol: score}
        """
        self.stock_scores.update(scores)

    def validate_cancel_order(self, order: Order) -> PolicyResult:
        """
        验证撤单请求

        Args:
            order: 待撤单的订单

        Returns:
            PolicyResult: 验证结果
        """
        # 使用撤单风控策略
        cancel_policy = CancelOrderPolicy()
        return cancel_policy.check(order)
