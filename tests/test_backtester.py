# -*- coding: utf-8 -*-
"""
回测系统测试

测试回测引擎、技术指标和性能指标计算。
"""

import pytest
from datetime import datetime, timedelta
from typing import List, Optional

from src.indicators import TechnicalIndicators, QuoteDataAnalyzer
from src.performance import PerformanceMetrics, BacktestReport, calculate_benchmark_return
from src.backtester import BacktestEngine, run_backtest
from core.schemas import QuoteData, Decision


# ============================================================================
# TechnicalIndicators Tests
# ============================================================================

class TestTechnicalIndicators:
    """技术指标测试"""

    def test_sma(self):
        """测试简单移动平均线"""
        prices = [10, 12, 14, 16, 18, 20]
        result = TechnicalIndicators.sma(prices, 3)

        assert result[0] is None
        assert result[1] is None
        assert abs(result[2] - 12) < 0.01  # (10+12+14)/3
        assert abs(result[3] - 14) < 0.01  # (12+14+16)/3
        assert abs(result[4] - 16) < 0.01  # (14+16+18)/3
        assert abs(result[5] - 18) < 0.01  # (16+18+20)/3

    def test_sma_insufficient_data(self):
        """测试数据不足"""
        prices = [10, 12]
        result = TechnicalIndicators.sma(prices, 5)

        assert all(r is None for r in result)

    def test_ema(self):
        """测试指数移动平均线"""
        prices = [10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30]
        result = TechnicalIndicators.ema(prices, 5)

        # 前面应该有 None 值
        assert result[0] is None

        # EMA 应该接近价格趋势
        valid_values = [r for r in result if r is not None]
        assert len(valid_values) > 0
        assert valid_values[-1] > valid_values[0]  # 上升趋势

    def test_rsi(self):
        """测试相对强弱指标"""
        # 构造上涨趋势
        prices = [10 + i for i in range(20)]
        result = TechnicalIndicators.rsi(prices, 14)

        # 前面应该有 None 值
        assert result[0] is None

        # 上升趋势应该有较高的 RSI
        valid_values = [r for r in result if r is not None]
        assert len(valid_values) > 0
        assert valid_values[-1] > 50  # 强势

    def test_rsi_range(self):
        """测试 RSI 范围"""
        prices = [10 + (i % 10) for i in range(100)]  # 震荡
        result = TechnicalIndicators.rsi(prices, 14)

        valid_values = [r for r in result if r is not None]
        for rsi in valid_values:
            assert 0 <= rsi <= 100

    def test_bollinger_bands(self):
        """测试布林带"""
        prices = [10 + i * 0.1 for i in range(30)]
        upper, middle, lower = TechnicalIndicators.bollinger_bands(prices, 20, 2)

        # 检查上轨 > 中轨 > 下轨
        for i in range(len(prices)):
            if upper[i] is not None:
                assert upper[i] > middle[i] > lower[i]

    def test_macd(self):
        """测试 MACD"""
        prices = [10 + i * 0.1 for i in range(50)]
        macd, signal, histogram = TechnicalIndicators.macd(prices)

        # 检查长度一致
        assert len(macd) == len(signal) == len(histogram) == len(prices)

        # 检查有效值
        valid_macd = [m for m in macd if m is not None]
        assert len(valid_macd) > 0


class TestQuoteDataAnalyzer:
    """行情数据分析器测试"""

    @pytest.fixture
    def sample_quotes(self) -> List[QuoteData]:
        """创建样本行情数据"""
        quotes = []
        base_price = 100.0
        base_date = datetime(2024, 1, 1)

        for i in range(50):
            price = base_price + i * 0.5
            quotes.append(QuoteData(
                symbol="600519",
                name="Test Stock",
                price=price,
                change=0.5,
                volume=1000000,
                amount=price * 1000000,
                high=price * 1.01,
                low=price * 0.99,
                upper_limit=price * 1.1,
                lower_limit=price * 0.9,
            ))

        return quotes

    def test_initialization(self, sample_quotes):
        """测试初始化"""
        analyzer = QuoteDataAnalyzer(sample_quotes)

        assert analyzer.quotes == sample_quotes
        assert len(analyzer._prices) == 50

    def test_get_sma(self, sample_quotes):
        """测试获取 SMA"""
        analyzer = QuoteDataAnalyzer(sample_quotes)
        sma = analyzer.get_sma(10)

        assert len(sma) == 50
        assert sma[0] is None
        assert sma[-1] is not None

    def test_get_rsi(self, sample_quotes):
        """测试获取 RSI"""
        analyzer = QuoteDataAnalyzer(sample_quotes)
        rsi = analyzer.get_rsi()

        assert len(rsi) == 50

        # 检查有效值范围
        valid_values = [r for r in rsi if r is not None]
        for r in valid_values:
            assert 0 <= r <= 100

    def test_get_latest_signals(self, sample_quotes):
        """测试获取最新信号"""
        analyzer = QuoteDataAnalyzer(sample_quotes)
        signals = analyzer.get_latest_signals()

        assert isinstance(signals, dict)
        assert "rsi" in signals
        assert "macd" in signals
        assert "trend" in signals


# ============================================================================
# PerformanceMetrics Tests
# ============================================================================

