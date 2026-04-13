# -*- coding: utf-8 -*-
"""
Agent 回测引擎

使用 ReAct Agent 在历史数据上进行回测，让 LLM 真正自主决策。
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field

from core.schemas import (
    Order, OrderSide, OrderType, QuoteData,
    SurvivalLevel, MarketRegime, Decision, Position
)
from core.survival_rules import SurvivalRules
from core.policy_engine import PolicyEngine
from core.agent_loop import AgentLoop, AgentResponse
from core.model_router import ModelRouter
from core.market_regime import MarketRegimeDetector
from core.tool_executor import ToolExecutor
from simulation.account import Account
from simulation.matcher import Matcher
from src.indicators import QuoteDataAnalyzer
from src.performance import PerformanceMetrics, BacktestReport


logger = logging.getLogger(__name__)


# ============================================
# 决策追踪
# ============================================

@dataclass
class AgentDecisionRecord:
    """Agent 决策记录"""
    date: str
    symbol: str
    price: float

    # Agent 决策
    action: str
    confidence: float
    reasoning: str
    is_final: bool
    quantity: Optional[int] = None  # 交易数量

    # Agent 思考过程
    thought_process: Optional[str] = None
    iterations: int = 0

    # 执行结果
    executed: bool = False
    execution_result: Optional[str] = None

    # 模型信息
    model_used: str = "unknown"
    survival_level: str = "normal"
    market_regime: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "date": self.date,
            "symbol": self.symbol,
            "price": self.price,
            "action": self.action,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "thought_process": self.thought_process,
            "iterations": self.iterations,
            "executed": self.executed,
            "execution_result": self.execution_result,
            "model_used": self.model_used,
            "survival_level": self.survival_level,
            "market_regime": self.market_regime,
        }


# ============================================
# Agent 回测引擎
# ============================================

class AgentBacktestEngine:
    """
    Agent 回测引擎

    与传统回测引擎不同，本引擎在每个决策点调用 ReAct Agent，
    让 LLM 自主分析市场并做出交易决策。
    """

    def __init__(
        self,
        initial_cash: float,
        symbols: List[str],
        model_router: ModelRouter,
        decision_interval: int = 5,  # 每隔 N 天决策一次
        max_position_ratio: float = 0.30,
    ):
        """
        初始化 Agent 回测引擎

        Args:
            initial_cash: 初始资金
            symbols: 股票代码列表
            model_router: 模型路由器
            decision_interval: 决策间隔（天），避免每个 K 线都调用 LLM
            max_position_ratio: 最大仓位比例
        """
        self.initial_cash = initial_cash
        self.symbols = symbols
        self.decision_interval = decision_interval
        self.max_position_ratio = max_position_ratio

        # 回测组件
        self.account = Account(initial_cash=initial_cash, db_path=":memory:")
        self.matcher = Matcher()
        self.policy_engine = PolicyEngine(cash=initial_cash, max_position_ratio=max_position_ratio)
        self.survival_rules = SurvivalRules(initial_cash=initial_cash)
        self.market_detector = MarketRegimeDetector()

        # Agent 组件
        self.model_router = model_router
        self.agent_loop: Optional[AgentLoop] = None

        # 数据
        self.historical_data: Dict[str, List[QuoteData]] = {}
        self.decision_dates: List[datetime] = []

        # 决策记录
        self.decision_records: List[AgentDecisionRecord] = []
        self.trade_records: List[Dict[str, Any]] = []

        # 统计
        self.total_llm_calls: int = 0
        self.total_tokens_used: int = 0

    async def initialize(self) -> None:
        """初始化 Agent 组件"""
        # 初始化模型路由器
        await self.model_router.initialize()

        # 创建 Agent Loop（不使用 ToolExecutor，回测时直接模拟）
        self.agent_loop = AgentLoop(
            model_router=self.model_router,
            survival_rules=self.survival_rules,
            market_detector=self.market_detector,
            tool_executor=None,  # 回测中不需要真实的工具执行
            enable_logging=True,
        )

        logger.info("Agent 回测引擎初始化完成")

    def load_historical_data(self, data_dir: Optional[Path] = None) -> bool:
        """
        加载历史数据

        Args:
            data_dir: 数据目录（默认为 data/stocks/）

        Returns:
            是否成功加载
        """
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data" / "stocks"

        for symbol in self.symbols:
            data_file = data_dir / f"stock_{symbol}.csv"

            if not data_file.exists():
                logger.error(f"未找到 {symbol} 的数据文件: {data_file}")
                return False

            try:
                import pandas as pd
                df = pd.read_csv(data_file)
                df['date'] = pd.to_datetime(df['date'])

                # 转换为 QuoteData
                quotes = []
                for i, row in df.iterrows():
                    change = 0.0
                    if i > 0:
                        change = ((row['close'] - quotes[-1].price) / quotes[-1].price) * 100
                        change = max(-11, min(11, change))

                    quotes.append(QuoteData(
                        symbol=symbol,
                        name=f"股票{symbol}",
                        price=float(row['close']),
                        change=change,
                        volume=int(row['volume']),
                        amount=float(row.get('amount', 0)),
                        high=float(row['high']),
                        low=float(row['low']),
                        open=float(row['open']),
                        timestamp=row['date'],
                    ))

                self.historical_data[symbol] = quotes
                logger.info(f"加载 {symbol}: {len(quotes)} 条 K 线数据")

            except Exception as e:
                logger.error(f"加载 {symbol} 数据失败: {e}")
                return False

        # 确定决策日期（所有股票的交集日期）
        self._determine_decision_dates()

        return True

    def _determine_decision_dates(self) -> None:
        """确定决策日期列表"""
        # 获取所有股票都存在的日期
        if not self.historical_data:
            return

        # 使用第一只股票的日期作为基准
        first_symbol = list(self.historical_data.keys())[0]
        all_dates = [
            q.timestamp for q in self.historical_data[first_symbol]
        ]

        # 每隔 decision_interval 天决策一次
        self.decision_dates = all_dates[::self.decision_interval]

        logger.info(f"决策日期: {len(self.decision_dates)} 个 (间隔 {self.decision_interval} 天)")

    async def run(self) -> Dict[str, Any]:
        """
        运行 Agent 回测

        Returns:
            回测结果
        """
        logger.info("=" * 60)
        logger.info("Agent 回测开始")
        logger.info("=" * 60)
        logger.info(f"股票代码: {', '.join(self.symbols)}")
        logger.info(f"初始资金: ¥{self.initial_cash:,.2f}")
        logger.info(f"决策间隔: {self.decision_interval} 天")
        logger.info(f"决策次数: {len(self.decision_dates)} 次")
        logger.info("=" * 60)

        # 确保已初始化
        if not self.agent_loop:
            await self.initialize()

        # 逐日决策
        for decision_idx, decision_date in enumerate(self.decision_dates):
            logger.info("")
            logger.info(f"决策 #{decision_idx + 1}/{len(self.decision_dates)} - {decision_date.date()}")

            # 更新账户持仓市值
            self._update_account_values(decision_date)

            # 检查生存等级
            survival_state = self.survival_rules.get_current_state()
            logger.info(f"生存等级: {survival_state.level.value}")

            # 检测市场状态
            market_regime = await self._detect_market_regime(decision_date)
            logger.info(f"市场状态: {market_regime.value}")

            # 对每只股票生成决策
            for symbol in self.symbols:
                try:
                    # 获取历史数据（到当前日期）
                    historical_quotes = self._get_historical_quotes(symbol, decision_date)
                    if not historical_quotes:
                        continue

                    # 获取当前行情
                    current_quote = historical_quotes[-1]

                    # 生成 Agent 决策
                    decision_record = await self._generate_agent_decision(
                        symbol=symbol,
                        current_quote=current_quote,
                        historical_quotes=historical_quotes,
                        decision_date=decision_date,
                        survival_state=survival_state,
                        market_regime=market_regime,
                    )

                    if decision_record:
                        self.decision_records.append(decision_record)

                        # 执行决策
                        await self._execute_decision(decision_record, decision_date, survival_state)

                except Exception as e:
                    logger.error(f"处理 {symbol} 时出错: {e}", exc_info=True)

        # 计算最终持仓市值
        self._update_account_values(self.decision_dates[-1] if self.decision_dates else datetime.now())

        # 生成报告
        return await self._generate_report()

    async def _generate_agent_decision(
        self,
        symbol: str,
        current_quote: QuoteData,
        historical_quotes: List[QuoteData],
        decision_date: datetime,
        survival_state,
        market_regime: MarketRegime,
    ) -> Optional[AgentDecisionRecord]:
        """
        生成 Agent 决策

        Args:
            symbol: 股票代码
            current_quote: 当前行情
            historical_quotes: 历史行情
            decision_date: 决策日期
            survival_state: 生存状态
            market_regime: 市场状态

        Returns:
            决策记录
        """
        # 构建用户输入
        user_input = self._build_user_input(symbol, current_quote, historical_quotes)

        # 获取当前持仓
        positions = self.account.get_positions()

        # 调用 Agent Loop
        try:
            response: AgentResponse = await self.agent_loop.react_loop(
                user_input=user_input,
                current_cash=self.account.cash,
                total_value=self.account.total_value,
                initial_cash=self.initial_cash,
                positions=positions,
                market_data={"symbol": symbol, "quote": current_quote},
            )

            self.total_llm_calls += 1

            if not response.success:
                logger.warning(f"Agent 决策失败: {response.message}")
                return None

            # 提取最终决策
            final_result = response.final_result
            if not final_result or not final_result.get("decision"):
                return None

            decision_data = final_result["decision"]

            # 创建决策记录
            record = AgentDecisionRecord(
                date=decision_date.strftime("%Y-%m-%d"),
                symbol=symbol,
                price=current_quote.price,
                action=decision_data.get("action", "wait"),
                confidence=decision_data.get("confidence", 0.5),
                reasoning=decision_data.get("reasoning", ""),
                is_final=decision_data.get("is_final", True),
                thought_process=response.thought_process,
                iterations=final_result.get("iterations", 0),
                model_used="llm",
                survival_level=survival_state.level.value,
                market_regime=market_regime.value,
            )

            logger.info(f"决策: {record.action.upper()} {record.symbol} "
                       f"置信度: {record.confidence:.2f}")
            logger.info(f"推理: {record.reasoning[:100]}...")

            return record

        except Exception as e:
            logger.error(f"Agent 决策异常: {e}")
            return None

    def _build_user_input(
        self,
        symbol: str,
        current_quote: QuoteData,
        historical_quotes: List[QuoteData],
    ) -> str:
        """构建用户输入"""
        # 获取技术指标摘要
        analyzer = QuoteDataAnalyzer(historical_quotes)

        # 获取最近信号
        signals = analyzer.get_latest_signals()

        # 获取均线数据
        ma5 = analyzer.get_sma(5)
        ma10 = analyzer.get_sma(10)
        ma20 = analyzer.get_sma(20)

        ma_info = ""
        if ma5 and len(ma5) > 0:
            ma_info += f"MA5: {ma5[-1]:.2f} "
        if ma10 and len(ma10) > 0:
            ma_info += f"MA10: {ma10[-1]:.2f} "
        if ma20 and len(ma20) > 0:
            ma_info += f"MA20: {ma20[-1]:.2f}"

        # 获取 RSI 和 MACD
        rsi = analyzer.get_rsi(14)
        macd, signal, hist = analyzer.get_macd()

        rsi_value = f"{rsi[-1]:.2f}" if rsi and len(rsi) > 0 else "N/A"
        macd_value = f"{macd[-1]:.4f}" if macd and len(macd) > 0 else "N/A"

        input_str = f"""请分析 {current_quote.name}({symbol}) 的当前情况并做出交易决策。

