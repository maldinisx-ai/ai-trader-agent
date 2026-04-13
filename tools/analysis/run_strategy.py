# -*- coding: utf-8 -*-
"""
策略分析工具

让 Agent 可以调用各种交易策略生成买卖信号。
"""

from typing import Optional, Dict, Any
from pathlib import Path

from core.schemas import Decision
from src.strategies.base import BaseStrategy, StrategyConfig, SignalType
from src.strategies.ma_cross import MACrossStrategy, TripleMACrossStrategy
from src.indicators import QuoteDataAnalyzer
from simulation.account import Account
from core.policy_engine import PolicyEngine


# 策略注册表
STRATEGIES = {
    "ma_cross": MACrossStrategy,
    "triple_ma": TripleMACrossStrategy,
}


# 默认策略配置
DEFAULT_CONFIGS = {
    "ma_cross": {
        "fast_period": 10,
        "slow_period": 30,
        "max_position_ratio": 0.30,
    },
    "triple_ma": {
        "short_period": 5,
        "medium_period": 10,
        "long_period": 30,
        "max_position_ratio": 0.30,
    },
}


def create_strategy(
    strategy_name: str,
    params: Optional[Dict[str, Any]] = None,
) -> BaseStrategy:
    """
    创建策略实例

    Args:
        strategy_name: 策略名称 ("ma_cross", "triple_ma")
        params: 策略参数 (可选，覆盖默认值)

    Returns:
        策略实例

    Raises:
        ValueError: 未知策略名称
    """
    if strategy_name not in STRATEGIES:
        raise ValueError(f"未知策略: {strategy_name}. 可用策略: {list(STRATEGIES.keys())}")

    # 合并默认配置和用户配置
    config_params = DEFAULT_CONFIGS.get(strategy_name, {}).copy()
    if params:
        config_params.update(params)

    config = StrategyConfig(name=strategy_name, params=config_params)
    strategy_class = STRATEGIES[strategy_name]
    return strategy_class(config)


def analyze_with_strategy(
    symbol: str,
    strategy_name: str = "ma_cross",
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    使用指定策略分析单只股票

    Args:
        symbol: 股票代码
        strategy_name: 策略名称
        params: 策略参数

    Returns:
        分析结果，包含:
        - symbol: 股票代码
        - signal: 信号类型 (buy/sell/hold)
        - reasoning: 决策原因
        - confidence: 信号置信度
        - current_price: 当前价格
        - suggested_quantity: 建议数量
        - indicators: 技术指标值
    """
    import pandas as pd
    from core.schemas import QuoteData

    # 加载股票数据
    data_path = Path(__file__).parent.parent.parent / f"data/stocks/stock_{symbol}.csv"
    if not data_path.exists():
        return {
            "symbol": symbol,
            "signal": "hold",
            "reasoning": f"数据文件不存在: {data_path}",
            "confidence": 0.0,
            "current_price": 0,
            "suggested_quantity": 0,
            "indicators": {},
        }

    df = pd.read_csv(data_path)
    df['date'] = pd.to_datetime(df['date'])

    # 构建 QuoteData 列表
    quotes = []
    for i, row in df.iterrows():
        change = 0.0
        if i > 0 and quotes:
            change = ((row['close'] - quotes[-1].price) / quotes[-1].price) * 100
            change = max(-11, min(11, change))

        quotes.append(QuoteData(
            symbol=symbol,
            name=f"股票{symbol}",
            price=float(row['close']),
            change=change,
            volume=int(row['volume']),
            amount=float(row.get('amount', 0)),
            high=float(row['high']),
            low=float(row['low']),
            open=float(row['open']),
            timestamp=row['date'],
        ))

    # 创建策略和分析器
    strategy = create_strategy(strategy_name, params)
    analyzer = QuoteDataAnalyzer(quotes)

    # 模拟账户信息
    account_info = {
        "cash": 500000,
        "total_value": 500000,
        "positions": [],
    }

    # 生成信号
    signal = strategy.generate_signal(analyzer, account_info)

    if signal is None:
        return {
            "symbol": symbol,
            "signal": "hold",
            "reasoning": "无交易信号",
            "confidence": 0.0,
            "current_price": quotes[-1].price if quotes else 0,
            "suggested_quantity": 0,
            "indicators": _get_indicators_dict(analyzer, strategy),
        }

    return {
        "symbol": symbol,
        "signal": signal.signal_type.value,
        "reasoning": signal.reasoning,
        "confidence": signal.confidence,
        "current_price": signal.price,
        "suggested_quantity": signal.quantity,
        "indicators": _get_indicators_dict(analyzer, strategy),
        "metadata": signal.metadata,
    }


def _get_indicators_dict(
    analyzer: QuoteDataAnalyzer,
    strategy: BaseStrategy,
) -> Dict[str, Any]:
    """提取技术指标"""
    indicators = {}

    if hasattr(strategy, 'fast_period'):
        ma = analyzer.get_sma(strategy.fast_period)
        indicators[f"ma_{strategy.fast_period}"] = ma[-1] if ma else None

    if hasattr(strategy, 'slow_period'):
        ma = analyzer.get_sma(strategy.slow_period)
        indicators[f"ma_{strategy.slow_period}"] = ma[-1] if ma else None

    if hasattr(strategy, 'short_period'):
        ma = analyzer.get_sma(strategy.short_period)
        indicators[f"ma_{strategy.short_period}"] = ma[-1] if ma else None

    if hasattr(strategy, 'medium_period'):
        ma = analyzer.get_sma(strategy.medium_period)
        indicators[f"ma_{strategy.medium_period}"] = ma[-1] if ma else None

    if hasattr(strategy, 'long_period'):
        ma = analyzer.get_sma(strategy.long_period)
        indicators[f"ma_{strategy.long_period}"] = ma[-1] if ma else None

    return indicators


def list_strategies() -> Dict[str, Dict[str, Any]]:
    """
    列出所有可用策略

    Returns:
        策略信息字典
    """
    return {
        name: {
            "description": _get_strategy_description(name),
            "default_params": DEFAULT_CONFIGS.get(name, {}),
        }
        for name in STRATEGIES.keys()
    }


def _get_strategy_description(strategy_name: str) -> str:
    """获取策略描述"""
    descriptions = {
        "ma_cross": "MA交叉策略 - 金叉买入，死叉卖出",
        "triple_ma": "三均线策略 - 多头排列买入，空头排列卖出",
    }
    return descriptions.get(strategy_name, "未知策略")


# 导出函数供 agent 使用
__all__ = [
    "analyze_with_strategy",
    "create_strategy",
    "list_strategies",
]
