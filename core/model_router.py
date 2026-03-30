# -*- coding: utf-8 -*-
"""
双模型路由器

根据生存等级和 Token 预算，智能路由到 API 模型或本地模型。
支持融合决策和降级模式。
"""

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from decimal import Decimal

import httpx
from pydantic import BaseModel, Field

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from .schemas import (
    AgentContext,
    Decision,
    SurvivalLevel,
    DecisionChain,
    Trade,
)


# ============================================
# Token 预算配置
# ============================================

class TokenBudget(BaseModel):
    """Token 预算配置"""
    system: int = 2000
    working_memory: int = 10000
    episodic: int = 30000
    semantic: int = 20000
    market_data: int = 50000
    output: int = 10000
    buffer: int = 78000

    @property
    def total(self) -> int:
        """总预算"""
        return sum([
            self.system,
            self.working_memory,
            self.episodic,
            self.semantic,
            self.market_data,
            self.output,
        ])

    @property
    def max_input_tokens(self) -> int:
        """最大输入 Token 数"""
        return self.total - self.output


# 默认 Token 预算（基于 Claude 200K 上下文）
DEFAULT_TOKEN_BUDGET = TokenBudget()


# ============================================
# 模型配置
# ============================================

# ============================================
# 模型类型
# ============================================

class ModelType(str, Enum):
    """模型类型"""
    API = "api"           # API 模型 (Claude/OpenAI/GLM)
    LOCAL = "local"       # 本地 Ollama 模型
    FUSION = "fusion"     # 融合模式


class APIProvider(str, Enum):
    """API 提供商"""
    ANTHROPIC = "anthropic"  # Claude
    OPENAI = "openai"        # OpenAI
    ZHIPU = "zhipu"          # 智谱 GLM
    ALIYUN = "aliyun"        # 阿里云百炼


@dataclass
class ModelConfig:
    """模型配置"""
    model_type: ModelType
    model_name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 30
    api_provider: Optional[APIProvider] = None  # API 提供商 (仅 API 模型需要)
    priority: int = 0  # 降级优先级 (数字越小优先级越高)


# 默认模型配置
DEFAULT_API_MODEL = ModelConfig(
    model_type=ModelType.API,
    model_name="claude-sonnet-4-6",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    api_provider=APIProvider.ANTHROPIC,
    max_tokens=4096,
    temperature=0.7,
)

