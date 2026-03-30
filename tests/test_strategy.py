# -*- coding: utf-8 -*-
"""
测试策略系统模块

测试策略管理器、评分引擎、执行器和数据准备器
"""

import pytest
from datetime import datetime
from typing import Dict, Any
import pandas as pd

# 添加项目根目录到路径
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestStrategyDataClass:
    """测试 Strategy 数据类"""

    def test_strategy_creation(self):
        """测试创建策略对象"""
        from src.strategy.manager import Strategy

        strategy = Strategy(
            name="test_strategy",
            display_name="测试策略",
            description="这是一个测试策略",
            instructions="买入信号",
            category="trend",
            core_rules=[1, 2, 3],
            required_tools=["get_quote"],
            aliases=["test", "demo"],
            default_active=True,
            default_priority=50,
            market_regimes=["bull"],
            enabled=True,
            source="test"
        )

        assert strategy.name == "test_strategy"
        assert strategy.display_name == "测试策略"
        assert strategy.category == "trend"
        assert strategy.core_rules == [1, 2, 3]

    def test_strategy_to_dict(self):
        """测试策略转换为字典"""
        from src.strategy.manager import Strategy

        strategy = Strategy(
            name="test",
            display_name="测试",
            description="desc",
            instructions="ins"
        )

        result = strategy.to_dict()

        assert result["name"] == "test"
        assert result["display_name"] == "测试"
        assert "core_rules" in result
        assert "required_tools" in result

    def test_strategy_default_values(self):
        """测试策略默认值"""
        from src.strategy.manager import Strategy

        strategy = Strategy(
            name="test",
            display_name="测试",
            description="desc",
            instructions="ins"
        )

        assert strategy.category == "trend"
        assert strategy.core_rules == []
        assert strategy.required_tools == []
        assert strategy.aliases == []
        assert strategy.default_active is False
        assert strategy.default_priority == 100
        assert strategy.market_regimes == []
        assert strategy.enabled is False
        assert strategy.source == "builtin"


