# -*- coding: utf-8 -*-
"""
策略优化器测试

测试参数优化和 A/B 测试功能。
"""

import pytest
from typing import List, Optional, Dict, Any

from src.strategies.base import BaseStrategy, StrategyConfig, StrategySignal, SignalType
from src.strategies.ma_cross import MACrossStrategy
from src.optimizer import GridSearchOptimizer, ABTester, optimize_strategy, OptimizationResult, ABTestResult
from src.indicators import QuoteDataAnalyzer


# ============================================================================
# Test Strategy
# ============================================================================

class SimpleTestStrategy(BaseStrategy):
    """简单测试策略"""

    def generate_signal(
        self,
        analyzer: QuoteDataAnalyzer,
        account_info: Dict[str, Any],
    ) -> Optional[StrategySignal]:
        """总是买入的测试策略"""
        if not analyzer.quotes:
            return None

        quote = analyzer.quotes[-1]

        # 根据配置决定是否生成信号
        threshold = self.config.get("threshold", 0.5)
        import random
        if random.random() > threshold:
            return None

        quantity = self.get_position_size(quote.price, account_info, 0.30)

        return StrategySignal(
            signal_type=SignalType.BUY,
            symbol=quote.symbol,
            price=quote.price,
            quantity=quantity,
            confidence=0.6,
            reasoning="测试策略",
            metadata={},
        )


# ============================================================================
# GridSearchOptimizer Tests
# ============================================================================

class TestGridSearchOptimizer:
    """网格搜索优化器测试"""

    def test_initialization(self):
        """测试初始化"""
        param_grid = {
            "fast_period": [5, 10],
            "slow_period": [20, 30],
        }

        optimizer = GridSearchOptimizer(
            strategy_class=MACrossStrategy,
            param_grid=param_grid,
            backtest_config={
                "initial_cash": 100000,
                "start_date": "2024-01-01",
                "end_date": "2024-01-05",
                "symbols": ["600519"],
            },
        )

        assert optimizer.strategy_class == MACrossStrategy
        assert optimizer.param_grid == param_grid

    def test_optimize_small_grid(self):
        """测试小规模网格搜索"""
        param_grid = {
            "fast_period": [5],
            "slow_period": [20],
        }

        optimizer = GridSearchOptimizer(
            strategy_class=MACrossStrategy,
            param_grid=param_grid,
            backtest_config={
                "initial_cash": 100000,
                "start_date": "2024-01-01",
                "end_date": "2024-01-03",
                "symbols": ["600519"],
            },
        )

        results = optimizer.optimize()

        assert isinstance(results, list)
        assert len(results) > 0

        # 检查结果格式
        for result in results:
            assert isinstance(result, OptimizationResult)
            assert isinstance(result.config, StrategyConfig)
            assert isinstance(result.metrics, dict)

    def test_optimize_multiple_combinations(self):
        """测试多参数组合优化"""
        param_grid = {
            "fast_period": [5, 10],
            "slow_period": [20, 30],
        }

        optimizer = GridSearchOptimizer(
            strategy_class=MACrossStrategy,
            param_grid=param_grid,
            backtest_config={
                "initial_cash": 100000,
                "start_date": "2024-01-01",
                "end_date": "2024-01-03",
                "symbols": ["600519"],
            },
        )

        results = optimizer.optimize()

        # 应该有 2*2 = 4 个组合
        assert len(results) <= 4

        # 检查结果排序
        if len(results) >= 2:
            assert results[0].score >= results[1].score


# ============================================================================
# ABTester Tests
# ============================================================================

