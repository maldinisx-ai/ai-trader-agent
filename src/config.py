"""
系统配置
"""
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """系统配置"""
    # 数据目录
    data_dir: str = "data"

    # API 配置
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # 数据源配置
    data_source: str = "finshare"  # finshare, akshare

    # 策略配置
    strategy_dir: str = "strategies"

    # 默认激活的策略
    default_strategies: list = None

    def __post_init__(self):
        if self.default_strategies is None:
            self.default_strategies = [
                "momentum_trend",
                "value_reversal",
                "breakout_vol",
            ]


# 全局配置实例
_config: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config):
    """设置全局配置"""
    global _config
    _config = config
