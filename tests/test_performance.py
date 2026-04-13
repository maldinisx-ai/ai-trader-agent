# -*- coding: utf-8 -*-
"""
测试性能指标计算
"""

import pytest
import numpy as np
from typing import Dict, Any

# 确保模块被导入以正确收集覆盖率
import src.performance
from core.schemas import QuoteData
from src.performance import PerformanceMetrics, BacktestReport, calculate_benchmark_return, calculate_beta


class TestPerformanceMetrics:
    """测试性能指标"""

    def test_init_empty_trades(self):
        """测试初始化 - 空交易"""
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=[])
        assert metrics.initial_cash == 100000.0
        assert metrics.trades == []
        assert len(metrics._equity_curve) == 1
        assert metrics._equity_curve[0] == 100000.0

    def test_init_with_trades(self):
        """测试初始化 - 带交易"""
        trades = [
            {"pnl": 1000.0},
            {"pnl": -500.0},
            {"pnl": 200.0}
        ]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)
        assert len(metrics._equity_curve) == 4  # 初始值 + 3笔交易

    def test_build_equity_curve(self):
        """测试构建权益曲线"""
        trades = [
            {"pnl": 1000.0},
            {"pnl": -500.0}
        ]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)

        expected_curve = [100000.0, 101000.0, 100500.0]
        assert metrics._equity_curve == expected_curve


class TestPerformanceMetricsReturns:
    """测试收益率计算"""

    def test_total_return_positive(self):
        """测试总收益率（盈利）"""
        trades = [{"pnl": 10000.0}]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)

        total_return = metrics.total_return()
        assert total_return == 0.1  # 10%

    def test_total_return_negative(self):
        """测试总收益率（亏损）"""
        trades = [{"pnl": -10000.0}]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)

        total_return = metrics.total_return()
        assert total_return == -0.1  # -10%

    def test_total_return_zero(self):
        """测试总收益率（零）"""
        trades = [{"pnl": 0}]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)

        total_return = metrics.total_return()
        assert total_return == 0.0

    def test_annualized_return(self):
        """测试年化收益率"""
        trades = [{"pnl": 10000.0}]  # 10%收益
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)

        # 半年（126个交易日）
        ann_return = metrics.annualized_return(days=126)
        expected = (1 + 0.1) ** (365/126) - 1
        assert abs(ann_return - expected) < 0.01

    def test_annualized_return_one_year(self):
        """测试年化收益率（一年）"""
        trades = [{"pnl": 10000.0}]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)

        ann_return = metrics.annualized_return(days=365)
        assert abs(ann_return - 0.1) < 0.01


class TestPerformanceMetricsVolatility:
    """测试波动率"""

    def test_volatility(self):
        """测试波动率计算"""
        trades = [
            {"pnl": 1000.0},
            {"pnl": -500.0},
            {"pnl": 2000.0}
        ]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)

        vol = metrics.volatility()
        assert vol >= 0

    def test_volatility_empty(self):
        """测试空交易的波动率"""
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=[])
        assert metrics.volatility() == 0.0

    def test_volatility_single_trade(self):
        """测试单笔交易的波动率"""
        trades = [{"pnl": 1000.0}]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)
        assert metrics.volatility() == 0.0


class TestPerformanceMetricsSharpeRatio:
    """测试夏普比率"""

    def test_sharpe_ratio(self):
        """测试夏普比率"""
        trades = [
            {"pnl": 10000.0},
            {"pnl": -5000.0},
            {"pnl": 15000.0}
        ]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)

        sharpe = metrics.sharpe_ratio()
        assert sharpe >= 0

    def test_sharpe_ratio_custom_risk_free_rate(self):
        """测试自定义无风险利率"""
        trades = [{"pnl": 10000.0}]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)

        sharpe = metrics.sharpe_ratio(risk_free_rate=0.05)
        assert sharpe >= 0

    def test_sharpe_ratio_zero_volatility(self):
        """测试零波动率的夏普比率"""
        trades = [{"pnl": 10000.0}]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)
        # 单笔交易，波动率为0
        sharpe = metrics.sharpe_ratio()
        assert sharpe == 0.0