## 当前行情
- 价格: ¥{current_quote.price:.2f}
- 涨跌幅: {current_quote.change:+.2f}%
- 成交量: {current_quote.volume:,} 手
- 最高: ¥{current_quote.high:.2f}
- 最低: ¥{current_quote.low:.2f}

## 技术指标
- {ma_info}
- RSI(14): {rsi_value}
- MACD: {macd_value}
- 技术信号: {signals}

## 要求
根据以上信息，给出明确的交易决策（买入/卖出/持有/等待）。
如果选择买入或卖出，请指定数量（100股整数倍）。
"""

        return input_str

    async def _execute_decision(
        self,
        decision_record: AgentDecisionRecord,
        decision_date: datetime,
        survival_state,
    ) -> None:
        """执行决策"""
        action = decision_record.action

        # 跳过非交易决策
        if action not in ["buy", "sell"]:
            decision_record.execution_result = f"跳过 {action} 决策"
            return

        # 创建订单
        order = Order(
            order_id=f"AGENT_{decision_date.strftime('%Y%m%d_%H%M%S')}_{decision_record.symbol}",
            symbol=decision_record.symbol,
            side=OrderSide.BUY if action == "buy" else OrderSide.SELL,
            quantity=decision_record.quantity if decision_record.quantity else 100,
            price=0.0,  # 市价单
            order_type=OrderType.MARKET,
        )

        # 风控检查
        policy_check = self.policy_engine.validate_order(
            order=order,
            quote=self._get_current_quote(decision_record.symbol, decision_date),
            account=self.account,
        )

        if not policy_check.allowed:
            logger.warning(f"风控拒绝: {policy_check.reason}")
            decision_record.executed = False
            decision_record.execution_result = f"风控拒绝: {policy_check.reason}"
            return

        # 撮合订单
        match_result = await self.matcher.match(order)

        if match_result.filled_quantity > 0:
            # 更新账户
            success = self.account.update_from_trade(match_result)

            if success:
                decision_record.executed = True
                decision_record.execution_result = f"成交 {match_result.filled_quantity}股 @ ¥{match_result.filled_price:.2f}"

                # 记录交易
                self.trade_records.append({
                    "date": decision_record.date,
                    "symbol": decision_record.symbol,
                    "action": action,
                    "quantity": match_result.filled_quantity,
                    "price": match_result.filled_price,
                    "commission": match_result.commission,
                    "stamp_duty": match_result.stamp_duty,
                    "reasoning": decision_record.reasoning,
                    "confidence": decision_record.confidence,
                    "model_used": decision_record.model_used,
                })

                logger.info(f"✅ {decision_record.execution_result}")
            else:
                decision_record.executed = False
                decision_record.execution_result = "账户更新失败"
        else:
            decision_record.executed = False
            decision_record.execution_result = f"撮合失败: {match_result.reason}"

    def _get_historical_quotes(self, symbol: str, date: datetime) -> List[QuoteData]:
        """获取到指定日期的历史行情"""
        if symbol not in self.historical_data:
            return []

        quotes = self.historical_data[symbol]
        return [q for q in quotes if q.timestamp <= date]

    def _get_current_quote(self, symbol: str, date: datetime) -> Optional[QuoteData]:
        """获取指定日期的行情"""
        quotes = self._get_historical_quotes(symbol, date)
        return quotes[-1] if quotes else None

    def _update_account_values(self, date: datetime) -> None:
        """更新账户持仓市值"""
        positions = self.account.get_positions()

        for position in positions:
            quote = self._get_current_quote(position.symbol, date)
            if quote:
                position.update_market_value(quote.price)

    async def _detect_market_regime(self, date: datetime) -> MarketRegime:
        """检测市场状态"""
        try:
            # 获取上证指数数据（如果有）
            index_quotes = self._get_historical_quotes("000001", date)
            if index_quotes:
                return self.market_detector.detect(index_quotes)
        except Exception:
            pass

        return MarketRegime.SIDEWAYS

    async def _generate_report(self) -> Dict[str, Any]:
        """生成回测报告"""
        # 计算性能指标
        performance = PerformanceMetrics(
            initial_cash=self.initial_cash,
            trades=self.trade_records
        )

        # 获取最终账户状态
        final_info = self.account.get_account_info()

        # 统计决策
        decision_stats = self._calculate_decision_stats()

        # 生成报告
        report = {
            # 基础信息
            "backtest_type": "agent_llm",
            "initial_cash": self.initial_cash,
            "final_value": final_info["total_value"],
            "total_return": final_info["profit_loss_ratio"],
            "total_pnl": final_info["profit_loss"],

            # 交易统计
            "total_trades": len(self.trade_records),
            "decision_stats": decision_stats,

            # Agent 统计
            "total_llm_calls": self.total_llm_calls,
            "avg_confidence": decision_stats.get("avg_confidence", 0),

            # 性能指标
            "performance": performance.get_summary(),

            # 决策记录
            "decision_records": [r.to_dict() for r in self.decision_records],
            "trade_records": self.trade_records,
        }

        # 输出报告
        self._print_report(report)

        return report

    def _calculate_decision_stats(self) -> Dict[str, Any]:
        """计算决策统计"""
        if not self.decision_records:
            return {}

        actions = {}
        total_confidence = 0
        executed_count = 0

        for record in self.decision_records:
            action = record.action
            actions[action] = actions.get(action, 0) + 1
            total_confidence += record.confidence
            if record.executed:
                executed_count += 1

        return {
            "action_distribution": actions,
            "avg_confidence": total_confidence / len(self.decision_records),
            "execution_rate": executed_count / len(self.decision_records),
        }

    def _print_report(self, report: Dict[str, Any]) -> None:
        """打印报告"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("Agent 回测报告")
        logger.info("=" * 60)

        logger.info(f"初始资金: ¥{report['initial_cash']:,.2f}")
        logger.info(f"最终资产: ¥{report['final_value']:,.2f}")
        logger.info(f"总收益: {report['total_return']*100:+.2f}%")
        logger.info(f"总盈亏: ¥{report['total_pnl']:+,.2f}")

        logger.info("")
        logger.info("交易统计:")
        logger.info(f"总交易次数: {report['total_trades']}")

        decision_stats = report.get("decision_stats", {})
        action_dist = decision_stats.get("action_distribution", {})
        for action, count in action_dist.items():
            logger.info(f"  {action}: {count} 次")

        logger.info("")
        logger.info("Agent 统计:")
        logger.info(f"LLM 调用次数: {report['total_llm_calls']}")
        logger.info(f"平均置信度: {decision_stats.get('avg_confidence', 0):.2f}")
        logger.info(f"决策执行率: {decision_stats.get('execution_rate', 0)*100:.1f}%")

        logger.info("=" * 60)

    def save_decision_records(self, output_path: Path) -> None:
        """保存决策记录"""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        records = [r.to_dict() for r in self.decision_records]

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

        logger.info(f"决策记录已保存到: {output_path}")

    def save_trade_records(self, output_path: Path) -> None:
        """保存交易记录"""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.trade_records, f, indent=2, ensure_ascii=False)

        logger.info(f"交易记录已保存到: {output_path}")


