# -*- coding: utf-8 -*-
"""
策略基类

定义所有交易策略的基类和接口。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from core.schemas import Decision, QuoteData
from src.indicators import QuoteDataAnalyzer


class SignalType(str, Enum):
    """信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class StrategySignal:
    """策略信号"""
    signal_type: SignalType
    symbol: str
    price: float
    quantity: int
    confidence: float
    reasoning: str
    metadata: Dict[str, Any]

    def to_decision(self) -> Decision:
        """转换为决策对象"""
        return Decision(
            action=self.signal_type.value,
            symbol=self.symbol,
            quantity=self.quantity,
            price=self.price,
            reasoning=self.reasoning,
            confidence=self.confidence,
        )


@dataclass
class StrategyConfig:
    """策略配置"""
    name: str
    params: Dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        """获取参数值"""
        return self.params.get(key, default)

    def set(self, key: str, value: Any):
        """设置参数值"""
        self.params[key] = value

    def copy(self) -> 'StrategyConfig':
        """复制配置"""
        return StrategyConfig(
            name=self.name,
            params=self.params.copy(),
        )


class BaseStrategy(ABC):
    """
    策略基类

    所有交易策略必须继承此类并实现 generate_signal 方法。
    """

    def __init__(self, config: StrategyConfig):
        """
        初始化策略

        Args:
            config: 策略配置
        """
        self.config = config
        self.name = config.name
        self.signals_generated: int = 0

    @abstractmethod
    def generate_signal(
        self,
        analyzer: QuoteDataAnalyzer,
        account_info: Dict[str, Any],
    ) -> Optional[StrategySignal]:
        """
        生成交易信号

        Args:
            analyzer: 行情数据分析器
            account_info: 账户信息

        Returns:
            策略信号，如果不产生信号则返回 None
        """
        pass

    def validate_signal(self, signal: StrategySignal, account_info: Dict[str, Any]) -> bool:
        """
        验证信号有效性

        Args:
            signal: 策略信号
            account_info: 账户信息

        Returns:
            信号是否有效
        """
        # 检查资金是否足够
        if signal.signal_type == SignalType.BUY:
            required_cash = signal.price * signal.quantity
            available_cash = account_info.get("cash", 0)
            if required_cash > available_cash:
                return False

        return True

    def get_position_size(
        self,
        price: float,
        account_info: Dict[str, Any],
        max_position_ratio: float = 0.30,
    ) -> int:
        """
        计算仓位大小

        Args:
            price: 当前价格
            account_info: 账户信息
            max_position_ratio: 最大仓位比例

        Returns:
            建议股数（100的整数倍）
        """
        # 输入验证
        if price <= 0:
            return 0

        total_value = account_info.get("total_value", 0)
        if total_value <= 0:
            return 0

        max_position_value = total_value * max_position_ratio

        # 计算股数
        shares = int(max_position_value / price / 100) * 100

        return max(100, shares)  # 至少一手

    def update_config(self, params: Dict[str, Any]):
        """
        更新策略配置

        Args:
            params: 新的参数
        """
        for key, value in params.items():
            self.config.set(key, value)

    def get_config(self) -> StrategyConfig:
        """获取当前配置"""
        return self.config

    def reset(self):
        """重置策略状态"""
        self.signals_generated = 0
