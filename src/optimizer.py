# -*- coding: utf-8 -*-
"""
策略优化器

实现参数优化、A/B测试和策略比较功能。
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from itertools import product
import copy

from src.strategies.base import BaseStrategy, StrategyConfig, StrategySignal
from src.backtester import BacktestEngine
from src.performance import PerformanceMetrics


logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """优化结果"""
    config: StrategyConfig
    metrics: Dict[str, float]
    rank: int = 0

    @property
    def score(self) -> float:
        """综合得分"""
        # 默认使用夏普比率作为得分
        return self.metrics.get("sharpe_ratio", -999.0)


@dataclass
class ABTestResult:
    """A/B 测试结果"""
    strategy_a_name: str
    strategy_b_name: str
    metrics_a: Dict[str, float]
    metrics_b: Dict[str, float]
    winner: str
    significance: float = 0.0
    recommendation: str = ""


class GridSearchOptimizer:
    """
    网格搜索优化器

    遍历参数空间，寻找最优参数组合。
    """

    def __init__(
        self,
        strategy_class: type,
        param_grid: Dict[str, List[Any]],
        backtest_config: Dict[str, Any],
    ):
        """
        初始化网格搜索优化器

        Args:
            strategy_class: 策略类
            param_grid: 参数网格 {参数名: [值列表]}
            backtest_config: 回测配置
        """
        self.strategy_class = strategy_class
        self.param_grid = param_grid
        self.backtest_config = backtest_config

    def optimize(self, max_iterations: int = 100) -> List[OptimizationResult]:
        """
        执行网格搜索优化

        Args:
            max_iterations: 最大迭代次数

        Returns:
            优化结果列表（按得分排序）
        """
        logger.info("=" * 60)
        logger.info("开始网格搜索优化")
        logger.info("=" * 60)

        # 生成所有参数组合
        param_names = list(self.param_grid.keys())
        param_values = list(self.param_grid.values())

        # 计算总组合数
        total_combinations = 1
        for values in param_values:
            total_combinations *= len(values)

        logger.info(f"参数组合总数: {total_combinations}")

        # 限制迭代次数
        if total_combinations > max_iterations:
            logger.warning(f"组合数超过限制，随机采样 {max_iterations} 个组合")
            return self._random_search(max_iterations)

        results = []
        iteration = 0

        # 遍历所有组合
        for combination in product(*param_values):
            iteration += 1

            # 创建参数字典
            params = dict(zip(param_names, combination))

            logger.info(f"\n迭代 {iteration}/{total_combinations}")
            logger.info(f"参数: {params}")

            # 创建策略配置
            config = StrategyConfig(
                name=self.strategy_class.__name__,
                params=params.copy(),
            )

            # 运行回测
            try:
                metrics = self._evaluate_config(config)

                result = OptimizationResult(
                    config=config,
                    metrics=metrics,
                )

                results.append(result)

                logger.info(f"夏普比率: {metrics['sharpe_ratio']:.2f}")
                logger.info(f"总收益率: {metrics['total_return']*100:.2f}%")
                logger.info(f"最大回撤: {metrics['max_drawdown']*100:.2f}%")

            except Exception as e:
                logger.error(f"参数组合评估失败: {e}")

        # 排序结果
        results.sort(key=lambda x: x.score, reverse=True)

        # 更新排名
        for i, result in enumerate(results):
            result.rank = i + 1

        logger.info("\n" + "=" * 60)
        logger.info("优化完成")
        logger.info("=" * 60)

        # 输出前3名
        for i, result in enumerate(results[:3]):
            logger.info(f"\n第 {i+1} 名:")
            logger.info(f"  参数: {result.config.params}")
            logger.info(f"  夏普比率: {result.metrics['sharpe_ratio']:.2f}")
            logger.info(f"  总收益率: {result.metrics['total_return']*100:.2f}%")

        return results

    def _random_search(self, n_samples: int) -> List[OptimizationResult]:
        """随机搜索"""
        import random

        results = []
        param_names = list(self.param_grid.keys())
        param_values = list(self.param_grid.values())

        for i in range(n_samples):
            # 随机选择参数
            combination = [random.choice(values) for values in param_values]
            params = dict(zip(param_names, combination))

            logger.info(f"\n随机采样 {i+1}/{n_samples}")
            logger.info(f"参数: {params}")

            config = StrategyConfig(
                name=self.strategy_class.__name__,
                params=params.copy(),
            )

            try:
                metrics = self._evaluate_config(config)

                result = OptimizationResult(
                    config=config,
                    metrics=metrics,
                )

                results.append(result)

                logger.info(f"夏普比率: {metrics['sharpe_ratio']:.2f}")

            except Exception as e:
                logger.error(f"参数组合评估失败: {e}")

        # 排序
        results.sort(key=lambda x: x.score, reverse=True)

        return results

    def _evaluate_config(self, config: StrategyConfig) -> Dict[str, float]:
        """评估单个配置"""
        # 创建策略
        strategy = self.strategy_class(config)

        # 运行回测
        backtest_engine = BacktestEngine(
            initial_cash=self.backtest_config.get("initial_cash", 1_000_000),
            start_date=self.backtest_config["start_date"],
            end_date=self.backtest_config["end_date"],
            symbols=self.backtest_config["symbols"],
            strategy=strategy.generate_signal,
        )

        # 运行回测并获取结果
        backtest_engine.load_historical_data()
        result = backtest_engine.run()

        return result


class ABTester:
    """
    A/B 测试框架

    比较不同策略的表现。
    """

    def __init__(self, backtest_config: Dict[str, Any]):
        """
        初始化 A/B 测试器

        Args:
            backtest_config: 回测配置
        """
        self.backtest_config = backtest_config

    def compare(
        self,
        strategy_a: BaseStrategy,
        strategy_b: BaseStrategy,
    ) -> ABTestResult:
        """
        比较两个策略

        Args:
            strategy_a: 策略 A
            strategy_b: 策略 B

        Returns:
            A/B 测试结果
        """
        logger.info("=" * 60)
        logger.info("开始 A/B 测试")
        logger.info(f"策略 A: {strategy_a.name}")
        logger.info(f"策略 B: {strategy_b.name}")
        logger.info("=" * 60)

        # 评估策略 A
        metrics_a = self._evaluate_strategy(strategy_a)
        logger.info(f"\n策略 A 性能:")
        logger.info(f"  夏普比率: {metrics_a['sharpe_ratio']:.2f}")
        logger.info(f"  总收益率: {metrics_a['total_return']*100:.2f}%")
        logger.info(f"  最大回撤: {metrics_a['max_drawdown']*100:.2f}%")
        logger.info(f"  胜率: {metrics_a['win_rate']*100:.2f}%")

        # 评估策略 B
        metrics_b = self._evaluate_strategy(strategy_b)
        logger.info(f"\n策略 B 性能:")
        logger.info(f"  夏普比率: {metrics_b['sharpe_ratio']:.2f}")
        logger.info(f"  总收益率: {metrics_b['total_return']*100:.2f}%")
        logger.info(f"  最大回撤: {metrics_b['max_drawdown']*100:.2f}%")
        logger.info(f"  胜率: {metrics_b['win_rate']*100:.2f}%")

        # 比较结果
        winner, recommendation = self._compare_metrics(
            strategy_a.name, metrics_a,
            strategy_b.name, metrics_b,
        )

        result = ABTestResult(
            strategy_a_name=strategy_a.name,
            strategy_b_name=strategy_b.name,
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            winner=winner,
            recommendation=recommendation,
        )

        logger.info("\n" + "=" * 60)
        logger.info("A/B 测试结果")
        logger.info("=" * 60)
        logger.info(f"胜出策略: {winner}")
        logger.info(f"建议: {recommendation}")

        return result

    def _evaluate_strategy(self, strategy: BaseStrategy) -> Dict[str, float]:
        """评估单个策略"""
        backtest_engine = BacktestEngine(
            initial_cash=self.backtest_config.get("initial_cash", 1_000_000),
            start_date=self.backtest_config["start_date"],
            end_date=self.backtest_config["end_date"],
            symbols=self.backtest_config["symbols"],
            strategy=strategy.generate_signal,
        )

        backtest_engine.load_historical_data()
        result = backtest_engine.run()

        return result

    def _compare_metrics(
        self,
        name_a: str,
        metrics_a: Dict[str, float],
        name_b: str,
        metrics_b: Dict[str, float],
    ) -> Tuple[str, str]:
        """
        比较指标并推荐胜者

        Returns:
            (胜者名称, 推荐理由)
        """
        # 计算综合得分
        score_a = self._calculate_score(metrics_a)
        score_b = self._calculate_score(metrics_b)

        # 比较得分
        if score_a > score_b * 1.05:  # A 优于 B 5% 以上
            winner = name_a
            recommendation = f"{name_a} 的综合表现明显优于 {name_b}，建议使用 {name_a}。"
        elif score_b > score_a * 1.05:  # B 优于 A 5% 以上
            winner = name_b
            recommendation = f"{name_b} 的综合表现明显优于 {name_a}，建议使用 {name_b}。"
        else:
            # 表现接近，比较具体指标
            if metrics_a["sharpe_ratio"] > metrics_b["sharpe_ratio"]:
                winner = name_a
                recommendation = f"两者表现接近，但 {name_a} 的夏普比率更高，风险调整后收益更好。"
            elif metrics_b["sharpe_ratio"] > metrics_a["sharpe_ratio"]:
                winner = name_b
                recommendation = f"两者表现接近，但 {name_b} 的夏普比率更高，风险调整后收益更好。"
            elif metrics_a["max_drawdown"] < metrics_b["max_drawdown"]:
                winner = name_a
                recommendation = f"两者表现接近，但 {name_a} 的最大回撤更小，风险控制更好。"
            else:
                winner = name_b
                recommendation = f"两者表现接近，但 {name_b} 的最大回撤更小，风险控制更好。"

        return winner, recommendation

    def _calculate_score(self, metrics: Dict[str, float]) -> float:
        """
        计算综合得分

        Args:
            metrics: 性能指标

        Returns:
            综合得分
        """
        # 权重设置
        weights = {
            "sharpe_ratio": 0.4,
            "total_return": 0.3,
            "max_drawdown": -0.2,  # 负权重，越小越好
            "win_rate": 0.1,
        }

        score = 0.0
        for key, weight in weights.items():
            if key in metrics:
                score += metrics[key] * weight

        return score


def optimize_strategy(
    strategy_class: type,
    param_grid: Dict[str, List[Any]],
    start_date: str,
    end_date: str,
    symbols: List[str],
    initial_cash: float = 1_000_000,
) -> List[OptimizationResult]:
    """
    优化策略参数

    Args:
        strategy_class: 策略类
        param_grid: 参数网格
        start_date: 开始日期
        end_date: 结束日期
        symbols: 股票代码列表
        initial_cash: 初始资金

    Returns:
        优化结果列表
    """
    optimizer = GridSearchOptimizer(
        strategy_class=strategy_class,
        param_grid=param_grid,
        backtest_config={
            "initial_cash": initial_cash,
            "start_date": start_date,
            "end_date": end_date,
            "symbols": symbols,
        },
    )

    return optimizer.optimize()