class TestABTester:
    """A/B 测试器测试"""

    def test_initialization(self):
        """测试初始化"""
        backtest_config = {
            "initial_cash": 100000,
            "start_date": "2024-01-01",
            "end_date": "2024-01-05",
            "symbols": ["600519"],
        }

        tester = ABTester(backtest_config)

        assert tester.backtest_config == backtest_config

    def test_compare_strategies(self):
        """测试策略比较"""
        backtest_config = {
            "initial_cash": 100000,
            "start_date": "2024-01-01",
            "end_date": "2024-01-03",
            "symbols": ["600519"],
        }

        tester = ABTester(backtest_config)

        # 创建两个不同的策略
        config_a = StrategyConfig(
            name="StrategyA",
            params={"fast_period": 5, "slow_period": 20},
        )

        config_b = StrategyConfig(
            name="StrategyB",
            params={"fast_period": 10, "slow_period": 30},
        )

        strategy_a = MACrossStrategy(config_a)
        strategy_b = MACrossStrategy(config_b)

        # 比较
        result = tester.compare(strategy_a, strategy_b)

        assert isinstance(result, ABTestResult)
        assert result.strategy_a_name == "StrategyA"
        assert result.strategy_b_name == "StrategyB"
        assert isinstance(result.metrics_a, dict)
        assert isinstance(result.metrics_b, dict)
        assert result.winner in ["StrategyA", "StrategyB"]
        assert result.recommendation != ""

    def test_compare_identical_strategies(self):
        """测试相同策略的比较"""
        backtest_config = {
            "initial_cash": 100000,
            "start_date": "2024-01-01",
            "end_date": "2024-01-03",
            "symbols": ["600519"],
        }

        tester = ABTester(backtest_config)

        # 创建相同的策略
        config = StrategyConfig(
            name="SameStrategy",
            params={"fast_period": 5, "slow_period": 20},
        )

        strategy_a = MACrossStrategy(config)
        strategy_b = MACrossStrategy(config)

        # 比较
        result = tester.compare(strategy_a, strategy_b)

        # 应该能处理相同策略
        assert result.winner == "SameStrategy"


# ============================================================================
# Integration Tests
# ============================================================================

class TestOptimizerIntegration:
    """优化器集成测试"""

    def test_optimize_strategy_function(self):
        """测试优化策略函数"""
        param_grid = {
            "fast_period": [5],
            "slow_period": [20],
        }

        results = optimize_strategy(
            strategy_class=MACrossStrategy,
            param_grid=param_grid,
            start_date="2024-01-01",
            end_date="2024-01-03",
            symbols=["600519"],
            initial_cash=100000,
        )

        assert isinstance(results, list)
        assert len(results) > 0

    def test_optimization_result_properties(self):
        """测试优化结果属性"""
        config = StrategyConfig(
            name="Test",
            params={"param1": 10},
        )

        metrics = {
            "sharpe_ratio": 1.5,
            "total_return": 0.2,
            "max_drawdown": 0.1,
        }

        result = OptimizationResult(
            config=config,
            metrics=metrics,
        )

        assert result.score == 1.5
        assert result.rank == 0


# ============================================================================
# Utility Tests
# ============================================================================

class TestOptimizationResult:
    """优化结果测试"""

    def test_score_property(self):
        """测试得分属性"""
        config = StrategyConfig(name="Test", params={})

        metrics = {"sharpe_ratio": 2.0}
        result = OptimizationResult(config=config, metrics=metrics)

        assert result.score == 2.0

    def test_score_fallback(self):
        """测试得分回退值"""
        config = StrategyConfig(name="Test", params={})

        metrics = {"total_return": 0.1}
        result = OptimizationResult(config=config, metrics=metrics)

        assert result.score == -999.0


class TestABTestResult:
    """A/B 测试结果测试"""

    def test_properties(self):
        """测试属性"""
        result = ABTestResult(
            strategy_a_name="A",
            strategy_b_name="B",
            metrics_a={},
            metrics_b={},
            winner="A",
            recommendation="A is better",
        )

        assert result.strategy_a_name == "A"
        assert result.strategy_b_name == "B"
        assert result.winner == "A"
        assert result.recommendation == "A is better"