class TestStrategyManager:
    """测试策略管理器"""

    def test_init_with_default_dir(self):
        """测试使用默认目录初始化"""
        from src.strategy.manager import StrategyManager

        manager = StrategyManager()

        assert manager.strategy_dir.name == "strategies"
        assert isinstance(manager.strategies, dict)

    def test_init_with_custom_dir(self):
        """测试使用自定义目录初始化"""
        from src.strategy.manager import StrategyManager
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = StrategyManager(strategy_dir=tmp_dir)

            assert manager.strategy_dir == Path(tmp_dir)

    def test_list_strategies_all(self):
        """测试列出所有策略"""
        from src.strategy.manager import StrategyManager

        manager = StrategyManager()

        strategies = manager.list_strategies()

        assert isinstance(strategies, list)
        # 所有策略应该按优先级排序

    def test_list_strategies_by_category(self):
        """测试按类别列出策略"""
        from src.strategy.manager import StrategyManager

        manager = StrategyManager()

        trend_strategies = manager.list_strategies(category="trend")

        # 筛选的结果应该都是指定类别
        for s in trend_strategies:
            assert s.category == "trend"

    def test_get_strategy_exists(self):
        """测试获取存在的策略"""
        from src.strategy.manager import StrategyManager

        manager = StrategyManager()

        # 尝试获取默认策略
        strategy = manager.get_strategy("momentum_trend")

        if strategy:
            assert strategy.name == "momentum_trend"

    def test_get_strategy_not_exists(self):
        """测试获取不存在的策略"""
        from src.strategy.manager import StrategyManager

        manager = StrategyManager()

        strategy = manager.get_strategy("nonexistent")

        assert strategy is None

    def test_activate_strategies(self):
        """测试激活策略"""
        from src.strategy.manager import StrategyManager, Strategy

        manager = StrategyManager()

        # 添加测试策略
        test_strategy = Strategy(
            name="test_active",
            display_name="测试激活",
            description="desc",
            instructions="ins"
        )
        manager.strategies["test_active"] = test_strategy

        activated = manager.activate(["test_active"])

        assert "test_active" in activated
        assert test_strategy.enabled is True

    def test_activate_nonexistent_strategy(self):
        """测试激活不存在的策略"""
        from src.strategy.manager import StrategyManager

        manager = StrategyManager()

        activated = manager.activate(["nonexistent"])

        assert "nonexistent" not in activated

    def test_deactivate_all(self):
        """测试停用所有策略"""
        from src.strategy.manager import StrategyManager, Strategy

        manager = StrategyManager()

        # 添加并激活测试策略
        test_strategy = Strategy(
            name="test_deactivate",
            display_name="测试停用",
            description="desc",
            instructions="ins",
            enabled=True
        )
        manager.strategies["test_deactivate"] = test_strategy

        manager.deactivate_all()

        assert test_strategy.enabled is False

    def test_get_active_strategies(self):
        """测试获取激活的策略"""
        from src.strategy.manager import StrategyManager, Strategy

        manager = StrategyManager()

        # 添加激活和未激活的策略
        active = Strategy(
            name="active",
            display_name="激活",
            description="desc",
            instructions="ins",
            enabled=True
        )
        inactive = Strategy(
            name="inactive",
            display_name="未激活",
            description="desc",
            instructions="ins",
            enabled=False
        )
        manager.strategies["active"] = active
        manager.strategies["inactive"] = inactive

        active_strategies = manager.get_active_strategies()

        assert len(active_strategies) == 1
        assert "active" in [s.name for s in active_strategies]

    def test_get_strategy_instructions_empty(self):
        """测试获取策略指令 - 空"""
        from src.strategy.manager import StrategyManager

        manager = StrategyManager()

        instructions = manager.get_strategy_instructions([])

        assert instructions == ""

    def test_get_strategy_instructions_with_names(self):
        """测试获取策略指令 - 指定名称"""
        from src.strategy.manager import StrategyManager, Strategy

        manager = StrategyManager()

        # 添加测试策略
        strategy = Strategy(
            name="test_ins",
            display_name="测试指令",
            description="desc",
            instructions="买入信号描述"
        )
        manager.strategies["test_ins"] = strategy

        instructions = manager.get_strategy_instructions(["test_ins"])

        assert "测试指令" in instructions
        assert "买入信号描述" in instructions

    def test_search_by_alias(self):
        """测试通过别名搜索策略"""
        from src.strategy.manager import StrategyManager, Strategy

        manager = StrategyManager()

        # 添加带别名的策略
        strategy = Strategy(
            name="test_alias",
            display_name="测试别名",
            description="desc",
            instructions="ins",
            aliases=["alias1", "alias2"]
        )
        manager.strategies["test_alias"] = strategy

        found = manager.search_by_alias("alias1")

        assert found is not None
        assert found.name == "test_alias"

    def test_search_by_alias_not_found(self):
        """测试通过别名搜索不存在的策略"""
        from src.strategy.manager import StrategyManager

        manager = StrategyManager()

        found = manager.search_by_alias("nonexistent_alias")

        assert found is None


class TestScoringRule:
    """测试评分规则"""

    def test_rule_condition_true(self):
        """测试规则条件为真"""
        from src.strategy.scoring import ScoringRule

        rule = ScoringRule(
            name="test_rule",
            condition=lambda d: d.get("value", 0) > 10,
            score=15,
            reason="测试规则"
        )

        result = rule.evaluate({"value": 20})

        assert result is not None
        assert result["name"] == "test_rule"
        assert result["score"] == 15
        assert result["reason"] == "测试规则"

    def test_rule_condition_false(self):
        """测试规则条件为假"""
        from src.strategy.scoring import ScoringRule

        rule = ScoringRule(
            name="test_rule",
            condition=lambda d: d.get("value", 0) > 10,
            score=15,
            reason="测试规则"
        )

        result = rule.evaluate({"value": 5})

        assert result is None

    def test_rule_with_category(self):
        """测试带类别的规则"""
        from src.strategy.scoring import ScoringRule

        rule = ScoringRule(
            name="test_rule",
            condition=lambda d: True,
            score=10,
            reason="测试",
            category="test_category"
        )

        result = rule.evaluate({})

        assert result["category"] == "test_category"


