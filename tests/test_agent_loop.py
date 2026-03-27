# -*- coding: utf-8 -*-
"""
测试 ReAct 循环核心逻辑
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.schemas import (
    AgentContext,
    AgentResponse,
    Decision,
    SurvivalLevel,
    MarketRegime,
    Position,
    ToolResult,
    MarketState,
)
from core.agent_loop import (
    AgentLoop,
    LoopState,
    create_agent_loop,
)
from core.model_router import ModelRouter
from core.survival_rules import SurvivalRules, SurvivalState
from core.market_regime import MarketRegimeDetector


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def mock_model_router():
    """模拟模型路由器"""
    router = AsyncMock(spec=ModelRouter)
    return router


@pytest.fixture
def mock_survival_rules():
    """模拟生存规则"""
    rules = MagicMock(spec=SurvivalRules)
    rules.get_current_state.return_value = SurvivalState(
        level=SurvivalLevel.NORMAL,
        drawdown=0.0,
        max_position=0.30,
        trading_interval=60,
        last_update=datetime.now(),
    )
    rules.update_level.return_value = rules.get_current_state.return_value
    return rules


@pytest.fixture
def mock_market_detector():
    """模拟市场检测器"""
    detector = AsyncMock(spec=MarketRegimeDetector)
    detector.detect.return_value = MarketState(
        regime=MarketRegime.SIDEWAYS,
        confidence=0.7,
        max_position_ratio=0.3,
    )
    return detector


@pytest.fixture
def normal_context():
    """正常状态的上下文"""
    return AgentContext(
        user_input="分析市场并给出建议",
        current_cash=800_000.0,
        total_value=1_000_000.0,
        initial_cash=1_000_000.0,
        positions=[],
        survival_level=SurvivalLevel.NORMAL,
        market_regime=MarketRegime.SIDEWAYS,
        max_position_ratio=0.30,
        trading_enabled=True,
    )


@pytest.fixture
def sample_positions():
    """示例持仓"""
    return [
        Position(
            symbol="600519",
            shares=300,
            avg_cost=1650.0,
            current_price=1680.0,
            opened_at=datetime.now(),
        )
    ]


# ============================================
# LoopState 测试
# ============================================

class TestLoopState:
    """测试循环状态"""

    def test_initial_state(self):
        """测试初始状态"""
        state = LoopState(max_iterations=5)
        assert state.iteration == 0
        assert state.max_iterations == 5
        assert state.should_continue is True
        assert state.decision_chain == []

    def test_should_continue_true(self):
        """测试应该继续"""
        state = LoopState(max_iterations=5, iteration=3)
        assert state.should_continue is True

    def test_should_continue_false(self):
        """测试不应该继续"""
        state = LoopState(max_iterations=5, iteration=5)
        assert state.should_continue is False

    def test_elapsed_seconds(self):
        """测试已用时间"""
        state = LoopState()
        # 刚开始应该接近 0
        assert state.elapsed_seconds < 1.0


# ============================================
# AgentLoop 初始化测试
# ============================================

class TestAgentLoopInit:
    """测试 AgentLoop 初始化"""

    def test_init(self, mock_model_router, mock_survival_rules, mock_market_detector):
        """测试初始化"""
        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
        )

        assert loop.model_router == mock_model_router
        assert loop.survival_rules == mock_survival_rules
        assert loop.market_detector == mock_market_detector
        assert loop.max_iterations == 5
        assert loop._working_memory == {}
        assert loop._episodic_memory == []

    def test_init_with_custom_config(self, mock_model_router, mock_survival_rules, mock_market_detector):
        """测试自定义配置初始化"""
        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
            max_iterations=10,
            enable_logging=False,
        )

        assert loop.max_iterations == 10
        assert loop.enable_logging is False


# ============================================
# 上下文构建测试
# ============================================

class TestBuildContext:
    """测试上下文构建"""

    @pytest.mark.asyncio
    async def test_build_basic_context(
        self,
        mock_model_router,
        mock_survival_rules,
        mock_market_detector,
    ):
        """测试构建基本上下文"""
        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
        )

        context = await loop._build_context(
            user_input="分析市场",
            current_cash=800_000.0,
            total_value=1_000_000.0,
            initial_cash=1_000_000.0,
            positions=[],
        )

        assert context.user_input == "分析市场"
        assert context.current_cash == 800_000.0
        assert context.total_value == 1_000_000.0
        assert context.initial_cash == 1_000_000.0
        assert context.survival_level == SurvivalLevel.NORMAL
        assert context.market_regime == MarketRegime.SIDEWAYS
        assert context.max_position_ratio == 0.30

    @pytest.mark.asyncio
    async def test_build_context_with_positions(
        self,
        mock_model_router,
        mock_survival_rules,
        mock_market_detector,
        sample_positions,
    ):
        """测试带持仓的上下文构建"""
        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
        )

        context = await loop._build_context(
            user_input="分析持仓",
            current_cash=500_000.0,
            total_value=1_000_000.0,
            initial_cash=1_000_000.0,
            positions=sample_positions,
        )

        assert len(context.positions) == 1
        assert context.positions[0].symbol == "600519"
        assert context.position_value == 504_000.0  # 300 * 1680


# ============================================
# ReAct 循环测试
# ============================================

class TestReactLoop:
    """测试 ReAct 循环"""

    @pytest.mark.asyncio
    async def test_simple_hold_decision(
        self,
        mock_model_router,
        mock_survival_rules,
        mock_market_detector,
        normal_context,
    ):
        """测试简单的持有决策"""
        # 设置模拟返回
        mock_model_router.generate_decision.return_value = Decision(
            action="hold",
            confidence=0.7,
            reasoning="市场震荡，建议持有",
            is_final=True,
        )

        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
            enable_logging=False,
        )

        response = await loop.react_loop(
            user_input="分析市场",
            current_cash=800_000.0,
            total_value=1_000_000.0,
            initial_cash=1_000_000.0,
            positions=[],
        )

        assert response.success is True
        assert "持有" in response.message
        assert response.final_result["decision"]["action"] == "hold"
        assert response.final_result["iterations"] == 1

    @pytest.mark.asyncio
    async def test_multi_iteration_loop(
        self,
        mock_model_router,
        mock_survival_rules,
        mock_market_detector,
    ):
        """测试多迭代循环"""
        # 第一次调用：需要查询行情
        mock_model_router.generate_decision.side_effect = [
            Decision(
                action="wait",
                confidence=0.5,
                reasoning="需要查询行情",
                tools_to_use=["get_quote"],
                is_final=False,
            ),
            Decision(
                action="hold",
                confidence=0.7,
                reasoning="根据行情，建议持有",
                is_final=True,
            ),
        ]

        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
            enable_logging=False,
        )

        response = await loop.react_loop(
            user_input="分析茅台",
            current_cash=800_000.0,
            total_value=1_000_000.0,
            initial_cash=1_000_000.0,
            positions=[],
        )

        assert response.success is True
        assert response.final_result["iterations"] == 2
        assert len(response.actions_taken) == 1  # 一次工具调用

    @pytest.mark.asyncio
    async def test_max_iterations_exceeded(
        self,
        mock_model_router,
        mock_survival_rules,
        mock_market_detector,
    ):
        """测试超过最大迭代次数"""
        # 始终返回需要工具调用的决策
        mock_model_router.generate_decision.return_value = Decision(
            action="wait",
            confidence=0.5,
            reasoning="继续等待",
            tools_to_use=["get_quote"],  # 需要工具调用，继续循环
            is_final=False,
        )

        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
            max_iterations=3,
            enable_logging=False,
        )

        response = await loop.react_loop(
            user_input="分析市场",
            current_cash=800_000.0,
            total_value=1_000_000.0,
            initial_cash=1_000_000.0,
            positions=[],
        )

        assert response.success is True
        assert response.final_result["iterations"] == 3

    @pytest.mark.asyncio
    async def test_loop_with_error(
        self,
        mock_model_router,
        mock_survival_rules,
        mock_market_detector,
    ):
        """测试循环中的错误处理"""
        # 模拟错误
        mock_model_router.generate_decision.side_effect = Exception("模型调用失败")

        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
            enable_logging=False,
        )

        response = await loop.react_loop(
            user_input="分析市场",
            current_cash=800_000.0,
            total_value=1_000_000.0,
            initial_cash=1_000_000.0,
            positions=[],
        )

        assert response.success is False
        assert "模型调用失败" in response.message


# ============================================
# 记忆管理测试
# ============================================

class TestMemoryManagement:
    """测试记忆管理"""

    @pytest.mark.asyncio
    async def test_working_memory(
        self,
        mock_model_router,
        mock_survival_rules,
        mock_market_detector,
    ):
        """测试工作记忆"""
        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
        )

        # 设置工作记忆
        loop._working_memory["last_decision"] = "hold"

        memory = loop.get_working_memory()
        assert memory["last_decision"] == "hold"

    @pytest.mark.asyncio
    async def test_episodic_memory(
        self,
        mock_model_router,
        mock_survival_rules,
        mock_market_detector,
    ):
        """测试情节记忆"""
        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
        )

        # 添加情节记忆
        loop._episodic_memory.append({
            "timestamp": "2024-03-23T10:00:00",
            "action": "buy",
            "symbol": "600519",
        })

        memory = loop.get_episodic_memory()
        assert len(memory) == 1
        assert memory[0]["action"] == "buy"

    @pytest.mark.asyncio
    async def test_semantic_memory(
        self,
        mock_model_router,
        mock_survival_rules,
        mock_market_detector,
    ):
        """测试语义记忆"""
        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
        )

        # 添加语义记忆
        loop.add_semantic_memory("rule1", "牛市中可适当加仓")

        assert loop._semantic_memory["rule1"] == "牛市中可适当加仓"

    @pytest.mark.asyncio
    async def test_reset_memory(
        self,
        mock_model_router,
        mock_survival_rules,
        mock_market_detector,
    ):
        """测试重置记忆"""
        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
        )

        # 添加记忆
        loop._working_memory["test"] = "value"
        loop._episodic_memory.append({"test": "value"})
        loop._semantic_memory["test"] = "value"

        # 重置
        loop.reset_memory()

        assert loop._working_memory == {}
        assert loop._episodic_memory == []
        assert loop._semantic_memory == {}


# ============================================
# 统计信息测试
# ============================================

class TestStats:
    """测试统计信息"""

    @pytest.mark.asyncio
    async def test_get_stats(
        self,
        mock_model_router,
        mock_survival_rules,
        mock_market_detector,
    ):
        """测试获取统计信息"""
        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
        )

        loop._total_decisions = 10
        loop._total_tool_calls = 25
        loop._successful_trades = 5

        stats = loop.get_stats()

        assert stats["total_decisions"] == 10
        assert stats["total_tool_calls"] == 25
        assert stats["successful_trades"] == 5


# ============================================
# 工具参数构建测试
# ============================================

class TestBuildToolParams:
    """测试工具参数构建"""

    @pytest.mark.asyncio
    async def test_build_buy_params(
        self,
        mock_model_router,
        mock_survival_rules,
        mock_market_detector,
        normal_context,
    ):
        """测试构建买入参数"""
        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
        )

        decision = Decision(
            action="buy",
            symbol="600519",
            quantity=100,
            price=1680.0,
            confidence=0.8,
            reasoning="技术面看涨",
        )

        params = loop._build_tool_params(decision, normal_context)

        assert params["symbol"] == "600519"
        assert params["quantity"] == 100
        assert params["price"] == 1680.0

    @pytest.mark.asyncio
    async def test_build_hold_params(
        self,
        mock_model_router,
        mock_survival_rules,
        mock_market_detector,
        normal_context,
    ):
        """测试构建持有参数（无参数）"""
        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
        )

        decision = Decision(
            action="hold",
            confidence=0.7,
            reasoning="市场震荡，建议持有",
        )

        params = loop._build_tool_params(decision, normal_context)

        assert params == {}


# ============================================
# 消息构建测试
# ============================================

class TestBuildMessage:
    """测试消息构建"""

    @pytest.mark.asyncio
    async def test_build_buy_message(
        self,
        mock_model_router,
        mock_survival_rules,
        mock_market_detector,
    ):
        """测试构建买入消息"""
        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
        )

        state = LoopState()
        state.decision_chain.append({
            "decision": {
                "action": "buy",
                "symbol": "600519",
                "quantity": 100,
                "reasoning": "技术面看涨",
            },
            "iteration": 1,
            "timestamp": "2024-03-23T10:00:00",
        })

        message = loop._build_message(state)

        assert "买入" in message
        assert "600519" in message
        assert "100 股" in message

    @pytest.mark.asyncio
    async def test_build_empty_message(
        self,
        mock_model_router,
        mock_survival_rules,
        mock_market_detector,
    ):
        """测试构建空消息"""
        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
        )

        state = LoopState()

        message = loop._build_message(state)

        assert message == "未生成任何决策"


# ============================================
# 思考过程构建测试
# ============================================

class TestBuildThoughtProcess:
    """测试思考过程构建"""

    @pytest.mark.asyncio
    async def test_build_thought_process(
        self,
        mock_model_router,
        mock_survival_rules,
        mock_market_detector,
    ):
        """测试构建思考过程"""
        loop = AgentLoop(
            model_router=mock_model_router,
            survival_rules=mock_survival_rules,
            market_detector=mock_market_detector,
        )

        state = LoopState()
        state.decision_chain.append({
            "decision": {
                "action": "buy",
                "confidence": 0.8,
                "reasoning": "技术面看涨，均线多头排列",
            },
            "iteration": 1,
            "timestamp": "2024-03-23T10:00:00",
        })

        thought_process = loop._build_thought_process(state)

        assert "[迭代 1]" in thought_process
        assert "动作: buy" in thought_process
        assert "置信度: 0.80" in thought_process
