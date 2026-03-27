# -*- coding: utf-8 -*-
"""
ReAct 循环核心逻辑

协调各模块完成决策：
1. Observe: 获取当前状态（持仓、行情、记忆）
2. Think: 调用模型生成决策
3. Act: 执行工具调用
4. Reflect: 更新记忆和状态
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import uuid4

from pydantic import BaseModel

from .schemas import (
    AgentContext,
    AgentResponse,
    Decision,
    SurvivalLevel,
    Position,
    ToolResult,
    ToolCall,
    DecisionChain,
)
from .model_router import ModelRouter
from .survival_rules import SurvivalRules
from .market_regime import MarketRegimeDetector


# ============================================
# 日志配置
# ============================================

logger = logging.getLogger(__name__)


# ============================================
# 循环状态
# ============================================

@dataclass
class LoopState:
    """循环状态"""
    iteration: int = 0
    max_iterations: int = 5
    context: Optional[AgentContext] = None
    decision_chain: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)

    @property
    def should_continue(self) -> bool:
        """是否应该继续循环"""
        return self.iteration < self.max_iterations

    @property
    def elapsed_seconds(self) -> float:
        """已用时间（秒）"""
        return (datetime.now() - self.start_time).total_seconds()


# ============================================
# ReAct 循环异常
# ============================================

class AgentLoopError(Exception):
    """Agent 循环基础异常"""
    pass


class MaxIterationsExceededError(AgentLoopError):
    """超过最大迭代次数"""
    pass


class ContextBuildError(AgentLoopError):
    """上下文构建错误"""
    pass


# ============================================
# ReAct 循环核心
# ============================================

class AgentLoop:
    """
    ReAct 循环核心

    实现推理-行动-观察-反思的决策循环。
    """

    # 默认配置
    DEFAULT_MAX_ITERATIONS = 5
    DEFAULT_TIMEOUT = 30  # 秒

    def __init__(
        self,
        model_router: ModelRouter,
        survival_rules: SurvivalRules,
        market_detector: MarketRegimeDetector,
        tool_executor: Optional[Any] = None,  # ToolExecutor (T9)
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        enable_logging: bool = True,
    ):
        """
        初始化 Agent 循环

        Args:
            model_router: 模型路由器
            survival_rules: 生存规则
            market_detector: 市场状态检测器
            tool_executor: 工具执行器（可选，T9 实现后传入）
            max_iterations: 最大迭代次数
            enable_logging: 是否启用日志
        """
        self.model_router = model_router
        self.survival_rules = survival_rules
        self.market_detector = market_detector
        self.tool_executor = tool_executor
        self.max_iterations = max_iterations
        self.enable_logging = enable_logging

        # 内存存储（Phase 2 实现持久化）
        self._working_memory: Dict[str, Any] = {}
        self._episodic_memory: List[Dict[str, Any]] = []
        self._semantic_memory: Dict[str, Any] = {}

        # 统计信息
        self._total_decisions: int = 0
        self._total_tool_calls: int = 0
        self._successful_trades: int = 0

    async def react_loop(
        self,
        user_input: str,
        current_cash: float,
        total_value: float,
        initial_cash: float,
        positions: List[Position],
        market_data: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """
        ReAct 循环主入口

        Args:
            user_input: 用户输入
            current_cash: 当前现金
            total_value: 总资产
            initial_cash: 初始资金
            positions: 当前持仓
            market_data: 市场数据（可选）

        Returns:
            AgentResponse: Agent 响应
        """
        start_time = datetime.now()
        state = LoopState(max_iterations=self.max_iterations)
        actions_taken: List[str] = []

        try:
            # 1. Observe: 构建初始上下文
            state.context = await self._build_context(
                user_input,
                current_cash,
                total_value,
                initial_cash,
                positions,
                market_data,
            )

            if self.enable_logging:
                logger.info(
                    f"[ReAct] 开始循环: 生存等级={state.context.survival_level.value}, "
                    f"市场状态={state.context.market_regime.value}"
                )

            # 2. Think + Act + Reflect 循环
            while state.should_continue:
                state.iteration += 1

                # Think: 调用模型生成决策
                decision = await self._think(state)

                # 记录决策
                state.decision_chain.append({
                    "iteration": state.iteration,
                    "decision": decision.model_dump(),
                    "timestamp": datetime.now().isoformat(),
                })

                # 检查是否为最终决策
                if decision.is_final:
                    if self.enable_logging:
                        logger.info(f"[ReAct] 迭代 {state.iteration}: 收到最终决策")
                    break

                # Act: 执行工具调用
                if decision.tools_to_use:
                    tool_results = await self._act(decision, state.context)
                    state.tool_results.extend(tool_results)
                    actions_taken.extend([f"调用工具: {tool}" for tool in decision.tools_to_use])

                    # Reflect: 更新上下文
                    state.context = self._reflect(state, tool_results)
                else:
                    # 无工具调用，视为最终决策
                    break

            # 3. 构建响应
            execution_time = (datetime.now() - start_time).total_seconds()

            response = AgentResponse(
                success=True,
                message=self._build_message(state),
                thought_process=self._build_thought_process(state),
                actions_taken=actions_taken,
                final_result={
                    "decision": state.decision_chain[-1]["decision"] if state.decision_chain else None,
                    "survival_level": state.context.survival_level.value,
                    "market_regime": state.context.market_regime.value,
                    "iterations": state.iteration,
                },
                execution_time=execution_time,
            )

            # 更新统计
            self._total_decisions += 1
            self._total_tool_calls += len(actions_taken)

            if self.enable_logging:
                logger.info(
                    f"[ReAct] 循环完成: 迭代={state.iteration}, "
                    f"耗时={execution_time:.2f}s, 操作={len(actions_taken)}"
                )

            return response

        except Exception as e:
            logger.error(f"[ReAct] 循环异常: {e}", exc_info=True)
            execution_time = (datetime.now() - start_time).total_seconds()

            return AgentResponse(
                success=False,
                message=f"循环执行失败: {str(e)}",
                thought_process=self._build_thought_process(state) if state.decision_chain else None,
                actions_taken=actions_taken,
                execution_time=execution_time,
            )

    async def _build_context(
        self,
        user_input: str,
        current_cash: float,
        total_value: float,
        initial_cash: float,
        positions: List[Position],
        market_data: Optional[Dict[str, Any]] = None,
    ) -> AgentContext:
        """
        构建初始上下文（Observe 阶段）

        包括：
        - 账户状态
        - 生存等级计算
        - 市场状态检测
        """
        # 计算回撤率
        drawdown = max(0, (initial_cash - total_value) / initial_cash)

        # 获取生存等级
        self.survival_rules.update_level(total_value)
        survival_state = self.survival_rules.get_current_state()
        survival_level = survival_state.level

        # 检测市场状态
        market_state = await self._detect_market_state(market_data)
        market_regime = market_state.regime

        # 获取最大仓位限制
        max_position = survival_state.max_position

        context = AgentContext(
            user_input=user_input,
            current_cash=current_cash,
            total_value=total_value,
            initial_cash=initial_cash,
            positions=positions,
            survival_level=survival_level,
            market_regime=market_regime,
            max_position_ratio=max_position,
            trading_enabled=survival_level != SurvivalLevel.DEAD,
        )

        return context

    async def _think(self, state: LoopState) -> Decision:
        """
        Think 阶段：调用模型生成决策

        Args:
            state: 循环状态

        Returns:
            Decision: 决策对象
        """
        if self.enable_logging:
            logger.debug(f"[ReAct] 迭代 {state.iteration}: 思考...")

        # 准备记忆数据
        memories = self._prepare_memories(state.context)

        # 调用模型路由器
        decision = await self.model_router.generate_decision(
            context=state.context,
            memories=memories,
            market_data=None,  # 市场数据已在上下文中
        )

        return decision

    async def _act(self, decision: Decision, context: AgentContext) -> List[ToolResult]:
        """
        Act 阶段：执行工具调用

        Args:
            decision: 决策对象
            context: Agent 上下文

        Returns:
            List[ToolResult]: 工具执行结果列表
        """
        if self.enable_logging:
            logger.debug(f"[ReAct] 执行工具: {decision.tools_to_use}")

        results: List[ToolResult] = []

        # 如果没有工具执行器，返回模拟结果
        if self.tool_executor is None:
            for tool_name in decision.tools_to_use:
                results.append(ToolResult(
                    success=True,
                    data=f"模拟 {tool_name} 执行结果",
                    error=None,
                    execution_time=0.1,
                ))
            return results

        # 执行工具调用
        for tool_name in decision.tools_to_use:
            try:
                # 构建工具参数
                params = self._build_tool_params(decision, context)

                # 执行工具
                result = await self.tool_executor.execute(tool_name, **params)
                results.append(result)

            except Exception as e:
                logger.error(f"[ReAct] 工具 {tool_name} 执行失败: {e}")
                results.append(ToolResult(
                    success=False,
                    error=str(e),
                    execution_time=0.0,
                ))

        return results

    def _reflect(
        self,
        state: LoopState,
        tool_results: List[ToolResult],
    ) -> AgentContext:
        """
        Reflect 阶段：更新上下文和记忆

        Args:
            state: 循环状态
            tool_results: 工具执行结果

        Returns:
            AgentContext: 更新后的上下文
        """
        # 更新工作记忆
        self._working_memory["last_tool_results"] = [
            {
                "success": r.success,
                "data": str(r.data)[:100] if r.data else None,
                "error": r.error,
            }
            for r in tool_results
        ]

        # 记录到情节记忆
        if tool_results:
            self._episodic_memory.append({
                "timestamp": datetime.now().isoformat(),
                "iteration": state.iteration,
                "tool_results": self._working_memory["last_tool_results"],
            })

        # 返回更新后的上下文（目前不变，后续可以根据工具结果更新）
        return state.context

    def _build_tool_params(self, decision: Decision, context: AgentContext) -> Dict[str, Any]:
        """
        构建工具调用参数

        Args:
            decision: 决策对象
            context: Agent 上下文

        Returns:
            Dict[str, Any]: 工具参数
        """
        params = {}

        if decision.action == "buy" or decision.action == "sell":
            if decision.symbol:
                params["symbol"] = decision.symbol
            if decision.quantity:
                params["quantity"] = decision.quantity
            if decision.price:
                params["price"] = decision.price

        return params

    async def _detect_market_state(self, market_data: Optional[Dict[str, Any]]) -> Any:
        """
        检测市场状态

        Args:
            market_data: 市场数据

        Returns:
            MarketState: 市场状态
        """
        # 如果没有市场数据，返回默认状态
        if market_data is None:
            from .schemas import MarketState
            return MarketState(
                regime="sideways",
                confidence=0.5,
                max_position_ratio=0.3,
            )

        # 调用市场状态检测器
        try:
            return await self.market_detector.detect(market_data)
        except Exception as e:
            logger.warning(f"[ReAct] 市场状态检测失败: {e}，使用默认状态")
            from .schemas import MarketState
            return MarketState(
                regime="sideways",
                confidence=0.5,
                max_position_ratio=0.3,
            )

    def _prepare_memories(self, context: AgentContext) -> Dict[str, Any]:
        """
        准备记忆数据供模型使用

        Args:
            context: Agent 上下文

        Returns:
            Dict[str, Any]: 记忆数据
        """
        # 获取相关情节记忆（最近 5 条）
        recent_episodic = self._episodic_memory[-5:] if self._episodic_memory else []

        # 获取语义记忆
        semantic = self._semantic_memory.copy()

        return {
            "episodic": recent_episodic,
            "semantic": semantic,
            "working": self._working_memory,
        }

    def _build_message(self, state: LoopState) -> str:
        """构建响应消息"""
        if not state.decision_chain:
            return "未生成任何决策"

        last_decision = state.decision_chain[-1]["decision"]
        action = last_decision.get("action", "unknown")

        messages = {
            "buy": f"建议买入 {last_decision.get('symbol')} {last_decision.get('quantity')} 股",
            "sell": f"建议卖出 {last_decision.get('symbol')} {last_decision.get('quantity')} 股",
            "hold": "建议维持现有持仓",
            "wait": "建议等待更好时机",
        }

        base_msg = messages.get(action, f"决策: {action}")

        if last_decision.get("reasoning"):
            return f"{base_msg}\n\n推理: {last_decision['reasoning']}"

        return base_msg

    def _build_thought_process(self, state: LoopState) -> str:
        """构建思考过程"""
        if not state.decision_chain:
            return ""

        lines = []
        for entry in state.decision_chain:
            iteration = entry["iteration"]
            decision = entry["decision"]
            timestamp = entry["timestamp"]

            lines.append(f"[迭代 {iteration}] {timestamp}")
            lines.append(f"  动作: {decision.get('action')}")
            lines.append(f"  置信度: {decision.get('confidence', 0):.2f}")
            if decision.get("reasoning"):
                reasoning = decision["reasoning"]
                lines.append(f"  推理: {reasoning[:100]}...")
            lines.append("")

        return "\n".join(lines)

    # ============================================
    # 公共接口
    # ============================================

    def get_working_memory(self) -> Dict[str, Any]:
        """获取工作记忆"""
        return self._working_memory.copy()

    def get_episodic_memory(self) -> List[Dict[str, Any]]:
        """获取情节记忆"""
        return self._episodic_memory.copy()

    def add_semantic_memory(self, key: str, value: Any) -> None:
        """添加语义记忆"""
        self._semantic_memory[key] = value

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_decisions": self._total_decisions,
            "total_tool_calls": self._total_tool_calls,
            "successful_trades": self._successful_trades,
            "episodic_memory_count": len(self._episodic_memory),
            "semantic_memory_count": len(self._semantic_memory),
        }

    def reset_memory(self) -> None:
        """重置记忆"""
        self._working_memory.clear()
        self._episodic_memory.clear()
        self._semantic_memory.clear()


# ============================================
# 工厂函数
# ============================================

async def create_agent_loop(
    model_router: ModelRouter,
    survival_rules: SurvivalRules,
    market_detector: MarketRegimeDetector,
    tool_executor: Optional[Any] = None,
    max_iterations: int = 5,
) -> AgentLoop:
    """
    创建并初始化 Agent 循环

    Args:
        model_router: 模型路由器
        survival_rules: 生存规则
        market_detector: 市场状态检测器
        tool_executor: 工具执行器（可选）
        max_iterations: 最大迭代次数

    Returns:
        AgentLoop: 已初始化的循环实例
    """
    loop = AgentLoop(
        model_router=model_router,
        survival_rules=survival_rules,
        market_detector=market_detector,
        tool_executor=tool_executor,
        max_iterations=max_iterations,
    )

    return loop