class TestMomentumScoringEngine:
    """测试动量趋势评分引擎"""

    def test_get_rules(self):
        """测试获取规则"""
        from src.strategy.scoring import MomentumScoringEngine

        rules = MomentumScoringEngine.get_rules()

        assert len(rules) > 0
        assert all(hasattr(r, 'name') for r in rules)
        assert all(hasattr(r, 'condition') for r in rules)
        assert all(hasattr(r, 'score') for r in rules)

    def test_calculate_buy_signal(self):
        """测试计算买入信号"""
        from src.strategy.scoring import MomentumScoringEngine

        market_data = {
            "n20_gain_pct": 20,  # 强动量
            "ma5": 110,
            "ma10": 105,
            "ma20": 100,  # 多头排列
            "ma20_slope": 0.5,  # 上升趋势
            "close": 110,
            "main_net_inflow_ratio": 25,  # 强流入
            "volume_ratio": 2.5,  # 放量
        }

        result = MomentumScoringEngine.calculate(market_data)

        assert result.score >= 70
        assert result.signal.value == "buy"
        assert result.confidence > 0.5

    def test_calculate_sell_signal(self):
        """测试计算卖出信号"""
        from src.strategy.scoring import MomentumScoringEngine

        market_data = {
            "n20_gain_pct": -10,  # 负动量
            "ma5": 95,
            "ma10": 100,
            "ma20": 105,  # 空头排列
            "ma20_slope": -0.3,
            "close": 95,
            "main_net_inflow_ratio": -20,  # 大幅流出
            "volume_ratio": 0.8,
        }

        result = MomentumScoringEngine.calculate(market_data)

        assert result.score <= 30
        assert result.signal.value == "sell"

    def test_calculate_hold_signal(self):
        """测试计算持有信号"""
        from src.strategy.scoring import MomentumScoringEngine

        market_data = {
            "n20_gain_pct": 2,  # 非常弱的动量
            "ma5": 99,
            "ma10": 100,
            "ma20": 101,  # 基本下跌
            "ma20_slope": -0.2,
            "close": 100,
            "main_net_inflow_ratio": 0,  # 无流入
            "volume_ratio": 0.8,
        }

        result = MomentumScoringEngine.calculate(market_data)

        assert 30 < result.score < 70
        assert result.signal.value == "hold"


class TestValueReversalScoringEngine:
    """测试价值反转评分引擎"""

    def test_get_rules(self):
        """测试获取规则"""
        from src.strategy.scoring import ValueReversalScoringEngine

        rules = ValueReversalScoringEngine.get_rules()

        assert len(rules) > 0

    def test_calculate_without_financial_data(self):
        """测试没有财务数据"""
        from src.strategy.scoring import ValueReversalScoringEngine

        market_data = {}

        result = ValueReversalScoringEngine.calculate(market_data)

        assert result.score == 50
        assert result.signal.value == "hold"
        assert result.confidence == 0.3

    def test_calculate_with_good_financials(self):
        """测试良好财务数据"""
        from src.strategy.scoring import ValueReversalScoringEngine

        market_data = {}
        financial_data = {
            "pe": 8,  # 低估值
            "pb": 0.8,  # 破净
            "roe": 20,  # 高盈利
            "dividend_yield": 6,  # 高股息
            "debt_ratio": 40,  # 低负债
            "from_high_drop_pct": -45,  # 深度下跌
            "rsi": 25,  # 超卖
        }

        result = ValueReversalScoringEngine.calculate(market_data, financial_data)

        assert result.score >= 70
        assert result.signal.value == "buy"


