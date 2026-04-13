# -*- coding: utf-8 -*-
"""
回测引擎

实现完整的历史数据回测系统，验证策略有效性。
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path

from core.schemas import (
    Order, OrderSide, OrderType, QuoteData, OrderStatus,
    SurvivalLevel, MarketRegime, Decision, MatchResult
)
from core.survival_rules import SurvivalRules
from core.policy_engine import PolicyEngine
from core.agent_loop import AgentLoop
from core.model_router import ModelRouter
from core.market_regime import MarketRegimeDetector
from core.tool_executor import ToolExecutor
from simulation.account import Account
from simulation.matcher import Matcher
from src.indicators import QuoteDataAnalyzer, TechnicalIndicators
from src.performance import PerformanceMetrics, BacktestReport, calculate_benchmark_return


logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    回测引擎

    基于历史数据进行策略回测，评估策略表现。
    """

    def __init__(
        self,
        initial_cash: float,
        start_date: str,
        end_date: str,
        symbols: List[str],
        strategy: Optional[Callable] = None,
    ):
        """
        初始化回测引擎

        Args:
            initial_cash: 初始资金
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            symbols: 股票代码列表
            strategy: 策略函数 (可选，默认使用简单的技术指标策略)
        """
        self.initial_cash = initial_cash
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        self.symbols = symbols

        # 回测组件
        self.account = Account(initial_cash=initial_cash, db_path=":memory:")
        self.matcher = Matcher()
        self.policy_engine = PolicyEngine(cash=initial_cash, max_position_ratio=0.30)
        self.survival_rules = SurvivalRules(initial_cash=initial_cash)

        # 策略
        self.strategy = strategy or self._default_strategy

        # 数据
        self.historical_data: Dict[str, List[QuoteData]] = {}
        self.current_date: Optional[datetime] = None
        self.current_quotes: Dict[str, QuoteData] = {}

        # 交易记录
        self.trade_records: List[Dict[str, Any]] = []

    def _default_strategy(self, analyzer: QuoteDataAnalyzer, account_info: Dict[str, Any]) -> Optional[Decision]:
        """
        默认策略：基于技术指标的简单策略

        策略规则：
        1. RSI < 30 且 MACD 金叉 -> 买入
        2. RSI > 70 或 MACD 死叉 -> 卖出
        """
        signals = analyzer.get_latest_signals()

        # 获取最新价格
        if not analyzer.quotes:
            return None

        latest_quote = analyzer.quotes[-1]
        current_price = latest_quote.price

        # 检查持仓
        positions = self.account.get_positions()
        has_position = any(pos.symbol == latest_quote.symbol for pos in positions)

        # 买入信号：超卖 + 金叉
        if not has_position:
            if signals.get("rsi") == "oversold" or signals.get("macd") == "bullish_cross":
                return Decision(
                    action="buy",
                    symbol=latest_quote.symbol,
                    quantity=100,  # 固定手数
                    price=current_price,
                    reasoning=f"RSI超卖({signals.get('rsi')})或MACD金叉({signals.get('macd')})",
                    confidence=0.7,
                )

        # 卖出信号：超买或死叉
        else:
            if signals.get("rsi") == "overbought" or signals.get("macd") == "bearish_cross":
                position = next(pos for pos in positions if pos.symbol == latest_quote.symbol)
                return Decision(
                    action="sell",
                    symbol=latest_quote.symbol,
                    quantity=position.shares,
                    price=current_price,
                    reasoning=f"RSI超买({signals.get('rsi')})或MACD死叉({signals.get('macd')})",
                    confidence=0.7,
                )

        return None

    def load_historical_data(self, data_path: Optional[str] = None) -> bool:
        """
        加载历史数据

        Args:
            data_path: 数据文件路径 (可选)

        Returns:
            是否成功加载
        """
        # TODO: 实现从文件或 API 加载历史数据
        # 这里使用模拟数据演示
        logger.warning("使用模拟数据进行回测演示")

        for symbol in self.symbols:
            self.historical_data[symbol] = self._generate_mock_data(symbol)

        return True

    def _generate_mock_data(self, symbol: str) -> List[QuoteData]:
        """生成模拟历史数据"""
        mock_data = []
        current_date = self.start_date
        base_price = 100.0

        while current_date <= self.end_date:
            # 跳过周末
            if current_date.weekday() < 5:
                # 随机价格波动
                import random
                change_pct = (random.random() - 0.5) * 0.04  # ±2% 波动
                price = base_price * (1 + change_pct)

                mock_data.append(QuoteData(
                    symbol=symbol,
                    name=f"股票{symbol}",
                    price=price,
                    change=change_pct * 100,
                    volume=random.randint(1000000, 10000000),
                    amount=price * random.randint(1000000, 10000000),
                    high=price * 1.01,
                    low=price * 0.99,
                    upper_limit=price * 1.1,
                    lower_limit=price * 0.9,
                ))

                base_price = price

            current_date += timedelta(days=1)

        return mock_data

    def run(self) -> Dict[str, Any]:
        """
        运行回测

        Returns:
            回测结果
        """
        logger.info("=" * 60)
        logger.info("开始回测")
        logger.info("=" * 60)
        logger.info(f"回测期间: {self.start_date.date()} ~ {self.end_date.date()}")
        logger.info(f"股票代码: {', '.join(self.symbols)}")
        logger.info(f"初始资金: ¥{self.initial_cash:,.2f}")

        # 加载数据
        if not self.load_historical_data():
            logger.error("加载历史数据失败")
            return {}

        # 确定回测日期范围
        all_dates = set()
        for quotes in self.historical_data.values():
            for quote in quotes:
                # 模拟数据没有日期，使用索引
                pass

        # 使用第一个股票的数据长度作为回测天数
        backtest_days = len(list(self.historical_data.values())[0])

        # 逐日回测
        for day_idx in range(backtest_days):
            self.current_date = self.start_date + timedelta(days=day_idx)

            # 获取当日行情
            self.current_quotes = {}
            for symbol, quotes in self.historical_data.items():
                if day_idx < len(quotes):
                    self.current_quotes[symbol] = quotes[day_idx]
                    self.matcher.update_quote(quotes[day_idx])

            # 跳过没有数据的日期
            if not self.current_quotes:
                continue

            # 更新账户持仓市值
            self._update_account_values()

            # 检查生存等级
            survival_state = self.survival_rules.get_current_state()

            # 对每个股票执行策略
            for symbol, quote in self.current_quotes.items():
                try:
                    # 获取历史数据（到当前日期）
                    historical_quotes = self.historical_data[symbol][:day_idx + 1]

                    # 创建分析器
                    analyzer = QuoteDataAnalyzer(historical_quotes)

                    # 生成交易决策
                    account_info = self.account.get_account_info()
                    decision = self.strategy(analyzer, account_info)

                    if decision:
                        # 执行交易
                        self._execute_decision(decision, survival_state)

                except Exception as e:
                    logger.error(f"处理 {symbol} 时出错: {e}")

            # 每50天输出进度
            if (day_idx + 1) % 50 == 0:
                account_info = self.account.get_account_info()
                logger.info(f"第 {day_idx + 1} 天 - 总资产: ¥{account_info['total_value']:,.2f}")

        # 计算性能指标
        logger.info("\n回测完成，计算性能指标...")

        performance = PerformanceMetrics(
            initial_cash=self.initial_cash,
            trades=self.trade_records
        )

        # 生成报告
        report_generator = BacktestReport(
            performance=performance,
            metadata={
                "start_date": self.start_date.strftime("%Y-%m-%d"),
                "end_date": self.end_date.strftime("%Y-%m-%d"),
                "symbols": ", ".join(self.symbols),
                "strategy": "default_technical",
            }
        )

        # 输出报告
        text_report = report_generator.generate_text()
        logger.info("\n" + text_report)

        return report_generator.generate_dict()

    def _update_account_values(self):
        """更新账户持仓市值

        注意：回测中持仓市值通过交易记录计算，不需要实时更新
        """
        # 在回测中，我们通过交易记录来计算最终结果
        # 不需要实时更新持仓的市值
        pass

    def _execute_decision(self, decision: Decision, survival_state):
        """
        执行交易决策

        Args:
            decision: 交易决策
            survival_state: 生存状态
        """
        # 创建订单
        order = Order(
            order_id=f"BT_{self.current_date.strftime('%Y%m%d')}_{decision.symbol}",
            symbol=decision.symbol,
            side=OrderSide.BUY if decision.action == "buy" else OrderSide.SELL,
            quantity=decision.quantity or 100,
            price=decision.price or 0.0,
            order_type=OrderType.MARKET,
        )

        # 风控检查
        policy_check = self.policy_engine.validate_order(
            order=order,
            quote=self.current_quotes.get(order.symbol),
        )

        if not policy_check.allowed:
            logger.debug(f"风控拒绝: {policy_check.reason}")
            return

        # 撮合订单
        match_result = asyncio.run(self.matcher.match(order))

        if match_result.filled_quantity > 0:
            # 更新账户
            success = self.account.update_from_trade(match_result)

            if success:
                # 记录交易
                self.trade_records.append({
                    "date": self.current_date.strftime("%Y-%m-%d"),
                    "symbol": decision.symbol,
                    "action": decision.action,
                    "quantity": match_result.filled_quantity,
                    "price": match_result.filled_price,
                    "pnl": 0.0,  # 回测中 pnl 需要后续计算
                    "reasoning": decision.reasoning,
                })

                logger.debug(f"交易成功: {decision.action} {match_result.filled_quantity}股 "
                           f"@ ¥{match_result.filled_price:.2f}")


def run_backtest(
    start_date: str,
    end_date: str,
    symbols: List[str],
    initial_cash: float = 1_000_000.0,
    strategy: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    运行回测

    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        symbols: 股票代码列表
        initial_cash: 初始资金
        strategy: 策略函数 (可选)

    Returns:
        回测结果
    """
    engine = BacktestEngine(
        initial_cash=initial_cash,
        start_date=start_date,
        end_date=end_date,
        symbols=symbols,
        strategy=strategy,
    )

    return engine.run()
