"""
测试 src.config 模块
"""
import pytest

# 确保模块被导入以正确收集覆盖率
import src.config
from src.config import Config, get_config, set_config


class TestConfigDataclass:
    """测试Config dataclass"""

    def test_config_default_values(self):
        """测试Config默认值"""
        config = Config()

        assert config.data_dir == "data"
        assert config.api_host == "127.0.0.1"
        assert config.api_port == 8000
        assert config.data_source == "finshare"
        assert config.strategy_dir == "strategies"
        assert config.default_strategies == [
            "momentum_trend",
            "value_reversal",
            "breakout_vol",
        ]

    def test_config_custom_values(self):
        """测试Config自定义值"""
        config = Config(
            data_dir="custom_data",
            api_host="192.168.1.1",
            api_port=9000,
            data_source="akshare",
            strategy_dir="my_strategies",
            default_strategies=["custom_strategy"],
        )

        assert config.data_dir == "custom_data"
        assert config.api_host == "192.168.1.1"
        assert config.api_port == 9000
        assert config.data_source == "akshare"
        assert config.strategy_dir == "my_strategies"
        assert config.default_strategies == ["custom_strategy"]

    def test_config_post_init_sets_default_strategies(self):
        """测试__post_init__设置默认策略"""
        config = Config()

        assert config.default_strategies is not None
        assert len(config.default_strategies) == 3
        assert "momentum_trend" in config.default_strategies
        assert "value_reversal" in config.default_strategies
        assert "breakout_vol" in config.default_strategies

    def test_config_post_init_preserves_custom_strategies(self):
        """测试__post_init__保留自定义策略"""
        custom_strategies = ["strategy1", "strategy2", "strategy3"]
        config = Config(default_strategies=custom_strategies)

        assert config.default_strategies == custom_strategies

    def test_config_custom_port(self):
        """测试自定义端口"""
        config = Config(api_port=8080)
        assert config.api_port == 8080

    def test_config_custom_data_dir(self):
        """测试自定义数据目录"""
        config = Config(data_dir="/tmp/data")
        assert config.data_dir == "/tmp/data"

    def test_config_multiple_custom_values(self):
        """测试多个自定义值"""
        config = Config(
            api_host="localhost",
            api_port=3000,
            data_source="akshare",
            strategy_dir="custom/strategies",
        )
        assert config.api_host == "localhost"
        assert config.api_port == 3000
        assert config.data_source == "akshare"
        assert config.strategy_dir == "custom/strategies"
        # default_strategies should be set by __post_init__
        assert config.default_strategies == [
            "momentum_trend",
            "value_reversal",
            "breakout_vol",
        ]


class TestGetConfig:
    """测试get_config函数"""

    def test_get_config_returns_singleton(self):
        """测试get_config返回单例"""
        # 重置全局配置
        set_config(None)

        config1 = get_config()
        config2 = get_config()

        assert config1 is config2

    def test_get_config_creates_default_on_first_call(self):
        """测试首次调用get_config创建默认配置"""
        # 重置全局配置
        set_config(None)

        config = get_config()

        assert isinstance(config, Config)
        assert config.data_dir == "data"
        assert config.api_host == "127.0.0.1"
        assert config.api_port == 8000

    def test_get_config_returns_same_instance_after_set(self):
        """测试set_config后get_config返回相同实例"""
        custom_config = Config(data_dir="custom")
        set_config(custom_config)

        retrieved = get_config()

        assert retrieved is custom_config
        assert retrieved.data_dir == "custom"


class TestSetConfig:
    """测试set_config函数"""

    def test_set_config_updates_global_config(self):
        """测试set_config更新全局配置"""
        custom_config = Config(data_dir="new_data", api_port=9999)
        set_config(custom_config)

        retrieved = get_config()

        assert retrieved.data_dir == "new_data"
        assert retrieved.api_port == 9999

    def test_set_config_none_resets_global(self):
        """测试set_config(None)重置全局配置"""
        # 先设置一个配置
        custom_config = Config(data_dir="temp")
        set_config(custom_config)

        # 重置为None
        set_config(None)

        # 再次调用get_config应该创建新的默认配置
        new_config = get_config()

        assert new_config is not custom_config
        assert new_config.data_dir == "data"

    def test_set_config_multiple_times(self):
        """测试多次set_config"""
        config1 = Config(data_dir="dir1")
        config2 = Config(data_dir="dir2")
        config3 = Config(data_dir="dir3")

        set_config(config1)
        assert get_config().data_dir == "dir1"

        set_config(config2)
        assert get_config().data_dir == "dir2"

        set_config(config3)
        assert get_config().data_dir == "dir3"


class TestConfigIntegration:
    """测试Config集成场景"""

    def test_config_modification_does_not_affect_singleton(self):
        """测试修改config实例不影响后续单例"""
        # 获取配置
        config1 = get_config()
        original_data_dir = config1.data_dir

        # 修改实例属性（不影响单例）
        config1.data_dir = "modified"

        # 获取新实例
        set_config(None)
        config2 = get_config()

        # 新实例应该有原始默认值
        assert config2.data_dir == "data"
        assert config2.data_dir != "modified"

    def test_empty_default_strategies_list(self):
        """测试空的默认策略列表"""
        config = Config(default_strategies=[])
        assert config.default_strategies == []

    def test_single_default_strategy(self):
        """测试单个默认策略"""
        config = Config(default_strategies=["single_strategy"])
        assert config.default_strategies == ["single_strategy"]