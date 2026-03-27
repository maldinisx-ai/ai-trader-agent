# -*- coding: utf-8 -*-
"""
实盘交易模式

实现完整的实时交易循环，包括行情获取、决策、执行、风控等。
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

from core.schemas import (
    Order, OrderSide, OrderType, QuoteData, AgentContext,
    SurvivalLevel, MarketRegime, Decision, MatchResult
)
from core.survival_rules import SurvivalRules
from core.policy_engine import PolicyEngine
from core.agent_loop import AgentLoop
from core.model_router import ModelRouter
from core.tool_executor import ToolExecutor
from core.market_regime import MarketRegimeDetector
from simulation.account import Account
from simulation.matcher import Matcher
from tools.data.get_quote import GetQuoteTool
from tools.trading.place_order import PlaceOrderTool
from tools.trading.get_positions import GetPositionsTool


# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TradingMetrics:
    """交易指标统计"""

    def __init__(self):
        self.total_decisions: int = 0
        self.successful_trades: int = 0
        self.rejected_trades: int = 0
        self.failed_trades: int = 0
        self.total_pnl: float = 0.0
        self.start_time: datetime = datetime.now()
        self.last_decision_time: Optional[datetime] = None
        self.decisions_by_survival: Dict[SurvivalLevel, int] = {
            SurvivalLevel.CRITICAL: 0,
            SurvivalLevel.LOW_COMPUTE: 0,
            SurvivalLevel.NORMAL: 0,
            SurvivalLevel.DEAD: 0,
        }

    def record_decision(self, survival_level: SurvivalLevel):
        """记录决策"""
        self.total_decisions += 1
        self.decisions_by_survival[survival_level] += 1
        self.last_decision_time = datetime.now()

    def record_trade(self, success: bool, pnl: float = 0.0):
        """记录交易结果"""
        if success:
            self.successful_trades += 1
            self.total_pnl += pnl
        else:
            self.failed_trades += 1

    def record_rejection(self):
        """记录拒绝交易"""
        self.rejected_trades += 1

    def get_summary(self) -> Dict[str, Any]:
        """获取统计摘要"""
        uptime = datetime.now() - self.start_time

        return {
            "total_decisions": self.total_decisions,
            "successful_trades": self.successful_trades,
            "rejected_trades": self.rejected_trades,
            "failed_trades": self.failed_trades,
            "total_pnl": self.total_pnl,
            "win_rate": self.successful_trades / max(1, self.successful_trades + self.failed_trades),
            "uptime_seconds": uptime.total_seconds(),
            "decisions_by_survival": {
                level.value: count
                for level, count in self.decisions_by_survival.items()
            },
            "last_decision_time": self.last_decision_time.isoformat() if self.last_decision_time else None,
        }


class TraderConfig:
    """交易配置"""

    def __init__(self, config: Dict[str, Any]):
        self.trading_symbols: List[str] = config.get("symbols", ["600519"])
        self.max_position_ratio: float = config.get("max_position_ratio", 0.30)
        self.decision_interval_seconds: int = config.get("decision_interval", 60)
        self.market_open_hour: int = config.get("market_open_hour", 9)
        self.market_open_minute: int = config.get("market_open_minute", 30)
        self.market_close_hour: int = config.get("market_close_hour", 15)
        self.market_close_minute: int = config.get("market_close_minute", 0)
        self.enable_auto_trading: bool = config.get("enable_auto_trading", False)
        self.dry_run: bool = config.get("dry_run", True)

    def is_market_open(self) -> bool:
        """检查市场是否开盘"""
        now = datetime.now()
        current_time = now.hour * 60 + now.minute

        open_time = self.market_open_hour * 60 + self.market_open_minute
        close_time = self.market_close_hour * 60 + self.market_close_minute

        # 检查是否是周末
        if now.weekday() >= 5:  # 周六=5, 周日=6
            return False

        return open_time <= current_time < close_time


class LiveTrader:
    """
    实盘交易器

    实现完整的交易循环：
    1. 获取实时行情
    2. 更新账户状态
    3. 检查生存等级
    4. 生成交易决策
    5. 风控检查
    6. 执行交易
    7. 记录交易
    """

    def __init__(
        self,
        account: Account,
        policy_engine: PolicyEngine,
        survival_rules: SurvivalRules,
        matcher: Matcher,
        tool_executor: ToolExecutor,
        config: Dict[str, Any],
    ):
        self.account = account
        self.policy_engine = policy_engine
        self.survival_rules = survival_rules
        self.matcher = matcher
        self.tool_executor = tool_executor

        # 配置
        trader_config = config.get("trader", {})
        self.config = TraderConfig(trader_config)

        # 组件
        self.agent_loop = AgentLoop(
            model_router=ModelRouter(),
            survival_rules=survival_rules,
            market_detector=MarketRegimeDetector(),
            tool_executor=tool_executor,
        )
        self.regime_detector = MarketRegimeDetector()

        # 状态
        self.running: bool = False
        self.should_stop: bool = False
        self.metrics = TradingMetrics()

        # 行情缓存
        self._quotes: Dict[str, QuoteData] = {}

    async def start(self):
        """启动交易循环"""
        logger.info("=" * 60)
        logger.info("AI Trader Agent - 实盘交易模式")
        logger.info("=" * 60)

        if self.config.dry_run:
            logger.info("⚠️  模拟交易模式 (Dry Run) - 不会执行真实交易")
        else:
            logger.info("🔴 实盘交易模式 - 将执行真实交易")

        logger.info(f"交易标的: {', '.join(self.config.trading_symbols or ['None'])}")
        logger.info(f"决策间隔: {self.config.decision_interval_seconds}秒")
        logger.info(f"自动交易: {'启用' if self.config.enable_auto_trading else '禁用'}")

        # 检查市场是否开盘
        if not self.config.is_market_open():
            logger.warning("⚠️  当前时间不在交易时段内")
            logger.info(f"交易时段: {self.config.market_open_hour:02d}:{self.config.market_open_minute:02d} - "
                       f"{self.config.market_close_hour:02d}:{self.config.market_close_minute:02d}")

        self.running = True
        logger.info("🚀 交易循环启动")
        logger.info("=" * 60)

        try:
            await self._trading_loop()
        except Exception as e:
            logger.error(f"交易循环异常: {e}", exc_info=True)
        finally:
            await self.stop()

    async def stop(self):
        """停止交易循环"""
        logger.info("正在停止交易循环...")
        self.running = False
        self.should_stop = True

        # 输出最终统计
        self._print_summary()

    async def _trading_loop(self):
        """交易循环主逻辑"""
        iteration = 0

        while self.running and not self.should_stop:
            iteration += 1
            logger.info("-" * 40)
            logger.info(f"迭代 #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            try:
                # 1. 检查市场状态
                if not self.config.is_market_open():
                    logger.info("市场休市，等待开盘...")
                    await asyncio.sleep(60)
                    continue

                # 2. 获取实时行情
                quotes = await self._get_quotes()
                if not quotes:
                    logger.warning("未获取到行情数据，跳过本次迭代")
                    await asyncio.sleep(self.config.decision_interval_seconds)
                    continue

                # 3. 更新撮合引擎行情
                for quote in quotes:
                    self.matcher.update_quote(quote)

                # 4. 更新账户持仓市值
                self._update_account_values(quotes)

                # 5. 检查生存等级
                survival_state = self.survival_rules.get_current_state()
                logger.info(f"生存等级: {survival_state.level.value} (权益: ¥{self.account.total_value:,.2f})")

                # 6. 检测市场状态
                market_regime = await self._detect_market_regime(quotes)
                logger.info(f"市场状态: {market_regime.value}")

                # 7. 生成交易决策
                decision = await self._generate_decision(quotes, survival_state, market_regime)
                if not decision:
                    logger.info("无交易决策")
                    await asyncio.sleep(self.config.decision_interval_seconds)
                    continue

                self.metrics.record_decision(survival_state.level)
                logger.info(f"决策: {decision.action.upper()} {decision.symbol} "
                          f"{decision.quantity or 0}股 @ ¥{decision.price or 0:.2f}")
                logger.info(f"理由: {decision.reasoning[:100]}...")

                # 8. 风控检查
                policy_check = self.policy_engine.validate_order(
                    order=self._create_order_from_decision(decision),
                    account=self.account,
                )

                if not policy_check.approved:
                    logger.warning(f"⛔ 风控拒绝: {policy_check.reason}")
                    self.metrics.record_rejection()
                    await asyncio.sleep(self.config.decision_interval_seconds)
                    continue

                # 9. 执行交易
                if self.config.enable_auto_trading:
                    await self._execute_decision(decision)
                else:
                    logger.info("🔒 自动交易未启用，跳过执行")

                # 10. 等待下一次决策
                logger.info(f"等待 {self.config.decision_interval_seconds} 秒...")
                await asyncio.sleep(self.config.decision_interval_seconds)

            except asyncio.CancelledError:
                logger.info("交易循环被取消")
                break
            except Exception as e:
                logger.error(f"迭代 #{iteration} 异常: {e}", exc_info=True)
                await asyncio.sleep(self.config.decision_interval_seconds)

    async def _get_quotes(self) -> List[QuoteData]:
        """获取实时行情"""
        quotes = []

        for symbol in self.config.trading_symbols:
            try:
                # 使用 GetQuoteTool 获取行情
                result = await self.tool_executor.execute_tool(
                    tool_name="get_quote",
                    params={"symbol": symbol}
                )

                if result.success and result.data:
                    quote = result.data
                    quotes.append(quote)
                    logger.info(f"📊 {symbol} - ¥{quote.price:.2f} ({quote.change:+.2f}%)")
                else:
                    logger.warning(f"获取 {symbol} 行情失败: {result.error}")

            except Exception as e:
                logger.error(f"获取 {symbol} 行情异常: {e}")

        return quotes

    def _update_account_values(self, quotes: List[QuoteData]):
        """更新账户持仓市值"""
        quote_map = {q.symbol: q.price for q in quotes}
        positions = self.account.get_positions()

        for pos in positions:
            if pos.symbol in quote_map:
                current_price = quote_map[pos.symbol]
                pos.update_market_value(current_price)

    async def _detect_market_regime(self, quotes: List[QuoteData]) -> MarketRegime:
        """检测市场状态"""
        try:
            # 使用 MarketRegimeDetector 检测
            return self.regime_detector.detect(quotes)
        except Exception as e:
            logger.warning(f"市场状态检测失败: {e}")
            return MarketRegime.SIDEWAYS

    async def _generate_decision(
        self,
        quotes: List[QuoteData],
        survival_state,
        market_regime: MarketRegime,
    ) -> Optional[Decision]:
        """生成交易决策"""
        try:
            # 构建上下文
            context = self._build_context(quotes, survival_state, market_regime)

            # 使用 AgentLoop 生成决策
            result = await self.agent_loop.run(context)

            if result and result.decision:
                return result.decision

            return None

        except Exception as e:
            logger.error(f"生成决策异常: {e}", exc_info=True)
            return None

    def _build_context(
        self,
        quotes: List[QuoteData],
        survival_state,
        market_regime: MarketRegime,
    ) -> AgentContext:
        """构建Agent决策上下文"""
        account_info = self.account.get_account_info()
        positions = self.account.get_positions()

        # 构建用户输入描述
        market_data_str = "; ".join([
            f"{q.name}({q.symbol}): ¥{q.price:.2f} ({q.change:+.2f}%)"
            for q in quotes
        ])

        user_input = (
            f"当前市场状态: {market_regime.value}。"
            f"行情数据: {market_data_str}。"
            f"请根据当前账户状态和市场情况做出交易决策。"
        )

        return AgentContext(
            user_input=user_input,
            current_cash=account_info["cash"],
            total_value=account_info["total_value"],
            initial_cash=account_info["initial_cash"],
            positions=positions,
            survival_level=survival_state.level,
            market_regime=market_regime,
            max_position_ratio=self.config.max_position_ratio,
            trading_enabled=True,
        )

    def _create_order_from_decision(self, decision: Decision) -> Order:
        """从决策创建订单"""
        return Order(
            order_id=f"LIVE_{datetime.now().strftime('%Y%m%d%H%M%S_%f')}",
            symbol=decision.symbol,
            side=OrderSide.BUY if decision.action == "buy" else OrderSide.SELL,
            quantity=decision.quantity or 100,
            price=decision.price or 0.0,
            order_type=OrderType.MARKET,
        )

    async def _execute_decision(self, decision: Decision):
        """执行交易决策"""
        order = self._create_order_from_decision(decision)

        try:
            # 撮合订单
            match_result = await self.matcher.match(order)

            if match_result.success:
                # 更新账户
                success = self.account.update_from_trade(match_result)

                if success:
                    pnl = match_result.pnl or 0.0
                    self.metrics.record_trade(success=True, pnl=pnl)
                    logger.info(f"✅ 交易成功: {order.side.value} {match_result.filled_quantity}股 "
                              f"@ ¥{match_result.filled_price:.2f}")
                    logger.info(f"   手续费: ¥{match_result.commission:.2f} "
                              f"印花税: ¥{match_result.stamp_duty:.2f}")
                    if pnl != 0:
                        logger.info(f"   盈亏: ¥{pnl:+,.2f}")
                else:
                    self.metrics.record_trade(success=False)
                    logger.error(f"❌ 账户更新失败")
            else:
                self.metrics.record_trade(success=False)
                logger.warning(f"⚠️ 撮合失败: {match_result.reason}")

        except Exception as e:
            self.metrics.record_trade(success=False)
            logger.error(f"执行交易异常: {e}", exc_info=True)

    def _print_summary(self):
        """打印交易摘要"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("交易统计摘要")
        logger.info("=" * 60)

        summary = self.metrics.get_summary()

        logger.info(f"总决策数: {summary['total_decisions']}")
        logger.info(f"成功交易: {summary['successful_trades']}")
        logger.info(f"拒绝交易: {summary['rejected_trades']}")
        logger.info(f"失败交易: {summary['failed_trades']}")
        logger.info(f"胜率: {summary['win_rate']*100:.1f}%")
        logger.info(f"总盈亏: ¥{summary['total_pnl']:+,.2f}")
        logger.info(f"运行时长: {summary['uptime_seconds']/3600:.1f}小时")

        logger.info("")
        logger.info("按生存等级统计:")
        for level, count in summary['decisions_by_survival'].items():
            if count > 0:
                logger.info(f"  {level}: {count} 次")

        # 账户最终状态
        account_info = self.account.get_account_info()
        logger.info("")
        logger.info("账户最终状态:")
        logger.info(f"初始资金: ¥{account_info['initial_cash']:,.2f}")
        logger.info(f"当前现金: ¥{account_info['cash']:,.2f}")
        logger.info(f"持仓市值: ¥{account_info['position_value']:,.2f}")
        logger.info(f"总资产:   ¥{account_info['total_value']:,.2f}")
        logger.info(f"总盈亏:   ¥{account_info['profit_loss']:+,.2f} ({account_info['profit_loss_ratio']*100:+.2f}%)")

        logger.info("=" * 60)


async def run_live_trader(
    account: Account,
    policy_engine: PolicyEngine,
    survival_rules: SurvivalRules,
    matcher: Matcher,
    tool_executor: ToolExecutor,
    config: Dict[str, Any],
):
    """
    运行实盘交易器

    Args:
        account: 模拟账户
        policy_engine: 风控引擎
        survival_rules: 生存规则
        matcher: 撮合引擎
        tool_executor: 工具执行器
        config: 配置字典
    """
    trader = LiveTrader(
        account=account,
        policy_engine=policy_engine,
        survival_rules=survival_rules,
        matcher=matcher,
        tool_executor=tool_executor,
        config=config,
    )

    await trader.start()