# ============================================
# 工厂函数
# ============================================

async def create_agent_backtest_engine(
    initial_cash: float,
    symbols: List[str],
    api_key: Optional[str] = None,
    third_party_api_key: Optional[str] = None,
    third_party_base_url: Optional[str] = None,
    third_party_model: Optional[str] = None,
    local_url: Optional[str] = None,
    decision_interval: int = 5,
    max_position_ratio: float = 0.30,
) -> AgentBacktestEngine:
    """
    创建并初始化 Agent 回测引擎

    Args:
        initial_cash: 初始资金
        symbols: 股票代码列表
        api_key: Anthropic API Key (Claude)
        third_party_api_key: 第三方 API Key (GLM/OpenAI)
        third_party_base_url: 第三方 API Base URL
        third_party_model: 第三方模型名称
        local_url: 本地模型 URL (Ollama)
        decision_interval: 决策间隔（天）
        max_position_ratio: 最大仓位比例

    Returns:
        已初始化的 Agent 回测引擎
    """
    from core.model_router import create_model_router

    # 创建模型路由器
    model_router = await create_model_router(
        api_key=api_key,
        third_party_api_key=third_party_api_key,
        third_party_base_url=third_party_base_url,
        third_party_model=third_party_model,
        local_url=local_url,
        enable_local=True,
    )

    # 创建 Agent 回测引擎
    engine = AgentBacktestEngine(
        initial_cash=initial_cash,
        symbols=symbols,
        model_router=model_router,
        decision_interval=decision_interval,
        max_position_ratio=max_position_ratio,
    )

    await engine.initialize()

    return engine
