# -*- coding: utf-8 -*-
"""
策略库

定义各种交易策略的基类和具体实现。
"""

from .base import BaseStrategy, StrategyConfig, StrategySignal
from .technical import TechnicalStrategy
from .ma_cross import MACrossStrategy
from .trend_scoring import TrendScoringStrategy

__all__ = [
    "BaseStrategy",
    "StrategyConfig",
    "StrategySignal",
    "TechnicalStrategy",
    "MACrossStrategy",
    "TrendScoringStrategy",
]
