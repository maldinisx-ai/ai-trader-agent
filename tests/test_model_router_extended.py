# -*- coding: utf-8 -*-
"""
测试模型路由器 - 扩展测试

TDD 流程: RED → GREEN → REFACTOR
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

# 确保模块被导入以正确收集覆盖率
import core.model_router
import core.schemas
from core.model_router import (
    ModelRouter,
    ModelType,
    ModelConfig,
    APIProvider,
    TokenBudget,
    TokenUsage,
    SystemHaltedError,
    TokenBudgetExceededError,
    ModelCallError,
    ModelUnavailableError,
    create_model_router,
)
from core.schemas import AgentContext, Decision, SurvivalLevel, Position, MarketRegime


# ============================================
# TokenBudget 测试
# ============================================

class TestTokenBudget:
    """测试 Token 预算配置"""

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

    def test_total_property(self):
        """测试总预算计算"""
        budget = TokenBudget()
        expected = 2000 + 10000 + 30000 + 20000 + 50000 + 10000
        assert budget.total == expected

    def test_max_input_tokens(self):
        """测试最大输入 Token"""
        budget = TokenBudget()
        assert budget.max_input_tokens == budget.total - budget.output

    def test_custom_budget(self):
        """测试自定义预算"""
        budget = TokenBudget(
            system=1000,
            working_memory=5000,
            episodic=10000,
            semantic=5000,
            market_data=20000,
            output=5000,
            buffer=30000,
        )
        assert budget.system == 1000
        assert budget.total == 46000


# ============================================
# TokenUsage 测试
# ============================================

class TestTokenUsage:
    """测试 Token 使用统计"""

    def test_default_usage(self):
        """测试默认使用量"""
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_tokens == 0

    def test_cost_calculation(self):
        """测试成本估算"""
        # Claude 定价: $3/M input, $15/M output
        usage = TokenUsage(
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        expected_cost = 3.0 + 15.0  # $3 input + $15 output
        assert usage.cost == expected_cost

    def test_partial_cost(self):
        """测试部分 Token 成本"""
        usage = TokenUsage(
            input_tokens=500_000,
            output_tokens=200_000,
        )
        expected_cost = (500_000 * 3 / 1_000_000) + (200_000 * 15 / 1_000_000)
        assert abs(usage.cost - expected_cost) < 0.01

    def test_timestamp_default(self):
        """测试默认时间戳"""
        usage = TokenUsage()
        assert isinstance(usage.timestamp, datetime)

    def test_custom_timestamp(self):
        """测试自定义时间戳"""
        now = datetime.now()
        usage = TokenUsage(timestamp=now)
        assert usage.timestamp == now


# ============================================
# ModelConfig 测试
# ============================================

class TestModelConfig:
    """测试模型配置"""

    def test_api_config(self):
        """测试 API 模型配置"""
        config = ModelConfig(
            model_type=ModelType.API,
            model_name="claude-sonnet-4-6",
            api_key="test-key",
            api_provider=APIProvider.ANTHROPIC,
            max_tokens=4096,
            temperature=0.7,
        )
        assert config.model_type == ModelType.API
        assert config.model_name == "claude-sonnet-4-6"
        assert config.api_key == "test-key"
        assert config.api_provider == APIProvider.ANTHROPIC

    def test_local_config(self):
        """测试本地模型配置"""
        config = ModelConfig(
            model_type=ModelType.LOCAL,
            model_name="qwen2.5:7b",
            base_url="http://localhost:11434",
            max_tokens=2048,
        )
        assert config.model_type == ModelType.LOCAL
        assert config.base_url == "http://localhost:11434"
        assert config.api_key is None

    def test_priority_field(self):
        """测试优先级字段"""
        config = ModelConfig(
            model_type=ModelType.API,
            model_name="test-model",
            priority=1,
        )
        assert config.priority == 1


# ============================================
# ModelRouter 初始化测试
# ============================================

class TestModelRouterInit:
    """测试模型路由器初始化"""

    def test_init_with_defaults(self):
        """测试默认初始化"""
        router = ModelRouter()
        assert router.api_config is None
        assert router.third_party_config is None
        assert router.local_config is None
        assert router.enable_local is False
        assert router._daily_tokens == 0
        assert router._daily_cost == 0.0
        assert router._daily_limit == 1_000_000

    def test_init_with_configs(self):
        """测试带配置初始化"""
        api_config = ModelConfig(
            model_type=ModelType.API,
            model_name="test-model",
            api_key="test-key",
            api_provider=APIProvider.ANTHROPIC,
        )
        router = ModelRouter(api_config=api_config)
        assert router.api_config == api_config

    def test_init_with_custom_budget(self):
        """测试自定义预算"""
        budget = TokenBudget(system=1000)
        router = ModelRouter(token_budget=budget)
        assert router.token_budget == budget

    def test_init_with_enable_local(self):
        """测试启用本地模型"""
        router = ModelRouter(enable_local=True)
        assert router.enable_local is True


# ============================================
# ModelRouter 初始化环境变量测试
# ============================================

class TestModelRouterEnvInit:
    """测试从环境变量初始化"""

    @pytest.mark.asyncio
    async def test_initialize_from_env_success(self):
        """测试成功从环境变量初始化"""
        with patch.dict(
            "os.environ",
            {
                "ANTHROPIC_AUTH_TOKEN": "test-token-123",
                "ANTHROPIC_BASE_URL": "https://test-url.com",
                "ANTHROPIC_MODEL": "claude-sonnet-4-6",
            },
        ):
            router = ModelRouter()
            with patch("core.model_router.AsyncAnthropic"):
                await router.initialize()
                assert router._api_available is True
                assert len(router._api_providers) == 1
                assert router._api_providers[0].api_provider == APIProvider.ALIYUN

    @pytest.mark.asyncio
    async def test_initialize_from_env_no_token(self):
        """测试缺少环境变量"""
        with patch.dict("os.environ", {}, clear=True):
            router = ModelRouter()
            with pytest.raises(ModelUnavailableError):
                await router._initialize_from_env()

    @pytest.mark.asyncio
    async def test_initialize_from_env_invalid_token(self):
        """测试无效的 Token"""
        with patch.dict("os.environ", {"ANTHROPIC_AUTH_TOKEN": "sk-ant-xxx"}):
            router = ModelRouter()
            with pytest.raises(ModelUnavailableError):
                await router._initialize_from_env()


# ============================================
# ModelRouter 生成决策测试
# ============================================

class TestModelRouterGenerateDecision:
    """测试生成决策"""

    @pytest.fixture
    def router(self):
        """创建路由器实例"""
        return ModelRouter()

    @pytest.fixture
    def context(self):
        """创建测试上下文"""
        return AgentContext(
            initial_cash=100000.0,
            current_cash=100000.0,
            total_value=100000.0,
            survival_level=SurvivalLevel.NORMAL,
            market_regime=MarketRegime.BULL,
            max_position_ratio=0.3,
            positions=[],
            user_input="分析市场",
        )

    @pytest.mark.asyncio
    async def test_generate_decision_dead_survival(self, router, context):
        """测试 DEAD 生存等级抛出异常"""
        context.survival_level = SurvivalLevel.DEAD
        with pytest.raises(SystemHaltedError):
            await router.generate_decision(context)

    @pytest.mark.asyncio
    async def test_generate_decision_token_limit_exceeded(self, router, context):
        """测试 Token 预算超限"""
        router._daily_tokens = 1_000_001
        with pytest.raises(TokenBudgetExceededError):
            await router.generate_decision(context)

    @pytest.mark.asyncio
    async def test_generate_decision_success(self, router, context):
        """测试成功生成决策"""
        # Mock the fallback method
        expected_decision = Decision(
            action="hold",
            confidence=0.7,
            reasoning="测试推理",
            is_final=True,
        )
        router._call_with_fallback = AsyncMock(return_value=expected_decision)

        result = await router.generate_decision(context)
        assert result.action == "hold"
        assert result.confidence == 0.7


# ============================================
# ModelRouter 调用降级测试
# ============================================

class TestModelRouterFallback:
    """测试降级调用"""

    @pytest.fixture
    def router(self):
        """创建路由器实例"""
        router = ModelRouter()
        router._api_clients = [
            {
                "client": Mock(),
                "config": ModelConfig(
                    model_type=ModelType.API,
                    model_name="test-model",
                    api_provider=APIProvider.ALIYUN,
                ),
                "available": True,
            }
        ]
        router._call_client = AsyncMock()
        return router

    @pytest.fixture
    def context(self):
        """创建测试上下文"""
        return AgentContext(
            initial_cash=100000.0,
            current_cash=100000.0,
            total_value=100000.0,
            survival_level=SurvivalLevel.NORMAL,
            market_regime=MarketRegime.BULL,
            max_position_ratio=0.3,
            positions=[],
            user_input="分析市场",
        )

    @pytest.mark.asyncio
    async def test_call_with_fallback_success(self, router, context):
        """测试成功调用"""
        expected_decision = Decision(
            action="buy",
            symbol="600519",
            quantity=100,
            confidence=0.8,
            reasoning="看涨",
            is_final=True,
        )
        router._call_client.return_value = expected_decision

        result = await router._call_with_fallback(context)
        assert result.action == "buy"
        assert result.symbol == "600519"

    @pytest.mark.asyncio
    async def test_call_with_fallback_all_unavailable(self, router, context):
        """测试所有模型不可用"""
        router._api_clients[0]["available"] = False

        with pytest.raises(ModelCallError):
            await router._call_with_fallback(context)

    @pytest.mark.asyncio
    async def test_call_with_fallback_auto_skip(self, router, context):
        """测试自动跳过不可用模型"""
        # Set first client as unavailable
        router._api_clients[0]["available"] = False

        # Add second available client
        router._api_clients.append({
            "client": Mock(),
            "config": ModelConfig(
                model_type=ModelType.API,
                model_name="backup-model",
                api_provider=APIProvider.ZHIPU,
            ),
            "available": True,
        })

        expected_decision = Decision(
            action="hold",
            confidence=0.6,
            reasoning="观望",
            is_final=True,
        )
        router._call_client.return_value = expected_decision

        result = await router._call_with_fallback(context)
        assert result.action == "hold"


# ============================================
# ModelRouter 解析决策测试
# ============================================

class TestModelRouterParseDecision:
    """测试解析决策"""

    @pytest.fixture
    def router(self):
        """创建路由器实例"""
        return ModelRouter()

    def test_parse_decision_valid_json(self, router):
        """测试解析有效 JSON"""
        response = '''```json
{
    "action": "buy",
    "symbol": "600519",
    "quantity": 100,
    "price": 1800.0,
    "confidence": 0.85,
    "reasoning": "技术面强势",
    "is_final": true
}
```'''
        result = router._parse_decision(response, "test-model")
        assert result.action == "buy"
        assert result.symbol == "600519"
        assert result.quantity == 100
        assert result.price == 1800.0
        assert result.confidence == 0.85

    def test_parse_decision_json_without_markdown(self, router):
        """测试解析无 markdown 标记的 JSON"""
        response = '{"action": "sell", "symbol": "600519", "quantity": 100, "confidence": 0.7, "reasoning": "止盈", "is_final": true}'
        result = router._parse_decision(response, "test-model")
        assert result.action == "sell"
        assert result.quantity == 100

    def test_parse_decision_invalid_action(self, router):
        """测试无效的 action 值"""
        response = '{"action": "invalid", "confidence": 0.5}'
        result = router._parse_decision(response, "test-model")
        # 应该回退到 wait
        assert result.action == "wait"

    def test_parse_decision_missing_fields(self, router):
        """测试缺少字段"""
        response = '{"action": "hold"}'
        result = router._parse_decision(response, "test-model")
        assert result.action == "hold"
        assert result.confidence == 0.5  # 默认值
        assert result.is_final is True  # 默认值

    def test_parse_decision_no_json(self, router):
        """测试无 JSON 内容"""
        response = "这是一段普通文本，没有 JSON"
        result = router._parse_decision(response, "test-model")
        assert result.action == "wait"
        assert result.confidence == 0.0
        assert "无法解析" in result.reasoning

    def test_parse_decision_malformed_json(self, router):
        """测试格式错误的 JSON"""
        response = '{"action": "buy", "invalid": }'
        result = router._parse_decision(response, "test-model")
        assert result.action == "wait"
        assert "解析失败" in result.reasoning


# ============================================
# ModelRouter 融合决策测试
# ============================================

class TestModelRouterMergeDecisions:
    """测试融合决策"""

    @pytest.fixture
    def router(self):
        """创建路由器实例"""
        return ModelRouter()

    @pytest.fixture
    def context(self):
        """创建测试上下文"""
        return AgentContext(
            initial_cash=100000.0,
            current_cash=100000.0,
            total_value=100000.0,
            survival_level=SurvivalLevel.NORMAL,
            market_regime=MarketRegime.BULL,
            max_position_ratio=0.3,
            positions=[],
            user_input="分析市场",
        )

    def test_merge_both_none(self, router, context):
        """测试两个决策都为空"""
        result = router._merge_decisions(None, None, context)
        assert result.action == "wait"
        assert result.confidence == 0.0

    def test_merge_only_api(self, router, context):
        """测试只有 API 决策"""
        api_decision = Decision(
            action="buy",
            symbol="600519",
            quantity=100,
            confidence=0.8,
            reasoning="API 推荐",
            is_final=True,
        )
        result = router._merge_decisions(api_decision, None, context)
        assert result.action == "buy"
        assert result.symbol == "600519"

    def test_merge_only_local(self, router, context):
        """测试只有本地决策"""
        local_decision = Decision(
            action="sell",
            symbol="600519",
            quantity=100,
            confidence=0.7,
            reasoning="本地推荐",
            is_final=True,
        )
        result = router._merge_decisions(None, local_decision, context)
        assert result.action == "sell"

    def test_merge_same_action(self, router, context):
        """测试相同决策"""
        api_decision = Decision(
            action="buy",
            symbol="600519",
            quantity=100,
            confidence=0.8,
            reasoning="API 推荐",
            is_final=True,
        )
        local_decision = Decision(
            action="buy",
            symbol="600519",
            quantity=100,
            confidence=0.7,
            reasoning="本地推荐",
            is_final=True,
        )
        result = router._merge_decisions(api_decision, local_decision, context)
        assert result.action == "buy"
        assert result.confidence == 0.8  # 取更高置信度
        assert "[融合]" in result.reasoning

    def test_merge_conflict_with_wait(self, router, context):
        """测试冲突，有一个是 wait"""
        api_decision = Decision(
            action="buy",
            symbol="600519",
            quantity=100,
            confidence=0.8,
            reasoning="API 推荐",
            is_final=True,
        )
        local_decision = Decision(
            action="wait",
            confidence=0.7,
            reasoning="本地观望",
            is_final=True,
        )
        result = router._merge_decisions(api_decision, local_decision, context)
        assert result.action == "wait"
        assert result.confidence < 0.8  # 降低置信度

    def test_merge_conflict_with_hold(self, router, context):
        """测试冲突，有一个是 hold"""
        api_decision = Decision(
            action="buy",
            symbol="600519",
            quantity=100,
            confidence=0.8,
            reasoning="API 推荐",
            is_final=True,
        )
        local_decision = Decision(
            action="hold",
            confidence=0.7,
            reasoning="本地持有",
            is_final=True,
        )
        result = router._merge_decisions(api_decision, local_decision, context)
        assert result.action == "hold"

    def test_merge_conflict_buy_sell(self, router, context):
        """测试买卖冲突"""
        api_decision = Decision(
            action="buy",
            symbol="600519",
            quantity=100,
            confidence=0.9,
            reasoning="API 看涨",
            is_final=True,
        )
        local_decision = Decision(
            action="sell",
            symbol="600519",
            quantity=100,
            confidence=0.6,
            reasoning="本地看跌",
            is_final=True,
        )
        result = router._merge_decisions(api_decision, local_decision, context)
        assert result.action == "buy"  # 选择高置信度
        assert result.confidence == 0.9 * 0.9  # 降低 10%


# ============================================
# ModelRouter 提示词构建测试
# ============================================

class TestModelRouterBuildPrompt:
    """测试构建提示词"""

    @pytest.fixture
    def router(self):
        """创建路由器实例"""
        return ModelRouter()

    @pytest.fixture
    def context(self):
        """创建测试上下文"""
        return AgentContext(
            initial_cash=100000.0,
            current_cash=100000.0,
            total_value=100000.0,
            survival_level=SurvivalLevel.NORMAL,
            market_regime=MarketRegime.BULL,
            max_position_ratio=0.3,
            positions=[],
            user_input="分析贵州茅台",
        )

    def test_build_prompt_basic(self, router, context):
        """测试基本提示词"""
        prompt = router._build_prompt(context)
        assert "100,000.00 元" in prompt
        assert "0.00%" in prompt  # 回撤率 (total_value = initial_cash)
        assert "normal" in prompt
        assert "bull" in prompt
        assert "分析贵州茅台" in prompt

    def test_build_prompt_with_positions(self, router, context):
        """测试带持仓的提示词"""
        from datetime import datetime
        position = Position(
            symbol="600519",
            shares=100,
            avg_cost=1700.0,
            current_price=1800.0,
            opened_at=datetime.now(),
        )
        context.positions = [position]
        prompt = router._build_prompt(context)
        assert "600519" in prompt
        assert "100 股" in prompt
        assert "1700.00" in prompt
        assert "1800.00" in prompt

    def test_build_prompt_with_memories(self, router, context):
        """测试带记忆的提示词"""
        memories = {
            "episodic": "上次买入盈利",
            "semantic": "茅台是好公司",
            "reflections": "长期持有策略",
        }
        prompt = router._build_prompt(context, memories=memories)
        assert "上次买入盈利" in prompt
        assert "茅台是好公司" in prompt
        assert "长期持有策略" in prompt

    def test_build_prompt_conservative_mode(self, router, context):
        """测试保守模式提示词"""
        prompt = router._build_prompt(context, conservative=True)
        assert "保守模式" in prompt
        assert "保守策略" in prompt
        assert "降低风险" in prompt

    def test_build_prompt_with_market_data(self, router, context):
        """测试带市场数据的提示词"""
        market_data = "上证指数: 3000点"
        prompt = router._build_prompt(context, market_data=market_data)
        assert "上证指数: 3000点" in prompt


# ============================================
# ModelRouter Token 统计测试
# ============================================

class TestModelRouterTokenStats:
    """测试 Token 统计"""

    def test_get_token_usage(self):
        """测试获取 Token 使用量"""
        router = ModelRouter()
        router._daily_tokens = 100000
        usage = router.get_token_usage()
        assert usage.total_tokens == 100000
        assert usage.input_tokens == 50000  # 估算
        assert usage.output_tokens == 50000

    def test_reset_daily_usage(self):
        """测试重置每日使用量"""
        router = ModelRouter()
        router._daily_tokens = 50000
        router._daily_cost = 10.0
        router.reset_daily_usage()
        assert router._daily_tokens == 0
        assert router._daily_cost == 0.0


# ============================================
# 工厂函数测试
# ============================================

class TestCreateModelRouter:
    """测试工厂函数"""

    @pytest.mark.asyncio
    async def test_create_with_api_key(self):
        """测试使用 API Key 创建"""
        with patch("core.model_router.AsyncAnthropic"):
            router = await create_model_router(
                api_key="test-key",
                third_party_api_key=None,
                local_url=None,
                enable_local=False,
            )
            assert router is not None
            assert isinstance(router, ModelRouter)

    @pytest.mark.asyncio
    async def test_create_with_third_party(self):
        """测试使用第三方 API 创建"""
        with patch("core.model_router.AsyncOpenAI"):
            router = await create_model_router(
                api_key=None,
                third_party_api_key="test-third-key",
                third_party_base_url="https://test.com",
                third_party_model="glm-4-flash",
                local_url=None,
                enable_local=False,
            )
            assert router is not None

    @pytest.mark.asyncio
    async def test_create_with_local(self):
        """测试使用本地模型创建"""
        with patch("core.model_router.AsyncOpenAI"):
            with patch.object(ModelRouter, "_test_local_connection"):
                router = await create_model_router(
                    api_key=None,
                    third_party_api_key=None,
                    local_url="http://localhost:11434",
                    enable_local=True,
                )
                assert router is not None


# ============================================
# 异常测试
# ============================================

class TestModelRouterExceptions:
    """测试异常类"""

    def test_system_halted_error(self):
        """测试系统挂起异常"""
        error = SystemHaltedError("系统已挂起")
        assert "系统已挂起" in str(error)
        assert isinstance(error, Exception)

    def test_token_budget_exceeded_error(self):
        """测试 Token 超限异常"""
        error = TokenBudgetExceededError("Token 已用完")
        assert "Token 已用完" in str(error)

    def test_model_call_error(self):
        """测试模型调用异常"""
        error = ModelCallError("调用失败")
        assert "调用失败" in str(error)

    def test_model_unavailable_error(self):
        """测试模型不可用异常"""
        error = ModelUnavailableError("模型不可用")
        assert "模型不可用" in str(error)
