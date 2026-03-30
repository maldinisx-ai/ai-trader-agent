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
from src.indicators import QuoteDataAnalyzer
from core.comprehensive_scoring import ComprehensiveScoringSystem
from .model_router import ModelRouter
from .survival_rules import SurvivalRules
from .market_regime import MarketRegimeDetector
from .reflection import ReflectionEngine, DecisionChain as ReflectionDecisionChain


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
    market_data: Optional[Dict[str, Any]] = None  # 市场数据

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
        policy_engine: Optional[Any] = None,  # PolicyEngine (用于评分拦截)
        reflection_engine: Optional[ReflectionEngine] = None,  # 反思引擎 (新增)
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
            policy_engine: 风控引擎（可选，用于评分拦截）
            reflection_engine: 反思引擎（可选，用于交易反思）
            max_iterations: 最大迭代次数
            enable_logging: 是否启用日志
        """
        self.model_router = model_router
        self.survival_rules = survival_rules
        self.market_detector = market_detector
        self.tool_executor = tool_executor
        self.policy_engine = policy_engine
        self.reflection_engine = reflection_engine
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
        state.market_data = market_data  # 存储市场数据
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
        - 股票评分计算 (新增)
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

        # 计算股票评分 (新增)
        if market_data and "stocks" in market_data:
            market_data = await self._calculate_scores(market_data)

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

    async def _calculate_scores(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算股票评分

        Args:
            market_data: 市场数据

        Returns:
            添加了评分信息的市场数据
        """
        scoring_system = ComprehensiveScoringSystem()
        scores_dict = {}  # 用于更新 PolicyEngine

        for stock in market_data.get("stocks", []):
            # 跳过已有评分的股票
            if "score" in stock:
                continue

            try:
                # 获取K线数据
                klines_df = stock.get("klines_df")
                if klines_df is None or klines_df.empty:
                    stock["score"] = {
                        "total_score": 50,
                        "buy_signal": "HOLD",
                        "error": "无K线数据"
                    }
                    continue

                # 将 DataFrame 转换为 QuoteData 列表
                from core.schemas import QuoteData
                import pandas as pd
                quotes = []
                for _, row in klines_df.iterrows():
                    # 处理 NaN 值
                    change_val = row.get("change", pd.NA)
                    if pd.isna(change_val):
                        change_val = 0.0
                    else:
                        change_val = float(change_val)
                        # 限制涨跌幅范围
                        change_val = max(-11, min(11, change_val))

                    quote = QuoteData(
                        symbol=stock["symbol"],
                        name=stock.get("industry") or "未知",
                        price=float(row["close"]),
                        change=change_val,
                        volume=int(row["volume"]),
                        amount=float(row.get("amount", 0) or 0),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        upper_limit=float(row["close"]) * 1.1,
                        lower_limit=float(row["close"]) * 0.9,
                    )
                    quotes.append(quote)

                # 创建分析器
                analyzer = QuoteDataAnalyzer(quotes)

                # 获取当前价格
                current_price = stock.get("latest", {}).get("close", 0)

                # 计算评分
                score_result = scoring_system.score(
                    symbol=stock["symbol"],
                    analyzer=analyzer,
                    current_price=current_price
                )

                # 附加评分信息
                stock["score"] = {
                    "total_score": score_result.total_score,
                    "buy_signal": score_result.buy_signal.value,
                    "technical_score": score_result.technical_score,
                    "fundamental_score": score_result.fundamental_score,
                    "money_flow_score": score_result.money_flow_score,
                    "reasons": score_result.reasons[:3],  # 最多3个理由
                    "risk_factors": score_result.risk_factors[:2],  # 最多2个风险
                }

                # 收集评分用于 PolicyEngine
                scores_dict[stock["symbol"]] = score_result.total_score

            except Exception as e:
                logger.warning(f"评分计算失败 {stock.get('symbol', 'unknown')}: {e}")
                stock["score"] = {
                    "total_score": 50,
                    "buy_signal": "HOLD",
                    "error": str(e)
                }

        # 更新 PolicyEngine 的评分（新增）
        if self.policy_engine and scores_dict:
            self.policy_engine.update_stock_scores(scores_dict)

        return market_data

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

        # 调用模型路由器，传递市场数据
        decision = await self.model_router.generate_decision(
            context=state.context,
            memories=memories,
            market_data=state.market_data,  # 传递市场数据
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
        tool_calls = []  # 记录工具调用，用于反思

        # 如果没有工具执行器，返回模拟结果
        if self.tool_executor is None:
            for tool_name in decision.tools_to_use:
                tool_calls.append({
                    "name": tool_name,
                    "parameters": self._build_tool_params(decision, context),
                    "result": f"模拟 {tool_name} 执行结果",
                })
                results.append(ToolResult(
                    success=True,
                    data=f"模拟 {tool_name} 执行结果",
                    error=None,
                    execution_time=0.1,
                ))
            # 记录工具调用
            self._working_memory["last_tool_calls"] = tool_calls
            return results

        # 执行工具调用
        for tool_name in decision.tools_to_use:
            try:
                # 构建工具参数
                params = self._build_tool_params(decision, context)

                # 执行工具
                result = await self.tool_executor.execute(tool_name, **params)
                results.append(result)

                # 记录工具调用
                tool_calls.append({
                    "name": tool_name,
                    "parameters": params,
                    "success": result.success,
                    "data": str(result.data)[:200] if result.data else None,
                    "error": result.error,
                })

            except Exception as e:
                logger.error(f"[ReAct] 工具 {tool_name} 执行失败: {e}")
                results.append(ToolResult(
                    success=False,
                    error=str(e),
                    execution_time=0.0,
                ))

                # 记录失败的工具调用
                tool_calls.append({
                    "name": tool_name,
                    "parameters": params,
                    "success": False,
                    "error": str(e),
                })

        # 记录工具调用（用于反思）
        self._working_memory["last_tool_calls"] = tool_calls

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
            market_data: 市场数据（字典格式，包含 quotes 列表）

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

        # 尝试从 quotes 转换为 MarketData
        try:
            from .schemas import MarketState
            from .market_regime import MarketData

            quotes = market_data.get("quotes", [])
            if not quotes or len(quotes) == 0:
                return MarketState(
                    regime="sideways",
                    confidence=0.5,
                    max_position_ratio=0.3,
                )

            # 使用第一个股票的数据作为市场参考
            quote_dict = quotes[0]

            # 如果 quote 是字典，尝试提取必要字段
            if isinstance(quote_dict, dict):
                # 构造简化的 MarketData
                # 由于没有历史均线数据，使用当前价格作为近似值
                current_price = float(quote_dict.get("price", 100.0))

                return MarketState(
                    regime="sideways",  # 缺少历史数据，默认震荡
                    confidence=0.5,
                    max_position_ratio=0.3,
                )

            # 如果 quote 是 QuoteData 对象（虽然 market_data 是字典格式）
            # 仍然返回默认状态
            return MarketState(
                regime="sideways",
                confidence=0.5,
                max_position_ratio=0.3,
            )

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

        # 获取反思记录（新增）
        reflections = []
        if self.reflection_engine:
            reflections = [
                {
                    "symbol": r.symbol,
                    "loss_ratio": r.loss_ratio,
                    "error_type": r.error_type.value,
                    "lesson": r.lesson,
                    "avoid_action": r.avoid_action,
                }
                for r in self.reflection_engine.get_reflections(limit=5)
            ]

        return {
            "episodic": recent_episodic,
            "semantic": semantic,
            "working": self._working_memory,
            "reflections": reflections,  # 新增反思数据
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
    # 反思机制接口 (新增)
    # ============================================

    async def reflect_on_trade(
        self,
        trade: Any,  # Trade 对象
        current_price: float,
        max_price: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """
        对交易结果进行反思

        Args:
            trade: 交易记录
            current_price: 当前价格
            max_price: 持仓期间最高价
            context: 上下文信息

        Returns:
            反思记录（如果有）
        """
        if self.reflection_engine is None:
            return None

        # 计算收益率（优先从 context 获取，否则从 trade 对象）
        loss_ratio = 0.0
        if context and "loss_ratio" in context:
            loss_ratio = context["loss_ratio"]
        elif hasattr(trade, 'pnl') and trade.pnl < 0:
            loss_ratio = trade.pnl / trade.amount
        elif hasattr(trade, 'price') and current_price > 0:
            # 从当前价格计算收益率
            entry_price = trade.price
            if entry_price > 0:
                loss_ratio = (current_price - entry_price) / entry_price

        # 检查是否需要反思（亏损 > 2%）
        if loss_ratio <= ReflectionEngine.LOSS_THRESHOLD:
            # 记录决策链
            decision_chain = ReflectionDecisionChain(
                trade_id=trade.trade_id,
                thought_process=self._build_thought_process(state=None) if self._total_decisions > 0 else "",
                tool_calls=self._working_memory.get("last_tool_calls", []),
                observations=[],
                final_decision={},
            )

            # 生成反思
            reflection = await self.reflection_engine.reflect_on_loss(
                trade=trade,
                loss_ratio=loss_ratio,
                decision_chain=decision_chain,
                context={
                    **(context or {}),
                    "max_price": max_price,
                    "total_value": self._working_memory.get("total_value", 0),
                }
            )

            # 记录到语义记忆
            self._semantic_memory[f"reflection_{trade.trade_id}"] = {
                "loss_ratio": loss_ratio,
                "error_type": reflection.error_type.value,
                "lesson": reflection.lesson,
                "avoid_action": reflection.avoid_action,
            }

            if self.enable_logging:
                logger.info(
                    f"[Reflection] 交易 {trade.trade_id} 亏损 {abs(loss_ratio):.2%}，"
                    f"错误类型: {reflection.error_type.value}"
                )

            return reflection

        return None

    async def reflect_on_consecutive_losses(self, recent_trades: List[Any]) -> List[Any]:
        """
        对连续亏损进行反思

        Args:
            recent_trades: 最近交易列表

        Returns:
            反思记录列表
        """
        if self.reflection_engine is None or len(recent_trades) < ReflectionEngine.CONSECUTIVE_LOSS:
            return []

        # 检查连续亏损
        consecutive_losses = 0
        reflections = []

        for trade in reversed(recent_trades):
            if hasattr(trade, 'pnl') and trade.pnl < 0:
                consecutive_losses += 1
                if consecutive_losses >= ReflectionEngine.CONSECUTIVE_LOSS:
                    reflection = await self.reflect_on_trade(trade, 0)
                    if reflection:
                        reflections.append(reflection)
            else:
                break

        return reflections


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
