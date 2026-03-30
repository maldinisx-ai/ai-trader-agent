# -*- coding: utf-8 -*-
"""
性能指标计算

计算回测策略的性能指标：收益率、夏普比率、最大回撤等。
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import numpy as np

from core.schemas import QuoteData


logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """回测性能指标"""

    def __init__(self, initial_cash: float, trades: List[Dict[str, Any]]):
        """
        初始化性能指标

        Args:
            initial_cash: 初始资金
            trades: 交易记录列表
        """
        self.initial_cash = initial_cash
        self.trades = trades
        self._equity_curve = self._build_equity_curve()

    def _build_equity_curve(self) -> List[float]:
        """构建权益曲线"""
        equity = [self.initial_cash]

        for trade in self.trades:
            pnl = trade.get("pnl", 0)
            equity.append(equity[-1] + pnl)

        return equity

    def total_return(self) -> float:
        """总收益率"""
        if not self._equity_curve:
            return 0.0
        final_value = self._equity_curve[-1]
        return (final_value - self.initial_cash) / self.initial_cash

    def annualized_return(self, days: int) -> float:
        """
        年化收益率

        Args:
            days: 回测天数
        """
        total_return = self.total_return()
        years = days / 365.0
        if years == 0:
            return 0.0
        return (1 + total_return) ** (1 / years) - 1

    def volatility(self) -> float:
        """波动率（标准差）"""
        if len(self._equity_curve) < 2:
            return 0.0

        returns = []
        for i in range(1, len(self._equity_curve)):
            ret = (self._equity_curve[i] - self._equity_curve[i - 1]) / self._equity_curve[i - 1]
            returns.append(ret)

        return np.std(returns) * np.sqrt(252)  # 年化波动率

    def sharpe_ratio(self, risk_free_rate: float = 0.03) -> float:
        """
        夏普比率

        Args:
            risk_free_rate: 无风险利率 (默认3%)
        """
        ann_return = self.annualized_return(len(self._equity_curve))
        vol = self.volatility()

        if vol == 0:
            return 0.0

        return (ann_return - risk_free_rate) / vol

    def max_drawdown(self) -> float:
        """最大回撤"""
        if not self._equity_curve:
            return 0.0

        peak = self._equity_curve[0]
        max_dd = 0.0

        for value in self._equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def win_rate(self) -> float:
        """胜率"""
        if not self.trades:
            return 0.0

        winning_trades = sum(1 for t in self.trades if t.get("pnl", 0) > 0)
        return winning_trades / len(self.trades)

    def profit_factor(self) -> float:
        """盈亏比"""
        total_profit = sum(t.get("pnl", 0) for t in self.trades if t.get("pnl", 0) > 0)
        total_loss = abs(sum(t.get("pnl", 0) for t in self.trades if t.get("pnl", 0) < 0))

        if total_loss == 0:
            return 999.0 if total_profit > 0 else 0.0

        return total_profit / total_loss

    def average_win(self) -> float:
        """平均盈利"""
        wins = [t.get("pnl", 0) for t in self.trades if t.get("pnl", 0) > 0]
        return np.mean(wins) if wins else 0.0

    def average_loss(self) -> float:
        """平均亏损（返回正数，表示亏损金额）"""
        losses = [abs(t.get("pnl", 0)) for t in self.trades if t.get("pnl", 0) < 0]
        return np.mean(losses) if losses else 0.0

    def total_trades(self) -> int:
        """总交易次数"""
        return len(self.trades)

    def get_summary(self, days: int = 252) -> Dict[str, Any]:
        """
        获取性能摘要

        Args:
            days: 回测天数 (默认252个交易日)

        Returns:
            性能指标字典
        """
        return {
            "initial_cash": self.initial_cash,
            "final_value": self._equity_curve[-1] if self._equity_curve else self.initial_cash,
            "total_return": self.total_return(),
            "annualized_return": self.annualized_return(days),
            "volatility": self.volatility(),
            "sharpe_ratio": self.sharpe_ratio(),
            "max_drawdown": self.max_drawdown(),
            "win_rate": self.win_rate(),
            "profit_factor": self.profit_factor(),
            "average_win": self.average_win(),
            "average_loss": self.average_loss(),
            "total_trades": self.total_trades(),
        }


class BacktestReport:
    """回测报告生成器"""

    def __init__(self, performance: PerformanceMetrics, metadata: Optional[Dict[str, Any]] = None):
        """
        初始化报告生成器

        Args:
            performance: 性能指标对象
            metadata: 元数据（策略名称、回测期间等）
        """
        self.performance = performance
        self.metadata = metadata or {}

    def generate_text(self) -> str:
        """生成文本报告"""
        summary = self.performance.get_summary()

        report = []
        report.append("=" * 60)
        report.append("回测报告")
        report.append("=" * 60)

        # 元数据
        if self.metadata:
            report.append("\n回测参数:")
            for key, value in self.metadata.items():
                report.append(f"  {key}: {value}")

        # 性能指标
        report.append("\n性能指标:")
        report.append(f"  初始资金: ¥{summary['initial_cash']:,.2f}")
        report.append(f"  最终资金: ¥{summary['final_value']:,.2f}")
        report.append(f"  总收益率: {summary['total_return']*100:.2f}%")
        report.append(f"  年化收益率: {summary['annualized_return']*100:.2f}%")
        report.append(f"  波动率: {summary['volatility']*100:.2f}%")
        report.append(f"  夏普比率: {summary['sharpe_ratio']:.2f}")
        report.append(f"  最大回撤: {summary['max_drawdown']*100:.2f}%")

        # 交易统计
        report.append("\n交易统计:")
        report.append(f"  总交易次数: {summary['total_trades']}")
        report.append(f"  胜率: {summary['win_rate']*100:.2f}%")
        report.append(f"  盈亏比: {summary['profit_factor']:.2f}")
        report.append(f"  平均盈利: ¥{summary['average_win']:,.2f}")
        report.append(f"  平均亏损: ¥{summary['average_loss']:,.2f}")

        report.append("\n" + "=" * 60)

        return "\n".join(report)

    def generate_dict(self) -> Dict[str, Any]:
        """生成字典格式报告"""
        summary = self.performance.get_summary()
        summary.update(self.metadata)
        return summary


def calculate_benchmark_return(quotes: List[QuoteData]) -> float:
    """
    计算基准收益率（买入持有）

    Args:
        quotes: 行情数据

    Returns:
        基准收益率
    """
    if len(quotes) < 2:
        return 0.0

    first_price = quotes[0].price
    last_price = quotes[-1].price

    return (last_price - first_price) / first_price


def calculate_beta(portfolio_returns: List[float], benchmark_returns: List[float]) -> float:
    """
    计算 Beta 系数

    Args:
        portfolio_returns: 组合收益率序列
        benchmark_returns: 基准收益率序列

    Returns:
        Beta 系数
    """
    if len(portfolio_returns) != len(benchmark_returns) or len(portfolio_returns) < 2:
        return 0.0

    covariance = np.cov(portfolio_returns, benchmark_returns)[0][1]
    benchmark_variance = np.var(benchmark_returns, ddof=1)  # 使用样本方差（除以 N-1）

    if benchmark_variance == 0:
        return 0.0

    return covariance / benchmark_variance