class TestPerformanceMetrics:
    """性能指标测试"""

    @pytest.fixture
    def sample_trades(self) -> List[dict]:
        """创建样本交易记录"""
        return [
            {"pnl": 1000, "date": "2024-01-01"},
            {"pnl": -500, "date": "2024-01-02"},
            {"pnl": 1500, "date": "2024-01-03"},
            {"pnl": 2000, "date": "2024-01-04"},
            {"pnl": -800, "date": "2024-01-05"},
        ]

    def test_initialization(self, sample_trades):
        """测试初始化"""
        metrics = PerformanceMetrics(initial_cash=100000, trades=sample_trades)

        assert metrics.initial_cash == 100000
        assert len(metrics._equity_curve) == 6  # 初始 + 5笔交易

    def test_total_return(self, sample_trades):
        """测试总收益率"""
        metrics = PerformanceMetrics(initial_cash=100000, trades=sample_trades)

        total_return = metrics.total_return()
        expected = (1000 - 500 + 1500 + 2000 - 800) / 100000

        assert abs(total_return - expected) < 0.01

    def test_win_rate(self, sample_trades):
        """测试胜率"""
        metrics = PerformanceMetrics(initial_cash=100000, trades=sample_trades)

        win_rate = metrics.win_rate()
        # 5笔交易中3笔盈利
        assert abs(win_rate - 0.6) < 0.01

    def test_profit_factor(self, sample_trades):
        """测试盈亏比"""
        metrics = PerformanceMetrics(initial_cash=100000, trades=sample_trades)

        pf = metrics.profit_factor()
        # 总盈利4500，总亏损1300，盈亏比=4500/1300≈3.46
        assert abs(pf - 3.46) < 0.1

    def test_max_drawdown(self):
        """测试最大回撤"""
        trades = [
            {"pnl": 10000},
            {"pnl": -5000},
            {"pnl": -8000},  # 回撤
            {"pnl": 3000},
        ]

        metrics = PerformanceMetrics(initial_cash=100000, trades=trades)
        dd = metrics.max_drawdown()

        # 最大回撤应该发生在第三笔交易后
        assert dd > 0

    def test_get_summary(self, sample_trades):
        """测试获取摘要"""
        metrics = PerformanceMetrics(initial_cash=100000, trades=sample_trades)

        summary = metrics.get_summary(days=5)

        assert "initial_cash" in summary
        assert "final_value" in summary
        assert "total_return" in summary
        assert "sharpe_ratio" in summary
        assert "max_drawdown" in summary
        assert "win_rate" in summary


class TestBacktestReport:
    """回测报告测试"""

    @pytest.fixture
    def sample_performance(self):
        """创建样本性能数据"""
        trades = [
            {"pnl": 1000, "date": "2024-01-01"},
            {"pnl": -500, "date": "2024-01-02"},
            {"pnl": 1500, "date": "2024-01-03"},
        ]
        return PerformanceMetrics(initial_cash=100000, trades=trades)

    def test_generate_text(self, sample_performance):
        """测试生成文本报告"""
        report = BacktestReport(
            performance=sample_performance,
            metadata={"strategy": "test", "period": "2024-01-01 to 2024-01-03"}
        )

        text = report.generate_text()

        assert "回测报告" in text
        assert "初始资金" in text
        assert "总收益率" in text
        assert "夏普比率" in text

    def test_generate_dict(self, sample_performance):
        """测试生成字典报告"""
        report = BacktestReport(
            performance=sample_performance,
            metadata={"strategy": "test"}
        )

        result = report.generate_dict()

        assert "total_return" in result
        assert "sharpe_ratio" in result
        assert result["strategy"] == "test"


# ============================================================================
# BacktestEngine Tests
# ============================================================================

class TestBacktestEngine:
    """回测引擎测试"""

    def test_initialization(self):
        """测试初始化"""
        engine = BacktestEngine(
            initial_cash=100000,
            start_date="2024-01-01",
            end_date="2024-01-31",
            symbols=["600519"],
        )

        assert engine.initial_cash == 100000
        assert engine.start_date == datetime(2024, 1, 1)
        assert engine.end_date == datetime(2024, 1, 31)
        assert engine.symbols == ["600519"]

    def test_load_mock_data(self):
        """测试加载模拟数据"""
        engine = BacktestEngine(
            initial_cash=100000,
            start_date="2024-01-01",
            end_date="2024-01-10",
            symbols=["600519"],
        )

        success = engine.load_historical_data()

        assert success is True
        assert "600519" in engine.historical_data
        assert len(engine.historical_data["600519"]) > 0

    def test_run_backtest(self):
        """测试运行回测"""
        engine = BacktestEngine(
            initial_cash=100000,
            start_date="2024-01-01",
            end_date="2024-01-10",
            symbols=["600519"],
        )

        result = engine.run()

        assert isinstance(result, dict)
        assert "initial_cash" in result
        assert "final_value" in result
        assert "total_return" in result
        assert "total_trades" in result


# ============================================================================
# Integration Tests
# ============================================================================

class TestBacktesterIntegration:
    """回测系统集成测试"""

    def test_run_backtest_function(self):
        """测试 run_backtest 函数"""
        result = run_backtest(
            start_date="2024-01-01",
            end_date="2024-01-10",
            symbols=["600519"],
            initial_cash=100000,
        )

        assert isinstance(result, dict)
        assert "total_return" in result
        assert "sharpe_ratio" in result
        assert "max_drawdown" in result

    def test_custom_strategy(self):
        """测试自定义策略"""
        def custom_strategy(analyzer, account_info):
            # 简单策略：总是买入
            if analyzer.quotes:
                quote = analyzer.quotes[-1]
                return Decision(
                    action="buy",
                    symbol=quote.symbol,
                    quantity=100,
                    price=quote.price,
                    reasoning="测试策略",
                    confidence=0.5,
                )
            return None

        result = run_backtest(
            start_date="2024-01-01",
            end_date="2024-01-05",
            symbols=["600519"],
            initial_cash=100000,
            strategy=custom_strategy,
        )

        assert isinstance(result, dict)
        assert result["total_trades"] > 0
