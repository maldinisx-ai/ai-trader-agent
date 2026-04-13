# -*- coding: utf-8 -*-
"""
测试双模型路由器
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 确保模块被导入以正确收集覆盖率
import core.model_router
import core.schemas
from core.schemas import (
    AgentContext,
    Decision,
    SurvivalLevel,
    MarketRegime,
    Position,
)
from core.model_router import (
    ModelRouter,
    ModelType,
    ModelConfig,
    TokenBudget,
    TokenUsage,
    SystemHaltedError,
    TokenBudgetExceededError,
    ModelUnavailableError,
    ModelCallError,
    create_model_router,
)


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def api_config():
    """API 模型配置"""
    return ModelConfig(
        model_type=ModelType.API,
        model_name="claude-sonnet-4-6",
        api_key="test-api-key",
    )


@pytest.fixture
def local_config():
    """本地模型配置"""
    return ModelConfig(
        model_type=ModelType.LOCAL,
        model_name="qwen2.5:7b",
        base_url="http://localhost:11434",
    )


@pytest.fixture
def normal_context():
    """正常状态的 Agent 上下文"""
    return AgentContext(
        user_input="分析当前市场并给出交易建议",
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
def loss_context():
    """亏损状态的 Agent 上下文"""
    return AgentContext(
        user_input="分析当前市场并给出交易建议",
        current_cash=850_000.0,
        total_value=900_000.0,
        initial_cash=1_000_000.0,
        positions=[],
        survival_level=SurvivalLevel.LOW_COMPUTE,
        market_regime=MarketRegime.BEAR,
        max_position_ratio=0.20,
        trading_enabled=True,
    )


@pytest.fixture
def dead_context():
    """DEAD 状态的 Agent 上下文"""
    return AgentContext(
        user_input="分析当前市场并给出交易建议",
        current_cash=600_000.0,
        total_value=650_000.0,
        initial_cash=1_000_000.0,
        positions=[],
        survival_level=SurvivalLevel.DEAD,
        market_regime=MarketRegime.BEAR,
        max_position_ratio=0.0,
        trading_enabled=False,
    )


@pytest.fixture
def context_with_positions():
    """有持仓的 Agent 上下文"""
    return AgentContext(
        user_input="分析当前持仓并给出建议",
        current_cash=500_000.0,
        total_value=1_000_000.0,
        initial_cash=1_000_000.0,
        positions=[
            Position(
                symbol="600519",
                shares=300,
                avg_cost=1650.0,
                current_price=1680.0,
                opened_at=datetime.now(),
            )
        ],
        survival_level=SurvivalLevel.NORMAL,
        market_regime=MarketRegime.BULL,
        max_position_ratio=0.30,
        trading_enabled=True,
    )


# ============================================
# TokenBudget 测试
# ============================================

class TestTokenBudget:
    """测试 Token 预算"""

    def test_default_budget(self):
        """测试默认预算"""
        budget = TokenBudget()
        assert budget.system == 2000
        assert budget.working_memory == 10000
        assert budget.episodic == 30000
        assert budget.semantic == 20000
        assert budget.market_data == 50000
        assert budget.output == 10000
        assert budget.buffer == 78000

    def test_total_calculation(self):
        """测试总预算计算"""
        budget = TokenBudget()
        # 总预算 = 2K + 10K + 30K + 20K + 50K + 10K = 122K
        assert budget.total == 122000

    def test_max_input_tokens(self):
        """测试最大输入 Token"""
        budget = TokenBudget()
        # 最大输入 = 总预算 - 输出预算 = 122K - 10K = 112K
        assert budget.max_input_tokens == 112000


# ============================================
# ModelRouter 初始化测试
# ============================================

class TestModelRouterInit:
    """测试 ModelRouter 初始化"""

    @pytest.mark.asyncio
    async def test_init_with_api_only(self, api_config):
        """测试仅 API 模型初始化"""
        router = ModelRouter(api_config=api_config, enable_local=False)
        assert router.api_config == api_config
        assert router.enable_local is False

    @pytest.mark.asyncio
    async def test_init_with_local_only(self, local_config):
        """测试仅本地模型初始化"""
        router = ModelRouter(local_config=local_config, enable_local=True)
        assert router.local_config == local_config
        assert router.enable_local is True

    @pytest.mark.asyncio
    async def test_init_with_both(self, api_config, local_config):
        """测试双模型初始化"""
        router = ModelRouter(
            api_config=api_config,
            local_config=local_config,
            enable_local=True,
        )
        assert router.api_config == api_config
        assert router.local_config == local_config

    @pytest.mark.asyncio
    async def test_no_available_models_raises_error(self):
        """测试无可用模型时抛出异常"""
        # Mock environment variables to be empty
        with patch.dict('os.environ', {
            'ANTHROPIC_AUTH_TOKEN': '',
            'THIRD_PARTY_API_KEY': '',
            'OLLAMA_BASE_URL': '',
        }):
            router = ModelRouter(
                api_config=None,
                third_party_config=None,
                local_config=None,
                enable_local=False,
            )
            with pytest.raises(ModelUnavailableError):
                await router.initialize()


# ============================================
# 决策生成测试
# ============================================

class TestGenerateDecision:
    """测试决策生成"""

    @pytest.mark.asyncio
    async def test_dead_level_raises_error(self, dead_context):
        """测试 DEAD 生存等级抛出异常"""
        router = ModelRouter()
        with pytest.raises(SystemHaltedError):
            await router.generate_decision(dead_context)

    @pytest.mark.asyncio
    async def test_token_budget_exceeded(self, normal_context):
        """测试 Token 预算超限"""
        router = ModelRouter()
        router._daily_tokens = 1_000_001  # 超过限制
        router._api_available = True

        with pytest.raises(TokenBudgetExceededError):
            await router.generate_decision(normal_context)


# ============================================
# 决策解析测试
# ============================================

class TestParseDecision:
    """测试决策解析"""

    def test_parse_valid_json_decision(self):
        """测试解析有效的 JSON 决策"""
        router = ModelRouter()
        response_text = '''```json
{
    "action": "buy",
    "symbol": "600519",
    "quantity": 100,
    "price": 1680.0,
    "confidence": 0.85,
    "reasoning": "技术面看涨",
    "is_final": true
}
```'''
        decision = router._parse_decision(response_text, "test-model")

        assert decision.action == "buy"
        assert decision.symbol == "600519"
        assert decision.quantity == 100
        assert decision.price == 1680.0
        assert decision.confidence == 0.85
        assert decision.is_final is True

    def test_parse_decision_without_code_block(self):
        """测试解析无代码块的 JSON 决策"""
        router = ModelRouter()
        response_text = '''{"action": "sell", "symbol": "600519", "quantity": 100, "confidence": 0.7, "reasoning": "止盈", "is_final": true}'''
        decision = router._parse_decision(response_text, "test-model")

        assert decision.action == "sell"
        assert decision.symbol == "600519"

    def test_parse_invalid_json_returns_wait(self):
        """测试无效 JSON 返回 wait"""
        router = ModelRouter()
        response_text = "这是一段普通文本，不是 JSON"
        decision = router._parse_decision(response_text, "test-model")

        assert decision.action == "wait"
        assert decision.confidence == 0.0

    def test_parse_with_invalid_action_defaults_to_wait(self):
        """测试无效 action 默认为 wait"""
        router = ModelRouter()
        response_text = '{"action": "invalid", "confidence": 0.5}'
        decision = router._parse_decision(response_text, "test-model")

        assert decision.action == "wait"

    def test_parse_hold_decision(self):
        """测试解析 hold 决策"""
        router = ModelRouter()
        response_text = '{"action": "hold", "confidence": 0.6, "reasoning": "维持现状"}'
        decision = router._parse_decision(response_text, "test-model")

        assert decision.action == "hold"


# ============================================
# 决策融合测试
# ============================================

class TestMergeDecisions:
    """测试决策融合"""

    def test_merge_both_api_and_local_agree(self):
        """测试两个模型决策一致"""
        router = ModelRouter()
        api_decision = Decision(
            action="buy",
            symbol="600519",
            quantity=100,
            price=1680.0,
            confidence=0.85,
            reasoning="API 认为看涨",
        )
        local_decision = Decision(
            action="buy",
            symbol="600519",
            quantity=100,
            price=1675.0,
            confidence=0.75,
            reasoning="本地认为看涨",
        )

        merged = router._merge_decisions(api_decision, local_decision, MagicMock())

        assert merged.action == "buy"
        assert merged.confidence == 0.85  # 使用更高的置信度
        assert "融合" in merged.reasoning

    def test_merge_api_only(self):
        """测试仅 API 模型有结果"""
        router = ModelRouter()
        api_decision = Decision(
            action="buy",
            symbol="600519",
            confidence=0.8,
            reasoning="API 认为看涨",
        )

        merged = router._merge_decisions(api_decision, None, MagicMock())

        assert merged.action == "buy"
        assert merged.confidence == 0.8

    def test_merge_local_only(self):
        """测试仅本地模型有结果"""
        router = ModelRouter()
        local_decision = Decision(
            action="sell",
            symbol="600519",
            confidence=0.7,
            reasoning="本地认为看跌",
        )

        merged = router._merge_decisions(None, local_decision, MagicMock())

        assert merged.action == "sell"

    def test_merge_conflicting_wait_vs_buy(self):
        """测试冲突：wait vs buy"""
        router = ModelRouter()
        api_decision = Decision(
            action="buy",
            symbol="600519",
            confidence=0.8,
            reasoning="API 认为看涨",
        )
        local_decision = Decision(
            action="wait",
            confidence=0.7,
            reasoning="本地建议等待",
        )

        merged = router._merge_decisions(api_decision, local_decision, MagicMock())

        assert merged.action == "wait"
        assert merged.confidence < 0.8  # 置信度降低
        assert "冲突" in merged.reasoning

    def test_merge_conflicting_buy_vs_sell(self):
        """测试冲突：buy vs sell"""
        router = ModelRouter()
        api_decision = Decision(
            action="buy",
            symbol="600519",
            confidence=0.9,
            reasoning="API 认为看涨",
        )
        local_decision = Decision(
            action="sell",
            symbol="600519",
            confidence=0.6,
            reasoning="本地认为看跌",
        )

        merged = router._merge_decisions(api_decision, local_decision, MagicMock())

        # 选择置信度更高的
        assert merged.action == "buy"
        assert merged.confidence == 0.9 * 0.9  # 降低 10%
        assert "冲突" in merged.reasoning

    def test_merge_both_none_returns_wait(self):
        """测试两个模型都无结果"""
        router = ModelRouter()
        context = MagicMock()

        merged = router._merge_decisions(None, None, context)

        assert merged.action == "wait"
        assert merged.confidence == 0.0


# ============================================
# 提示词构建测试
# ============================================

class TestBuildPrompt:
    """测试提示词构建"""

    def test_build_prompt_basic(self, normal_context):
        """测试基本提示词构建"""
        router = ModelRouter()
        prompt = router._build_prompt(normal_context)

        assert "800,000.00 元" in prompt  # 现金
        assert "1,000,000.00 元" in prompt  # 总资产
        assert "normal" in prompt  # 生存等级
        assert "sideways" in prompt  # 市场状态
        assert "分析当前市场并给出交易建议" in prompt  # 用户指令

    def test_build_prompt_with_positions(self, context_with_positions):
        """测试带持仓的提示词"""
        router = ModelRouter()
        prompt = router._build_prompt(context_with_positions)

        assert "600519" in prompt
        assert "300 股" in prompt

    def test_build_prompt_conservative_mode(self, normal_context):
        """测试保守模式提示词"""
        router = ModelRouter()
        prompt = router._build_prompt(normal_context, conservative=True)

        assert "保守模式" in prompt
        assert "降低风险" in prompt

    def test_build_prompt_with_memories(self, normal_context):
        """测试带记忆的提示词"""
        router = ModelRouter()
        memories = {
            "episodic": "之前买入茅台盈利 10%",
            "semantic": "牛市中可适当加仓",
            "reflections": "避免追高",
        }
        prompt = router._build_prompt(normal_context, memories=memories)

        assert "历史记忆" in prompt
        assert "之前买入茅台盈利 10%" in prompt
        assert "避免追高" in prompt


# ============================================
# Token 使用统计测试
# ============================================

class TestTokenUsage:
    """测试 Token 使用统计"""

    def test_get_token_usage(self):
        """测试获取 Token 使用"""
        router = ModelRouter()
        router._daily_tokens = 50_000

        usage = router.get_token_usage()

        assert usage.total_tokens == 50_000
        assert usage.input_tokens == 25_000  # 估算一半
        assert usage.output_tokens == 25_000

    def test_token_usage_cost_calculation(self):
        """测试 Token 成本计算"""
        usage = TokenUsage(
            input_tokens=100_000,
            output_tokens=10_000,
        )

        # 成本 = 100K * $3/M + 10K * $15/M = $0.30 + $0.15 = $0.45
        assert abs(usage.cost - 0.45) < 0.01

    def test_reset_daily_usage(self):
        """测试重置每日使用"""
        router = ModelRouter()
        router._daily_tokens = 50_000
        router._daily_cost = 10.0

        router.reset_daily_usage()

        assert router._daily_tokens == 0
        assert router._daily_cost == 0.0


# ============================================
# 生存等级路由测试
# ============================================

class TestSurvivalRouting:
    """测试生存等级路由"""

    @pytest.mark.asyncio
    async def test_normal_level_uses_fusion(self, normal_context):
        """测试 NORMAL 等级使用决策模式"""
        router = ModelRouter()
        # Mock _call_with_fallback 方法
        router._call_with_fallback = AsyncMock(return_value=Decision(
            action="hold",
            confidence=0.7,
            reasoning="决策",
        ))

        decision = await router.generate_decision(normal_context)

        assert decision.action == "hold"
        router._call_with_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_low_compute_uses_local_conservative(self, loss_context):
        """测试 LOW_COMPUTE 等级使用决策模式"""
        router = ModelRouter()
        # Mock _call_with_fallback 方法
        router._call_with_fallback = AsyncMock(return_value=Decision(
            action="hold",
            confidence=0.4,  # 保守模式降低
            reasoning="保守决策",
        ))

        decision = await router.generate_decision(loss_context)

        assert decision.action == "hold"

        assert decision.action == "hold"
        assert decision.confidence == 0.4


# ============================================
# ModelConfig 测试
# ============================================

class TestModelConfig:
    """测试模型配置"""

    def test_api_config(self):
        """测试 API 配置"""
        config = ModelConfig(
            model_type=ModelType.API,
            model_name="claude-sonnet-4-6",
            api_key="test-key",
        )
        assert config.model_type == ModelType.API
        assert config.api_key == "test-key"

    def test_local_config(self):
        """测试本地配置"""
        config = ModelConfig(
            model_type=ModelType.LOCAL,
            model_name="qwen2.5:7b",
            base_url="http://localhost:11434",
        )
        assert config.model_type == ModelType.LOCAL
        assert config.base_url == "http://localhost:11434"
