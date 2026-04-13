"""
策略管理器 - 加载和管理 YAML 策略文件
"""
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union
import yaml

logger = logging.getLogger(__name__)


@dataclass
class Strategy:
    """交易策略数据类"""
    name: str
    display_name: str
    description: str
    instructions: str
    category: str = "trend"
    core_rules: List[int] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    default_active: bool = False
    default_priority: int = 100
    market_regimes: List[str] = field(default_factory=list)
    enabled: bool = False
    source: str = "builtin"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "core_rules": self.core_rules,
            "required_tools": self.required_tools,
            "aliases": self.aliases,
            "default_active": self.default_active,
            "default_priority": self.default_priority,
            "market_regimes": self.market_regimes,
            "enabled": self.enabled,
            "source": self.source,
        }


class StrategyManager:
    """策略管理器"""

    def __init__(self, strategy_dir: Optional[Union[str, Path]] = None):
        """
        初始化策略管理器

        Args:
            strategy_dir: 策略目录路径，默认为项目根目录下的 strategies/
        """
        if strategy_dir is None:
            # 默认使用项目根目录下的 strategies/ 目录
            project_root = Path(__file__).resolve().parent.parent.parent
            strategy_dir = project_root / "strategies"

        self.strategy_dir = Path(strategy_dir)
        self.strategies: Dict[str, Strategy] = {}
        self._load_strategies()

    def _load_strategies(self):
        """加载所有策略文件"""
        if not self.strategy_dir.exists():
            logger.warning(f"策略目录不存在: {self.strategy_dir}")
            return

        for yaml_file in self.strategy_dir.glob("*.yaml"):
            try:
                strategy = self._load_strategy_from_yaml(yaml_file)
                self.strategies[strategy.name] = strategy
                logger.info(f"加载策略: {strategy.display_name} ({strategy.name})")
            except Exception as e:
                logger.error(f"加载策略失败 {yaml_file}: {e}")

        logger.info(f"共加载 {len(self.strategies)} 个策略")

    def _load_strategy_from_yaml(self, filepath: Path) -> Strategy:
        """从 YAML 文件加载单个策略"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"无效的策略文件格式: {filepath}")

        # 验证必填字段
        required_fields = ["name", "display_name", "description", "instructions"]
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            raise ValueError(f"策略文件 {filepath.name} 缺少必填字段: {missing}")

        return Strategy(
            name=str(data["name"]).strip(),
            display_name=str(data["display_name"]).strip(),
            description=str(data["description"]).strip(),
            instructions=str(data["instructions"]).strip(),
            category=str(data.get("category", "trend")).strip(),
            core_rules=data.get("core_rules", []) or [],
            required_tools=data.get("required_tools", []) or [],
            aliases=self._parse_list(data.get("aliases")),
            default_active=bool(data.get("default_active", False)),
            default_priority=int(data.get("default_priority", 100)),
            market_regimes=self._parse_list(data.get("market_regimes")),
            enabled=False,
            source=str(filepath),
        )

    def _parse_list(self, value) -> List[str]:
        """解析列表类型的值"""
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def list_strategies(self, category: Optional[str] = None) -> List[Strategy]:
        """
        列出所有策略

        Args:
            category: 可选，按类别筛选

        Returns:
            策略列表
        """
        strategies = list(self.strategies.values())
        if category:
            strategies = [s for s in strategies if s.category == category]
        return sorted(strategies, key=lambda x: x.default_priority)

    def get_strategy(self, name: str) -> Optional[Strategy]:
        """
        获取指定策略

        Args:
            name: 策略名称

        Returns:
            策略对象，不存在则返回 None
        """
        return self.strategies.get(name)

    def activate(self, names: List[str]) -> List[str]:
        """
        激活指定策略

        Args:
            names: 策略名称列表

        Returns:
            实际激活的策略名称列表
        """
        activated = []
        for name in names:
            if name in self.strategies:
                self.strategies[name].enabled = True
                activated.append(name)
            else:
                logger.warning(f"策略不存在: {name}")
        return activated

    def deactivate_all(self):
        """停用所有策略"""
        for strategy in self.strategies.values():
            strategy.enabled = False

    def get_active_strategies(self) -> List[Strategy]:
        """获取所有已激活的策略"""
        return [s for s in self.strategies.values() if s.enabled]

    def get_strategy_instructions(self, names: Optional[List[str]] = None) -> str:
        """
        获取策略指令文本

        Args:
            names: 策略名称列表，None 则使用已激活策略

        Returns:
            合并后的策略指令文本
        """
        if names is None:
            strategies = self.get_active_strategies()
        else:
            strategies = [self.get_strategy(n) for n in names]
            strategies = [s for s in strategies if s is not None]

        if not strategies:
            return ""

        instructions = []
        for strategy in strategies:
            instructions.append(f"## {strategy.display_name}\n\n{strategy.instructions}")

        return "\n\n---\n\n".join(instructions)

    def search_by_alias(self, alias: str) -> Optional[Strategy]:
        """
        通过别名搜索策略

        Args:
            alias: 策略别名

        Returns:
            匹配的策略，无匹配则返回 None
        """
        alias_lower = alias.strip().lower()
        for strategy in self.strategies.values():
            if alias_lower in [a.lower() for a in strategy.aliases]:
                return strategy
            if alias_lower == strategy.name.lower():
                return strategy
        return None


# 单例模式
_strategy_manager: Optional[StrategyManager] = None


def get_strategy_manager() -> StrategyManager:
    """获取策略管理器单例"""
    global _strategy_manager
    if _strategy_manager is None:
        _strategy_manager = StrategyManager()
    return _strategy_manager


def reload_strategies():
    """重新加载所有策略"""
    global _strategy_manager
    _strategy_manager = StrategyManager()
    return _strategy_manager