class TestBreakoutVolumeScoringEngine:
    """测试放量突破评分引擎"""

    def test_get_rules(self):
        """测试获取规则"""
        from src.strategy.scoring import BreakoutVolumeScoringEngine

        rules = BreakoutVolumeScoringEngine.get_rules()

        assert len(rules) > 0

    def test_calculate_strong_breakout(self):
        """测试强势突破"""
        from src.strategy.scoring import BreakoutVolumeScoringEngine

        market_data = {
            "volume_ratio": 3.0,  # 强放量
            "breakout_ratio": 0.05,  # 突破阻力位
            "close": 100,
            "high": 101,
            "consolidation_days": 40,  # 长期横盘
        }

        result = BreakoutVolumeScoringEngine.calculate(market_data)

        assert result.score >= 70
        assert result.signal.value == "buy"

    def test_calculate_fake_breakout(self):
        """测试假突破"""
        from src.strategy.scoring import BreakoutVolumeScoringEngine

        market_data = {
            "volume_ratio": 1.0,  # 无量
            "close": 95,
            "high": 102,  # 收盘远离最高价
            "close_near_high": False,
            "next_day_drop": -0.05,  # 次日大幅回落
        }

        result = BreakoutVolumeScoringEngine.calculate(market_data)

        # volume_ratio < 1.2 触发 weak_volume (-10) + next_day_drop 触发 pullback_risk (-15) = -25
        # 基础分 50 - 25 = 25 <= 30
        assert result.score <= 30


class TestGetStrategyEngine:
    """测试获取策略引擎"""

    def test_get_momentum_engine(self):
        """测试获取动量引擎"""
        from src.strategy.scoring import get_strategy_engine, MomentumScoringEngine

        engine = get_strategy_engine("momentum_trend")

        assert engine is MomentumScoringEngine

    def test_get_value_engine(self):
        """测试获取价值引擎"""
        from src.strategy.scoring import get_strategy_engine, ValueReversalScoringEngine

        engine = get_strategy_engine("value_reversal")

        assert engine is ValueReversalScoringEngine

    def test_get_breakout_engine(self):
        """测试获取突破引擎"""
        from src.strategy.scoring import get_strategy_engine, BreakoutVolumeScoringEngine

        engine = get_strategy_engine("breakout_vol")

        assert engine is BreakoutVolumeScoringEngine

    def test_get_nonexistent_engine(self):
        """测试获取不存在的引擎"""
        from src.strategy.scoring import get_strategy_engine

        engine = get_strategy_engine("nonexistent")

        assert engine is None