class TestPerformanceMetricsMaxDrawdown:
    """测试最大回撤"""

    def test_max_drawdown(self):
        """测试最大回撤"""
        trades = [
            {"pnl": 5000.0},   # 105000
            {"pnl": -15000.0}, # 90000
            {"pnl": 10000.0},  # 100000
            {"pnl": -20000.0}, # 80000
            {"pnl": 5000.0}    # 85000
        ]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)

        max_dd = metrics.max_drawdown()
        # 从105000到80000，回撤23.8%
        assert 0.23 < max_dd < 0.24

    def test_max_drawdown_no_drawdown(self):
        """测试无回撤"""
        trades = [{"pnl": 10000.0}]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)

        max_dd = metrics.max_drawdown()
        assert max_dd == 0.0


class TestPerformanceMetricsWinRate:
    """测试胜率"""

    def test_win_rate_all_win(self):
        """测试全胜"""
        trades = [
            {"pnl": 1000.0},
            {"pnl": 500.0},
            {"pnl": 200.0}
        ]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)
        assert metrics.win_rate() == 1.0

    def test_win_rate_mix(self):
        """测试混合结果"""
        trades = [
            {"pnl": 1000.0},
            {"pnl": -500.0},
            {"pnl": 500.0}
        ]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)
        assert abs(metrics.win_rate() - 2/3) < 0.01

    def test_win_rate_all_lose(self):
        """测试全败"""
        trades = [
            {"pnl": -1000.0},
            {"pnl": -500.0}
        ]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)
        assert metrics.win_rate() == 0.0

    def test_win_rate_empty(self):
        """测试空交易"""
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=[])
        assert metrics.win_rate() == 0.0


class TestPerformanceMetricsProfitFactor:
    """测试盈亏比"""

    def test_profit_factor(self):
        """测试盈亏比"""
        trades = [
            {"pnl": 1000.0},
            {"pnl": -500.0},
            {"pnl": 200.0},
            {"pnl": -100.0}
        ]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)

        pf = metrics.profit_factor()
        # 总盈利1200，总亏损600，盈亏比2.0
        assert abs(pf - 2.0) < 0.01

    def test_profit_factor_no_losses(self):
        """测试无亏损"""
        trades = [{"pnl": 1000.0}]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)
        assert metrics.profit_factor() == 999.0

    def test_profit_factor_no_wins(self):
        """测试无盈利"""
        trades = [{"pnl": -1000.0}]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)
        assert metrics.profit_factor() == 0.0


class TestPerformanceMetricsAverage:
    """测试平均值"""

    def test_average_win(self):
        """测试平均盈利"""
        trades = [
            {"pnl": 1000.0},
            {"pnl": -500.0},
            {"pnl": 2000.0}
        ]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)

        avg_win = metrics.average_win()
        # (1000 + 2000) / 2 = 1500
        assert abs(avg_win - 1500.0) < 0.01

    def test_average_loss(self):
        """测试平均(平均)亏损"""
        trades = [
            {"pnl": 1000.0},
            {"pnl": -500.0},
            {"pnl": -1000.0}
        ]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)

        avg_loss = metrics.average_loss()
        # (500 + 1000) / 2 = 750
        assert abs(avg_loss - 750.0) < 0.01

    def test_average_win_empty(self):
        """测试无盈利时的平均"""
        trades = [{"pnl": -1000.0}]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)
        assert metrics.average_win() == 0.0

    def test_average_loss_empty(self):
        """测试无亏损时的平均(平均)"""
        trades = [{"pnl": 1000.0}]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)
        assert metrics.average_loss() == 0.0


class TestPerformanceMetricsSummary:
    """测试性能摘要"""

    def test_get_summary(self):
        """测试获取摘要"""
        trades = [
            {"pnl": 1000.0},
            {"pnl": -500.0},
            {"pnl": 2000.0}
        ]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)

        summary = metrics.get_summary()

        assert summary["initial_cash"] == 100000.0
        assert summary["total_trades"] == 3
        assert "total_return" in summary
        assert "sharpe_ratio" in summary
        assert "max_drawdown" in summary
        assert "win_rate" in summary
        assert "profit_factor" in summary