DEFAULT_THIRD_PARTY_MODEL = ModelConfig(
    model_type=ModelType.API,
    model_name=os.getenv("THIRD_PARTY_MODEL", "glm-4-flash"),
    api_key=os.getenv("THIRD_PARTY_API_KEY"),
    base_url=os.getenv("THIRD_PARTY_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
    api_provider=APIProvider.ZHIPU,
    max_tokens=4096,
    temperature=0.7,
)

DEFAULT_LOCAL_MODEL = ModelConfig(
    model_type=ModelType.LOCAL,
    model_name=os.getenv("LOCAL_MODEL_NAME", "qwen2.5:7b"),
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    max_tokens=2048,
    temperature=0.7,
)


# ============================================
# 异常定义
# ============================================

class ModelRouterError(Exception):
    """模型路由器基础异常"""
    pass


class SystemHaltedError(ModelRouterError):
    """系统挂起异常（生存等级为 DEAD）"""
    pass


class TokenBudgetExceededError(ModelRouterError):
    """Token 预算超限异常"""
    pass


class ModelCallError(ModelRouterError):
    """模型调用失败异常"""
    pass


class ModelUnavailableError(ModelRouterError):
    """模型不可用异常"""
    pass


# ============================================
# Token 使用统计
# ============================================

@dataclass
class TokenUsage:
    """Token 使用统计"""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def cost(self) -> float:
        """估算成本（USD）"""
        # Claude 定价（2024年）: $3/M input, $15/M output
        input_cost = self.input_tokens * 3 / 1_000_000
        output_cost = self.output_tokens * 15 / 1_000_000
        return input_cost + output_cost


# ============================================
# 双模型路由器
# ============================================

class ModelRouter:
    """
    双模型路由器

    根据生存等级路由到不同模型：
    - normal: 融合双模型（API + 本地）
    - low_compute: 仅本地模型（保守模式）
    - critical: 仅本地模型（极度保守）
    - dead: 抛出异常，停止交易
    """

    # Token 预算
    TOKEN_BUDGET = DEFAULT_TOKEN_BUDGET

    # 置信度阈值
    CONFIDENCE_THRESHOLD = 0.6

    # 模型配置
    API_MODEL = DEFAULT_API_MODEL
    THIRD_PARTY_MODEL = DEFAULT_THIRD_PARTY_MODEL
    LOCAL_MODEL = DEFAULT_LOCAL_MODEL

    def __init__(
        self,
        api_config: Optional[ModelConfig] = None,
        third_party_config: Optional[ModelConfig] = None,
        local_config: Optional[ModelConfig] = None,
        token_budget: Optional[TokenBudget] = None,
        enable_local: bool = False,  # 默认不启用本地模型
    ):
        """
        初始化模型路由器

        Args:
            api_config: Claude API 模型配置
            third_party_config: 第三方 API 模型配置 (GLM/OpenAI)
            local_config: 本地模型配置
            token_budget: Token 预算
            enable_local: 是否启用本地模型
        """
        # 只有明确传入配置才使用，否则从环境变量读取
        self.api_config = api_config
        self.third_party_config = third_party_config
        self.local_config = local_config
        self.token_budget = token_budget or self.TOKEN_BUDGET
        self.enable_local = enable_local

        # Token 使用统计
        self._daily_tokens: int = 0
        self._daily_cost: float = 0.0
        self._daily_limit: int = 1_000_000  # 每日 100 万 Token 限制

        # API 提供商配置列表 (按优先级排序)
        self._api_providers: List[ModelConfig] = []
        self._api_clients: List[Dict[str, Any]] = []  # 存储客户端和配置

        # 初始化客户端
        self._api_client: Optional[AsyncAnthropic] = None
        self._third_party_client: Optional[AsyncOpenAI] = None
        self._local_client: Optional[AsyncOpenAI] = None

        # 模型可用性
        self._api_available: bool = False
        self._third_party_available: bool = False
        self._local_available: bool = False

        # 数据详细程度配置
        # True = 完整数据（本地模型）, False = 摘要数据（API模型）
        self.use_full_data: bool = False

    async def initialize(self) -> None:
        """初始化模型客户端并检查可用性"""
        # 如果没有传入任何配置，从环境变量自动配置
        if not self.api_config and not self.third_party_config and not self.local_config:
            await self._initialize_from_env()
        else:
            # 否则从传入的配置初始化（兼容旧代码）
            await self._initialize_from_configs()

    async def _initialize_from_env(self) -> None:
        """从环境变量自动配置（目前只支持阿里云百炼）"""
        self._api_providers = []
        self._api_clients = []

        # 阿里云百炼 (唯一配置的 API)
        aliyun_auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
        aliyun_base_url = os.getenv("ANTHROPIC_BASE_URL", "https://coding.dashscope.aliyuncs.com/apps/anthropic")
        aliyun_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20240529")

        if aliyun_auth_token and aliyun_auth_token != "sk-ant-xxx":
            try:
                client = AsyncAnthropic(api_key=aliyun_auth_token, base_url=aliyun_base_url)
                config = ModelConfig(
                    model_type=ModelType.API,
                    model_name=aliyun_model,
                    api_key=aliyun_auth_token,
                    base_url=aliyun_base_url,
                    api_provider=APIProvider.ALIYUN,
                    priority=0
                )
                self._api_providers.append(config)
                self._api_clients.append({"client": client, "config": config, "available": True})
                self._api_available = True
                self._api_client = client  # 设置兼容旧代码的客户端
                print(f"[ModelRouter] 阿里云百炼 已配置: {aliyun_model}")
            except Exception as e:
                print(f"[ModelRouter] 阿里云百炼初始化失败: {e}")
                raise ModelUnavailableError(f"无法初始化阿里云百炼: {e}")
        else:
            raise ModelUnavailableError(
                "未配置阿里云百炼 API。请设置 ANTHROPIC_AUTH_TOKEN 和 ANTHROPIC_BASE_URL 环境变量。"
            )

        # 验证至少有一个模型可用
        available_count = sum(1 for item in self._api_clients if item["available"])
        if available_count == 0:
            raise ModelUnavailableError(
                "没有可用的模型。请配置 ANTHROPIC_AUTH_TOKEN。"
            )

        print(f"[ModelRouter] 初始化完成，可用模型数: {available_count}")
        for item in self._api_clients:
            if item["available"]:
                provider = item["config"].api_provider or "Local"
                model = item["config"].model_name
                print(f"  - {provider.value if hasattr(provider, 'value') else provider}: {model}")

    async def _test_local_connection(self, client: Any, base_url: str) -> None:
        """测试本地模型连接"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as http_client:
                response = await http_client.get(f"{base_url}/api/tags")
                response.raise_for_status()
        except Exception as e:
            raise ModelUnavailableError(f"无法连接到 Ollama: {e}")

    async def _initialize_from_configs(self) -> None:
        """从传入的配置初始化（兼容旧代码）"""
        # 初始化 Claude API 客户端
        if self.api_config and self.api_config.api_key and self.api_config.api_provider == APIProvider.ANTHROPIC:
            self._api_client = AsyncAnthropic(api_key=self.api_config.api_key)
            self._api_available = True
        else:
            self._api_available = False

        # 初始化第三方 API 客户端 (GLM/OpenAI)
        if self.third_party_config and self.third_party_config.api_key:
            provider = self.third_party_config.api_provider or APIProvider.ZHIPU
            if provider in [APIProvider.OPENAI, APIProvider.ZHIPU]:
                self._third_party_client = AsyncOpenAI(
                    base_url=self.third_party_config.base_url,
                    api_key=self.third_party_config.api_key,
                )
                self._third_party_available = True
            else:
                self._third_party_available = False
        else:
            self._third_party_available = False

        # 初始化本地客户端（可选，失败不抛出异常）
        if self.enable_local and self.local_config.base_url:
            try:
                self._local_client = AsyncOpenAI(
                    base_url=self.local_config.base_url,
                    api_key="ollama",  # Ollama 不需要真实 key
                )
                # 测试连接
                await self._test_local_connection(self._local_client, self.local_config.base_url)
                self._local_available = True
            except Exception as e:
                self._local_available = False
                # 本地模型不可用不抛出异常，继续使用 API 模型
                print(f"[警告] 本地模型不可用: {e}")
        else:
            self._local_available = False

        # 验证至少有一个模型可用
        if not self._api_available and not self._third_party_available and not self._local_available:
            raise ModelUnavailableError(
                "没有可用的模型。请配置 ANTHROPIC_API_KEY、THIRD_PARTY_API_KEY 或启动 Ollama。"
            )

    async def generate_decision(
        self,
        context: AgentContext,
        memories: Optional[Dict[str, Any]] = None,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """
        根据生存等级生成决策

        Args:
            context: Agent 上下文
            memories: 记忆数据（情节记忆、语义记忆）
            market_data: 市场数据

        Returns:
            Decision: 决策对象

        Raises:
            SystemHaltedError: 生存等级为 DEAD 时抛出
            TokenBudgetExceededError: Token 预算超限时抛出
        """
        # 检查生存等级
        if context.survival_level == SurvivalLevel.DEAD:
            raise SystemHaltedError(
                f"系统已挂起。回撤率: {context.drawdown:.1%} > 30%"
            )

        # 检查 Token 预算
        if self._daily_tokens >= self._daily_limit:
            raise TokenBudgetExceededError(
                f"每日 Token 预算已耗尽: {self._daily_tokens} / {self._daily_limit}"
            )

        # 使用新的自动降级决策方法
        return await self._call_with_fallback(context, memories, market_data)

    async def _call_with_fallback(
        self,
        context: AgentContext,
        memories: Optional[Dict[str, Any]] = None,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """
        调用模型，支持自动降级

        按优先级尝试所有配置的 API 提供商：
        1. 阿里云百炼 (priority 0)
        2. 智谱 GLM (priority 1)
        3. Claude API (priority 2)
        4. 本地 Ollama (priority 3)
        """
        last_error = None

        # 按优先级尝试所有可用的 API
        for item in self._api_clients:
            if not item["available"]:
                continue

            client = item["client"]
            config = item["config"]
            provider = config.api_provider or "Local"

            try:
                print(f"[ModelRouter] 尝试使用: {provider.value if hasattr(provider, 'value') else provider} ({config.model_name})")

                decision = await self._call_client(client, config, context, memories, market_data)
                print(f"[ModelRouter] 成功使用: {provider.value if hasattr(provider, 'value') else provider}")
                return decision

            except Exception as e:
                last_error = e
                error_msg = str(e)
                print(f"[ModelRouter] {provider.value if hasattr(provider, 'value') else provider} 失败: {error_msg[:100]}")

                # 标记为不可用（临时）
                item["available"] = False

                # 继续尝试下一个
                continue

        # 所有模型都失败，抛出异常
        raise ModelCallError(
            f"所有模型均不可用。最后错误: {str(last_error)[:200] if last_error else 'Unknown'}"
        )

    async def _call_client(
        self,
        client: Any,
        config: ModelConfig,
        context: AgentContext,
        memories: Optional[Dict[str, Any]] = None,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """
        调用单个客户端

        根据客户端类型选择调用方式
        """
        # 根据模型类型设置数据详细程度
        if config.model_type == ModelType.LOCAL:
            # 本地模型：使用完整数据（无额外成本）
            self.use_full_data = True
        else:
            # API 模型：使用摘要数据（节省 Token）
            self.use_full_data = False

        # 构建提示词
        prompt = self._build_prompt(context, memories, market_data)

        # 根据客户端类型调用
        if isinstance(client, AsyncAnthropic):
            # Anthropic 兼容接口 (阿里云百炼 / Claude)
            return await self._call_anthropic_client(client, config, prompt, context)
        elif isinstance(client, AsyncOpenAI):
            if config.model_type == ModelType.LOCAL:
                # 本地模型使用 Ollama 原生接口
                return await self._call_ollama_client(client, config, prompt)
            else:
                # 第三方 API (智谱 GLM 等)
                return await self._call_openai_client(client, config, prompt)
        else:
            raise ModelCallError(f"不支持的客户端类型: {type(client)}")

    async def _call_anthropic_client(
        self,
        client: AsyncAnthropic,
        config: ModelConfig,
        prompt: str,
        context: AgentContext,
    ) -> Decision:
        """调用 Anthropic 兼容接口"""
        response = await client.messages.create(
            model=config.model_name,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            messages=[{"role": "user", "content": prompt}],
        )

        # 兼容 ThinkingBlock 和 TextBlock
        content = ""
        for block in response.content:
            if hasattr(block, 'text'):
                content += block.text
            elif hasattr(block, 'thinking'):
                content += block.thinking or ""
            elif hasattr(block, 'content'):
                content += str(block.content or "")

        return self._parse_decision(content, model_name=config.model_name)

    async def _call_openai_client(
        self,
        client: AsyncOpenAI,
        config: ModelConfig,
        prompt: str,
    ) -> Decision:
        """调用 OpenAI 兼容接口 (智谱 GLM 等)"""
        response = await client.chat.completions.create(
            model=config.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )

        content = response.choices[0].message.content or ""
        return self._parse_decision(content, model_name=config.model_name)

    async def _call_ollama_client(
        self,
        client: AsyncOpenAI,
        config: ModelConfig,
        prompt: str,
    ) -> Decision:
        """调用本地 Ollama 模型"""
        response = await client.chat.completions.create(
            model=config.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )

        content = response.choices[0].message.content or ""
        return self._parse_decision(content, model_name=config.model_name)

    async def _fusion_decision(
        self,
        context: AgentContext,
        memories: Optional[Dict[str, Any]] = None,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """
        融合决策模式（API + 本地）

        流程：
        1. API 模型分析市场并生成初步决策
        2. 本地模型验证决策合理性
        3. 融合两个模型的输出
        """
        api_decision: Optional[Decision] = None
        local_decision: Optional[Decision] = None

        # 并行调用两个模型
        tasks = []
        # 优先使用第三方 API (GLM)，如果不可用则使用 Claude
        if self._third_party_available:
            tasks.append(self._call_third_party_model(context, memories, market_data))
        elif self._api_available:
            tasks.append(self._call_api_model(context, memories, market_data))
        if self._local_available:
            tasks.append(self._call_local_model(context, memories, market_data))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    continue
                # 第一个结果来自 API（第三方或 Claude）
                if i == 0:
                    api_decision = result
                # 第二个结果来自本地模型
                elif self._local_available:
                    local_decision = result

        # 融合决策
        return self._merge_decisions(
            api_decision,
            local_decision,
            context,
        )

    async def _local_decision(
        self,
        context: AgentContext,
        conservative: bool = False,
        memories: Optional[Dict[str, Any]] = None,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """
        本地模型决策（降级模式）

        Args:
            context: Agent 上下文
            conservative: 是否启用保守模式
            memories: 记忆数据
            market_data: 市场数据

        Returns:
            Decision: 决策对象
        """
        if not self._local_available:
            raise ModelUnavailableError("本地模型不可用")

        decision = await self._call_local_model(
            context,
            memories,
            market_data,
            conservative=conservative,
        )

        # 保守模式降低置信度
        if conservative and decision.confidence > 0.5:
            decision.confidence = min(decision.confidence * 0.8, 0.5)

        return decision

    async def _call_api_model(
        self,
        context: AgentContext,
        memories: Optional[Dict[str, Any]] = None,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """
        调用 Claude API 模型

        Args:
            context: Agent 上下文
            memories: 记忆数据
            market_data: 市场数据

        Returns:
            Decision: 决策对象
        """
        if not self._api_client or not self._api_available:
            raise ModelUnavailableError("Claude API 模型不可用")

        # 构建提示词
        prompt = self._build_prompt(context, memories, market_data)

        try:
            response = await self._api_client.messages.create(
                model=self.api_config.model_name,
                max_tokens=self.api_config.max_tokens,
                temperature=self.api_config.temperature,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            # 解析响应
            return self._parse_decision(
                response.content[0].text,
                model_name="claude-api",
            )

        except Exception as e:
            raise ModelCallError(f"Claude API 模型调用失败: {e}")

    async def _call_third_party_model(
        self,
        context: AgentContext,
        memories: Optional[Dict[str, Any]] = None,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """
        调用第三方 API 模型 (GLM/OpenAI)

        Args:
            context: Agent 上下文
            memories: 记忆数据
            market_data: 市场数据

        Returns:
            Decision: 决策对象
        """
        if not self._third_party_client or not self._third_party_available:
            raise ModelUnavailableError("第三方 API 模型不可用")

        # 构建提示词
        prompt = self._build_prompt(context, memories, market_data)

        try:
            response = await self._third_party_client.chat.completions.create(
                model=self.third_party_config.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.third_party_config.max_tokens,
                temperature=self.third_party_config.temperature,
            )

            # 解析响应
            return self._parse_decision(
                response.choices[0].message.content,
                model_name=f"{self.third_party_config.api_provider.value}-api",
            )

        except Exception as e:
            raise ModelCallError(f"第三方 API 模型调用失败: {e}")

    async def _call_local_model(
        self,
        context: AgentContext,
        memories: Optional[Dict[str, Any]] = None,
        market_data: Optional[Dict[str, Any]] = None,
        conservative: bool = False,
    ) -> Decision:
        """
        调用本地 Ollama 模型

        Args:
            context: Agent 上下文
            memories: 记忆数据
            market_data: 市场数据
            conservative: 是否保守模式

        Returns:
            Decision: 决策对象
        """
        if not self._local_available:
            raise ModelUnavailableError("本地模型不可用")

        # 构建提示词
        prompt = self._build_prompt(
            context,
            memories,
            market_data,
            conservative=conservative,
        )

        try:
            # 直接使用 Ollama 的 /api/chat 端点
            async with httpx.AsyncClient(timeout=self.local_config.timeout) as client:
                response = await client.post(
                    f"{self.local_config.base_url}/api/chat",
                    json={
                        "model": self.local_config.model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "options": {
                            "num_predict": self.local_config.max_tokens,
                            "temperature": self.local_config.temperature,
                        }
                    }
                )
                response.raise_for_status()
                result = response.json()

            # 解析响应
            message = result.get("message", {})
            content = message.get("content", "")

            return self._parse_decision(
                content,
                model_name="qwen-local",
            )

        except Exception as e:
            raise ModelCallError(f"本地模型调用失败: {e}")

    def _build_prompt(
        self,
        context: AgentContext,
        memories: Optional[Dict[str, Any]] = None,
        market_data: Optional[Dict[str, Any]] = None,
        conservative: bool = False,
    ) -> str:
        """
        构建模型提示词

        Args:
            context: Agent 上下文
            memories: 记忆数据
            market_data: 市场数据
            conservative: 是否保守模式

        Returns:
            str: 提示词
        """
        mode_text = "（保守模式）" if conservative else ""

        prompt = f"""你是一个专业的股票交易智能体{mode_text}。

## 当前账户状态
- 现金: {context.current_cash:,.2f} 元
- 总资产: {context.total_value:,.2f} 元
- 回撤率: {context.drawdown:.2%}
- 生存等级: {context.survival_level.value}
- 市场状态: {context.market_regime.value}
- 最大仓位: {context.max_position_ratio:.0%}

## 当前持仓
"""

        if context.positions:
            for pos in context.positions:
                prompt += f"""
- {pos.symbol}: {pos.shares} 股, 成本 {pos.avg_cost:.2f}, 当前 {pos.current_price:.2f}, 盈亏 {pos.pnl_ratio:+.2%}
"""
        else:
            prompt += "\n（空仓）\n"

        prompt += f"""
## 用户指令
{context.user_input}

## 决策要求
1. 分析当前市场状态和持仓情况
2. 给出明确的交易决策（买入/卖出/持有/等待）
3. 如果选择买入或卖出，指定股票代码、数量和价格
4. 给出置信度（0-1之间的数值）
5. 简要说明你的推理过程

## 决策格式
请严格按照以下格式回复：

```json
{{
    "action": "buy|sell|hold|wait",
    "symbol": "股票代码（如 600519）",
    "quantity": 数量（100的整数倍），
    "price": 价格（浮点数），
    "confidence": 置信度（0-1），
    "reasoning": "推理过程",
    "is_final": true
}}
```

注意：
- action=hold 表示维持现有仓位
- action=wait 表示等待更好时机
- symbol 仅在 buy/sell 时需要
- quantity 和 price 仅在 buy/sell 时需要
"""

        # 添加记忆信息
        if memories:
            prompt += "\n## 历史记忆\n"
            if "episodic" in memories and memories["episodic"]:
                prompt += f"\n相关交易记忆: {memories['episodic']}\n"
            if "semantic" in memories and memories["semantic"]:
                prompt += f"\n知识规则: {memories['semantic']}\n"
            if "reflections" in memories and memories["reflections"]:
                prompt += f"\n反思经验: {memories['reflections']}\n"

        # 添加市场数据
        if market_data:
            from tools.data.local_data_loader import format_market_data_for_ai

            prompt += "\n## 市场数据\n"

            # 检查是否已经是格式化的数据
            if isinstance(market_data, str):
                prompt += f"\n{market_data}\n"
            elif isinstance(market_data, dict):
                # 使用新的格式化函数，传递 use_full_data 标志
                formatted_data = format_market_data_for_ai(market_data, full_data=self.use_full_data)
                prompt += f"\n{formatted_data}\n"
            else:
                # 旧格式兼容
                prompt += f"\n{market_data}\n"

        # 保守模式提示
        if conservative:
            prompt += """
## 保守模式提示
当前处于资金亏损状态，请采取保守策略：
- 优先考虑降低风险
- 减少交易频率
- 降低单笔交易金额
- 提高决策置信度要求
"""

        return prompt

    def _parse_decision(self, response_text: str, model_name: str) -> Decision:
        """
        解析模型响应为 Decision 对象

        Args:
            response_text: 模型响应文本
            model_name: 模型名称

        Returns:
            Decision: 决策对象
        """
        import json
        import re

        # 尝试提取 JSON
        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接解析
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                # 无法解析，返回默认决策
                return Decision(
                    action="wait",
                    confidence=0.0,
                    reasoning=f"无法解析模型响应: {response_text[:100]}...",
                    is_final=True,
                )

        try:
            data = json.loads(json_str)

            # 验证并创建 Decision
            action = data.get("action", "wait")
            if action not in ["buy", "sell", "hold", "wait"]:
                action = "wait"

            return Decision(
                action=action,
                symbol=data.get("symbol"),
                quantity=data.get("quantity"),
                price=data.get("price"),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", "无推理说明"),
                is_final=data.get("is_final", True),
            )

        except (json.JSONDecodeError, ValueError) as e:
            return Decision(
                action="wait",
                confidence=0.0,
                reasoning=f"解析失败: {str(e)}. 原始响应: {response_text[:100]}...",
                is_final=True,
            )

    def _merge_decisions(
        self,
        api_decision: Optional[Decision],
        local_decision: Optional[Decision],
        context: AgentContext,
    ) -> Decision:
        """
        融合 API 和本地模型的决策

        融合策略：
        1. 如果只有一个模型返回结果，使用该结果
        2. 如果两个模型决策一致，使用 API 的置信度
        3. 如果两个模型决策冲突：
           - 如果都是交易决策，优先选择置信度更高的
           - 如果一个是交易一个是等待，选择等待

        Args:
            api_decision: API 模型决策
            local_decision: 本地模型决策
            context: Agent 上下文

        Returns:
            Decision: 融合后的决策
        """
        # 只有一个模型有结果
        if api_decision and not local_decision:
            return api_decision
        if local_decision and not api_decision:
            return local_decision
        if not api_decision and not local_decision:
            return Decision(
                action="wait",
                confidence=0.0,
                reasoning="所有模型均无响应",
                is_final=True,
            )

        # 两个模型都有结果，进行融合
        if api_decision.action == local_decision.action:
            # 决策一致，融合推理过程
            return Decision(
                action=api_decision.action,
                symbol=api_decision.symbol,
                quantity=api_decision.quantity,
                price=api_decision.price,
                confidence=max(api_decision.confidence, local_decision.confidence),
                reasoning=f"[融合] API: {api_decision.reasoning}\n本地: {local_decision.reasoning}",
                is_final=True,
            )
        else:
            # 决策冲突，选择更保守的
            actions = {api_decision.action, local_decision.action}

            # 如果有一个是 wait，选择 wait
            if "wait" in actions:
                return Decision(
                    action="wait",
                    confidence=max(api_decision.confidence, local_decision.confidence) * 0.8,
                    reasoning=f"[冲突] API: {api_decision.action}, 本地: {local_decision.action}. 选择等待观察",
                    is_final=True,
                )

            # 如果有一个是 hold，选择 hold
            if "hold" in actions:
                return Decision(
                    action="hold",
                    confidence=max(api_decision.confidence, local_decision.confidence) * 0.8,
                    reasoning=f"[冲突] API: {api_decision.action}, 本地: {local_decision.action}. 选择持有",
                    is_final=True,
                )

            # 买卖冲突，选择置信度更高的
            chosen = api_decision if api_decision.confidence > local_decision.confidence else local_decision
            return Decision(
                action=chosen.action,
                symbol=chosen.symbol,
                quantity=chosen.quantity,
                price=chosen.price,
                confidence=chosen.confidence * 0.9,  # 降低置信度
                reasoning=f"[冲突] API: {api_decision.action}, 本地: {local_decision.action}. 选择 {chosen.action}（置信度更高）",
                is_final=True,
            )

    def get_token_usage(self) -> TokenUsage:
        """获取 Token 使用统计"""
        return TokenUsage(
            input_tokens=self._daily_tokens // 2,  # 估算
            output_tokens=self._daily_tokens // 2,
            total_tokens=self._daily_tokens,
        )

    def reset_daily_usage(self) -> None:
        """重置每日 Token 使用量"""
        self._daily_tokens = 0
        self._daily_cost = 0.0


# ============================================
# 工厂函数
# ============================================

async def create_model_router(
    api_key: Optional[str] = None,
    third_party_api_key: Optional[str] = None,
    third_party_base_url: Optional[str] = None,
    third_party_model: Optional[str] = None,
    local_url: Optional[str] = None,
    enable_local: bool = True,
) -> ModelRouter:
    """
    创建并初始化模型路由器

    Args:
        api_key: Anthropic API Key (Claude)
        third_party_api_key: 第三方 API Key (GLM/OpenAI)
        third_party_base_url: 第三方 API Base URL
        third_party_model: 第三方模型名称
        local_url: 本地模型 URL (Ollama)
        enable_local: 是否启用本地模型

    Returns:
        ModelRouter: 已初始化的路由器
    """
    api_config = None
    if api_key:
        api_config = ModelConfig(
            model_type=ModelType.API,
            model_name="claude-sonnet-4-6",
            api_key=api_key,
            api_provider=APIProvider.ANTHROPIC,
        )

    third_party_config = None
    if third_party_api_key:
        third_party_config = ModelConfig(
            model_type=ModelType.API,
            model_name=third_party_model or os.getenv("THIRD_PARTY_MODEL", "glm-4-flash"),
            api_key=third_party_api_key,
            base_url=third_party_base_url or os.getenv("THIRD_PARTY_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
            api_provider=APIProvider.ZHIPU,
        )

    local_config = None
    if local_url:
        local_config = ModelConfig(
            model_type=ModelType.LOCAL,
            model_name=os.getenv("LOCAL_MODEL_NAME", "qwen2.5:7b"),
            base_url=local_url,
        )

    router = ModelRouter(
        api_config=api_config,
        third_party_config=third_party_config,
        local_config=local_config,
        enable_local=enable_local,
    )

    await router.initialize()
    return router