class TestMarketDataPreparer:
    """测试市场数据准备器"""

    def test_calculate_sma(self):
        """测试计算简单移动平均"""
        from src.strategy.data_preparer import MarketDataPreparer

        prices = [100, 101, 102, 103, 104, 105]
        ma = MarketDataPreparer._calculate_sma(prices, 3)

        assert len(ma) == len(prices)
        # 前2个应该是0（数据不足）
        assert ma[0] == 0.0
        assert ma[1] == 0.0
        # 第3个是前3个的平均
        assert ma[2] == 101.0
        # 最后一个
        assert ma[-1] == 104.0

    def test_calculate_sma_short_data(self):
        """测试数据不足时的 SMA"""
        from src.strategy.data_preparer import MarketDataPreparer

        prices = [100, 101]
        ma = MarketDataPreparer._calculate_sma(prices, 5)

        assert len(ma) == 2
        assert all(m == 0.0 for m in ma)

    def test_calculate_slope(self):
        """测试计算斜率"""
        from src.strategy.data_preparer import MarketDataPreparer

        # 递增序列，斜率为正
        values = [100, 101, 102, 103, 104, 105]
        slope = MarketDataPreparer._calculate_slope(values, period=5)

        assert slope > 0

    def test_calculate_slope_zero(self):
        """测试斜率为零"""
        from src.strategy.data_preparer import MarketDataPreparer

        values = [100, 100, 100, 100, 100, 100]
        slope = MarketDataPreparer._calculate_slope(values, period=5)

        assert slope == 0.0

    def test_calculate_volume_ratio(self):
        """测试计算量比"""
        from src.strategy.data_preparer import MarketDataPreparer

        volumes = [100, 110, 120, 130, 150]
        ratio = MarketDataPreparer._calculate_volume_ratio(volumes, period=5)

        # 最后一个成交量 / 平均成交量
        expected = 150 / (sum(volumes) / 5)
        assert abs(ratio - expected) < 0.01

    def test_calculate_volume_ratio_short(self):
        """测试数据不足时的量比"""
        from src.strategy.data_preparer import MarketDataPreparer

        volumes = [100, 101]
        ratio = MarketDataPreparer._calculate_volume_ratio(volumes, period=5)

        assert ratio == 1.0

    def test_prepare_from_df(self):
        """测试从 DataFrame 准备数据"""
        from src.strategy.data_preparer import MarketDataPreparer

        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=30),
            "open": [100 + i for i in range(30)],
            "high": [105 + i for i in range(30)],
            "low": [95 + i for i in range(30)],
            "close": [100 + i for i in range(30)],
            "volume": [1000000 * (i + 1) for i in range(30)],
        })

        data = MarketDataPreparer.prepare_from_df(df)

        assert "close" in data
        assert "ma5" in data
        assert "ma10" in data
        assert "ma20" in data
        assert "ma20_slope" in data
        assert "n20_gain_pct" in data

    def test_prepare_from_empty_df(self):
        """测试空 DataFrame"""
        from src.strategy.data_preparer import MarketDataPreparer

        df = pd.DataFrame()

        data = MarketDataPreparer.prepare_from_df(df)

        assert data == {}

    def test_normalize_columns(self):
        """测试标准化列名"""
        from src.strategy.data_preparer import MarketDataPreparer

        # 测试 finshare 格式
        df = pd.DataFrame({
            "trade_date": pd.date_range("2024-01-01", periods=5),
            "open_price": [100, 101, 102, 103, 104],
            "high_price": [105, 106, 107, 108, 109],
            "low_price": [95, 96, 97, 98, 99],
            "close_price": [100, 101, 102, 103, 104],
            "volume": [100, 110, 120, 130, 140],
        })

        normalized = MarketDataPreparer._normalize_columns(df)

        assert "date" in normalized.columns
        assert "open" in normalized.columns
        assert "high" in normalized.columns
        assert "low" in normalized.columns
        assert "close" in normalized.columns

    def test_prepare_with_money_flow(self):
        """测试添加资金流向"""
        from src.strategy.data_preparer import MarketDataPreparer

        base_data = {"close": 100}
        money_flow = {
            "net_inflow_main": 1000000,
            "net_inflow_main_ratio": 15,
            "continuous_inflow_days": 3
        }

        result = MarketDataPreparer.prepare_with_money_flow(base_data, money_flow)

        assert result["main_net_inflow"] == 1000000
        assert result["main_net_inflow_ratio"] == 15
        assert result["continuous_inflow_days"] == 3

    def test_prepare_with_indicators(self):
        """测试添加技术指标"""
        from src.strategy.data_preparer import MarketDataPreparer

        base_data = {"close": 100}
        indicators = {
            "rsi": 65,
            "macd": 0.5,
            "atr": 2.0
        }

        result = MarketDataPreparer.prepare_with_indicators(base_data, indicators)

        assert result["rsi"] == 65
        assert result["macd"] == 0.5
        assert result["atr"] == 2.0


class TestFinancialDataPreparer:
    """测试财务数据准备器"""

    def test_prepare_from_financials_empty(self):
        """测试空财务数据"""
        from src.strategy.data_preparer import FinancialDataPreparer

        df = pd.DataFrame()

        data = FinancialDataPreparer.prepare_from_financials(df)

        assert data == {}

    def test_prepare_from_dict(self):
        """测试从字典准备"""
        from src.strategy.data_preparer import FinancialDataPreparer

        financial_data = {
            "pe": 15,
            "pb": 2.5,
            "roe": 12,
            "debt_ratio": 50
        }

        data = FinancialDataPreparer.prepare_from_dict(financial_data)

        assert data["pe"] == 15
        assert data["pb"] == 2.5
        assert data["roe"] == 12
        assert data["debt_ratio"] == 50

    def test_prepare_from_dict_defaults(self):
        """测试字典默认值"""
        from src.strategy.data_preparer import FinancialDataPreparer

        data = FinancialDataPreparer.prepare_from_dict({})

        assert data["pe"] == 50
        assert data["pb"] == 3
        assert data["roe"] == 0