class TestBacktestReport:
    """测试回测报告"""

    def test_init(self):
        """测试初始化"""
        trades = [{"pnl": 1000.0}]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)
        report = BacktestReport(performance=metrics)

        assert report.performance == metrics
        assert report.metadata == {}

    def test_init_with_metadata(self):
        """测试带元数据初始化"""
        trades = [{"pnl": 1000.0}]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)

        metadata = {
            "strategy_name": "测试策略",
            "backtest_period": "2024-01-01 至 2024-12-31"
        }
        report = BacktestReport(performance=metrics, metadata=metadata)

        assert report.metadata["strategy_name"] == "测试策略"

    def test_generate_text(self):
        """测试生成文本报告"""
        trades = [{"pnl": 10000.0}]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)
        report = BacktestReport(performance=metrics)

        text = report.generate_text()
        assert "回测报告" in text
        assert "初始资金" in text
        assert "总收益率" in text
        assert "夏普比率" in text

    def test_generate_dict(self):
        """测试生成字典报告"""
        trades = [{"pnl": 10000.0}]
        metrics = PerformanceMetrics(initial_cash=100000.0, trades=trades)

        metadata = {"strategy_name": "测试策略"}
        report = BacktestReport(performance=metrics, metadata=metadata)

        dict_report = report.generate_dict()
        assert dict_report["initial_cash"] == 100000.0
        assert dict_report["strategy_name"] == "测试策略"
        assert "total_return" in dict_report


class TestBenchmarkCalculations:
    """测试基准计算"""

    def test_calculate_benchmark_return_up(self):
        """测试计算基准收益（上涨）"""
        quotes = [
            QuoteData(symbol="600519", name="贵州茅台", price=100.0, change=0, volume=1000, amount=100000),
            QuoteData(symbol="600519", name="贵州茅台", price=110.0, change=10.0, volume=1000, amount=110000)
        ]

        benchmark_return = calculate_benchmark_return(quotes)
        assert abs(benchmark_return - 0.1) < 0.01  # 10%

    def test_calculate_benchmark_return_down(self):
        """测试计算基准收益（下跌）"""
        quotes = [
            QuoteData(symbol="600519", name="贵州茅台", price=100.0, change=0, volume=1000, amount=100000),
            QuoteData(symbol="600519", name="贵州茅台", price=90.0, change=-10.0, volume=1000, amount=90000)
        ]

        benchmark_return = calculate_benchmark_return(quotes)
        assert abs(benchmark_return + 0.1) < 0.01  # -10%

    def test_calculate_benchmark_return_insufficient(self):
        """测试计算基准收益（数据不足）"""
        quotes = [QuoteData(symbol="600519", name="贵州茅台", price=100.0, change=0, volume=1000, amount=100000)]
        benchmark_return = calculate_benchmark_return(quotes)
        assert benchmark_return == 0.0

    def test_calculate_benchmark_return_empty(self):
        """测试计算基准收益（空数据）"""
        benchmark_return = calculate_benchmark_return([])
        assert benchmark_return == 0.0

    def test_calculate_beta(self):
        """测试计算Beta"""
        portfolio_returns = [0.05, -0.02, 0.03, 0.01]
        benchmark_returns = [0.04, -0.01, 0.02, 0.03]

        beta = calculate_beta(portfolio_returns, benchmark_returns)
        # Beta应该接近1（因为相关性高）
        assert 0.5 < beta < 1.5

    def test_calculate_beta_zero_variance(self):
        """测试计算Beta（零方差）"""
        portfolio_returns = [0.01, 0.01, 0.01]
        benchmark_returns = [0.01, 0.01, 0.01]

        beta = calculate_beta(portfolio_returns, benchmark_returns)
        assert beta == 0.0

    def test_calculate_beta_mismatched_length(self):
        """测试计算Beta（长度不匹配）"""
        portfolio_returns = [0.01, 0.02]
        benchmark_returns = [0.01]

        beta = calculate_beta(portfolio_returns, benchmark_returns)
        assert beta == 0.0

    def test_calculate_beta_empty(self):
        """测试计算Beta（空数据）"""
        beta = calculate_beta([], [])
        assert beta == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