class TestStrategyExecutor:
    """测试策略执行器"""

    def test_init(self):
        """测试初始化"""
        from src.strategy.executor import StrategyExecutor

        executor = StrategyExecutor()

        assert executor.strategy_manager is not None
        assert executor.data_preparer is not None
        assert executor.financial_preparer is not None

    def test_create_neutral_signal(self):
        """测试创建中性信号"""
        from src.strategy.executor import StrategyExecutor

        executor = StrategyExecutor()

        signal = executor._create_neutral_signal("测试原因")

        assert signal.strategy_name == "neutral"
        assert signal.signal == "hold"
        assert signal.score == 50

    def test_create_empty_result(self):
        """测试创建空结果"""
        from src.strategy.executor import StrategyExecutor

        executor = StrategyExecutor()

        result = executor._create_empty_result("600519", "贵州茅台")

        assert result.stock_code == "600519"
        assert result.stock_name == "贵州茅台"
        assert result.overall_signal == "hold"
        assert result.overall_score == 50
        assert len(result.signals) == 0

    def test_score_to_signal_str(self):
        """测试评分转换为信号"""
        from src.strategy.executor import StrategyExecutor

        executor = StrategyExecutor()

        # 买入信号
        assert executor._score_to_signal_str(80) == "buy"
        assert executor._score_to_signal_str(70) == "buy"

        # 卖出信号
        assert executor._score_to_signal_str(20) == "sell"
        assert executor._score_to_signal_str(30) == "sell"

        # 持有信号
        assert executor._score_to_signal_str(50) == "hold"

    def test_analyze_with_strategy_nonexistent(self):
        """测试分析不存在的策略"""
        from src.strategy.executor import StrategyExecutor

        executor = StrategyExecutor()

        signal = executor.analyze_with_strategy(
            "600519",
            "贵州茅台",
            "nonexistent_strategy",
            {"close": 100}
        )

        assert signal.signal == "hold"
        assert "不存在" in signal.reasoning


class TestStrategySignal:
    """测试策略信号"""

    def test_signal_creation(self):
        """测试创建信号"""
        from src.strategy.executor import StrategySignal

        signal = StrategySignal(
            strategy_name="test",
            display_name="测试",
            signal="buy",
            confidence=0.8,
            score=75,
            reasoning="买入理由"
        )

        assert signal.strategy_name == "test"
        assert signal.signal == "buy"
        assert signal.confidence == 0.8
        assert signal.score == 75

    def test_signal_with_price_levels(self):
        """测试带价格点位的信号"""
        from src.strategy.executor import StrategySignal

        signal = StrategySignal(
            strategy_name="test",
            display_name="测试",
            signal="buy",
            confidence=0.8,
            score=75,
            reasoning="买入理由",
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=120.0
        )

        assert signal.entry_price == 100.0
        assert signal.stop_loss == 95.0
        assert signal.take_profit == 120.0


class TestStrategyAnalysisResult:
    """测试策略分析结果"""

    def test_result_creation(self):
        """测试创建分析结果"""
        from src.strategy.executor import StrategyAnalysisResult
        from src.strategy.executor import StrategySignal

        signal = StrategySignal(
            strategy_name="test",
            display_name="测试",
            signal="buy",
            confidence=0.8,
            score=75,
            reasoning="买入理由"
        )

        result = StrategyAnalysisResult(
            stock_code="600519",
            stock_name="贵州茅台",
            signals=[signal],
            overall_signal="buy",
            overall_score=75,
            overall_confidence=0.8,
            active_strategies=["test"],
            analysis_time=datetime.now().isoformat()
        )

        assert result.stock_code == "600519"
        assert result.overall_signal == "buy"
        assert len(result.signals) == 1
        assert "test" in result.active_strategies

    def test_result_with_metadata(self):
        """测试带元数据的分析结果"""
        from src.strategy.executor import StrategyAnalysisResult

        result = StrategyAnalysisResult(
            stock_code="600519",
            stock_name="贵州茅台",
            signals=[],
            overall_signal="hold",
            overall_score=50,
            overall_confidence=0.5,
            active_strategies=[],
            market_data={"close": 100},
            financial_data={"pe": 15},
            analysis_time=datetime.now().isoformat()
        )

        assert result.market_data is not None
        assert result.financial_data is not None
        assert result.market_data["close"] == 100
        assert result.financial_data["pe"] == 15