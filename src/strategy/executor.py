"""
策略执行器 - 应用策略到股票分析

整合评分引擎和数据准备器，实现完整的策略分析流程。
"""
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from .manager import StrategyManager, get_strategy_manager
from .scoring import (
    ScoringResult,
    SignalType,
    get_strategy_engine,
    MomentumScoringEngine,
    ValueReversalScoringEngine,
    BreakoutVolumeScoringEngine,
)
from .data_preparer import MarketDataPreparer, FinancialDataPreparer

logger = logging.getLogger(__name__)


@dataclass
class StrategySignal:
    """策略信号"""
    strategy_name: str
    display_name: str
    signal: str  # buy, sell, hold
    confidence: float  # 0-1
    score: int  # 0-100
    reasoning: str
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    factors: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class StrategyAnalysisResult:
    """策略分析结果"""
    stock_code: str
    stock_name: str
    signals: List[StrategySignal]
    overall_signal: str  # buy, sell, hold
    overall_score: int
    overall_confidence: float
    active_strategies: List[str]
    analysis_time: str
    market_data: Optional[Dict[str, Any]] = None
    financial_data: Optional[Dict[str, Any]] = None


class StrategyExecutor:
    """策略执行器 - 整合评分引擎"""

    def __init__(self, strategy_manager: Optional[StrategyManager] = None):
        """
        初始化策略执行器

        Args:
            strategy_manager: 策略管理器，默认使用单例
        """
        self.strategy_manager = strategy_manager or get_strategy_manager()
        self.data_preparer = MarketDataPreparer()
        self.financial_preparer = FinancialDataPreparer()

    def analyze_with_strategy(
        self,
        stock_code: str,
        stock_name: str,
        strategy_name: str,
        market_data: Dict[str, Any],
        financial_data: Optional[Dict[str, Any]] = None,
    ) -> StrategySignal:
        """
        使用指定策略分析股票

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            strategy_name: 策略名称
            market_data: 市场数据（原始数据或已处理数据）
            financial_data: 财务数据（可选）

        Returns:
            策略信号
        """
        strategy = self.strategy_manager.get_strategy(strategy_name)
        if not strategy:
            logger.warning(f"策略不存在: {strategy_name}")
            return self._create_neutral_signal(f"策略不存在: {strategy_name}")

        # 准备数据（如果需要）
        prepared_market = self._prepare_market_data(market_data)
        prepared_financial = self._prepare_financial_data(financial_data)

        # 获取策略评分引擎
        engine_class = get_strategy_engine(strategy_name)
        if not engine_class:
            logger.warning(f"策略 {strategy_name} 没有对应的评分引擎")
            return self._create_neutral_signal(f"策略 {strategy_name} 暂不支持自动评分")

        # 执行评分
        scoring_result: ScoringResult = engine_class.calculate(
            prepared_market, prepared_financial
        )

        # 计算价格点位
        entry_price, stop_loss, take_profit = self._calculate_price_levels(
            scoring_result.signal, prepared_market, strategy
        )

        return StrategySignal(
            strategy_name=strategy.name,
            display_name=strategy.display_name,
            signal=scoring_result.signal.value,
            confidence=scoring_result.confidence,
            score=scoring_result.score,
            reasoning=scoring_result.reasoning,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            factors=[
                {
                    "name": f["name"],
                    "score": f["score"],
                    "reason": f["reason"],
                    "category": f.get("category", "general"),
                }
                for f in scoring_result.factors
            ],
        )

    def analyze_with_active_strategies(
        self,
        stock_code: str,
        stock_name: str,
        market_data: Dict[str, Any],
        financial_data: Optional[Dict[str, Any]] = None,
    ) -> StrategyAnalysisResult:
        """
        使用所有激活的策略分析股票

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            market_data: 市场数据
            financial_data: 财务数据（可选）

        Returns:
            策略分析结果
        """
        active_strategies = self.strategy_manager.get_active_strategies()
        if not active_strategies:
            logger.warning("没有激活的策略")
            return self._create_empty_result(stock_code, stock_name)

        signals = []
        total_score = 0
        total_confidence = 0

        # 准备数据（避免重复准备）
        prepared_market = self._prepare_market_data(market_data)
        prepared_financial = self._prepare_financial_data(financial_data)

        # 对每个策略执行分析
        for strategy in active_strategies:
            try:
                signal = self.analyze_with_strategy(
                    stock_code,
                    stock_name,
                    strategy.name,
                    prepared_market,
                    prepared_financial,
                )
                signals.append(signal)
                total_score += signal.score
                total_confidence += signal.confidence
            except Exception as e:
                logger.error(f"策略 {strategy.name} 分析失败: {e}")
                # 继续执行其他策略

        if not signals:
            return self._create_empty_result(stock_code, stock_name)

        # 计算综合信号
        overall_score = int(total_score / len(signals))
        overall_confidence = total_confidence / len(signals)
        overall_signal = self._score_to_signal_str(overall_score)

        return StrategyAnalysisResult(
            stock_code=stock_code,
            stock_name=stock_name,
            signals=signals,
            overall_signal=overall_signal,
            overall_score=overall_score,
            overall_confidence=overall_confidence,
            active_strategies=[s.name for s in active_strategies],
            analysis_time=datetime.now().isoformat(),
            market_data=prepared_market,
            financial_data=prepared_financial,
        )

    def analyze_from_csv(
        self,
        stock_code: str,
        stock_name: str,
        kline_df,  # K线数据 DataFrame
        financial_df=None,  # 财务数据 DataFrame
        money_flow=None,  # 资金流向数据
    ) -> StrategyAnalysisResult:
        """
        从 CSV 数据分析股票

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            kline_df: K线数据 DataFrame
            financial_df: 财务数据 DataFrame（可选）
            money_flow: 资金流向数据（可选）

        Returns:
            策略分析结果
        """
        import pandas as pd

        # 准备市场数据
        market_data = self.data_preparer.prepare_from_df(kline_df)

        # 添加资金流向数据
        if money_flow:
            market_data = self.data_preparer.prepare_with_money_flow(
                market_data, money_flow
            )

        # 准备财务数据
        financial_data = None
        if financial_df is not None and not financial_df.empty:
            financial_data = self.financial_preparer.prepare_from_financials(financial_df)

        return self.analyze_with_active_strategies(
            stock_code, stock_name, market_data, financial_data
        )

    def _prepare_market_data(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """准备市场数据"""
        # 如果已经包含必要字段，直接返回
        if "close" in market_data and "ma5" in market_data:
            return market_data

        # 否则尝试从 DataFrame 或其他格式转换
        if "df" in market_data:
            return self.data_preparer.prepare_from_df(market_data["df"])

        return market_data

    def _prepare_financial_data(self, financial_data: Optional[Dict]) -> Optional[Dict]:
        """准备财务数据"""
        if not financial_data:
            return None

        # 如果已经包含必要字段，直接返回
        if "pe" in financial_data:
            return financial_data

        # 否则尝试从 DataFrame 转换
        if "df" in financial_data:
            import pandas as pd
            df = financial_data["df"]
            if isinstance(df, pd.DataFrame) and not df.empty:
                return self.financial_preparer.prepare_from_financials(df)

        return financial_data

    def _score_to_signal_str(self, score: int) -> str:
        """将评分转换为信号字符串"""
        if score >= 70:
            return "buy"
        elif score <= 30:
            return "sell"
        else:
            return "hold"

    def _calculate_price_levels(
        self,
        signal: SignalType,
        market_data: Dict[str, Any],
        strategy,
    ) -> tuple:
        """
        计算价格点位（买入价、止损价、目标价）

        根据策略类型和市场数据计算精确的价格点位
        """
        current_price = market_data.get("close", 0)
        if current_price == 0:
            return None, None, None

        if signal == SignalType.BUY:
            entry = current_price

            # 根据策略类型设置不同的止损止盈
            if strategy.category == "trend":
                # 趋势策略：MA20 止损
                ma20 = market_data.get("ma20", 0)
                if ma20 > 0:
                    stop_loss = max(ma20 * 0.97, current_price * 0.95)
                else:
                    stop_loss = current_price * 0.95

                # 止盈：保守 12%，激进 20%
                take_profit = current_price * 1.12

            elif strategy.category == "reversal":
                # 反转策略：更宽的止损
                low_20 = min(market_data.get("low", current_price) for _ in range(1))
                stop_loss = low_20 * 0.98
                take_profit = current_price * 1.20

            elif strategy.category == "pattern":
                # 形态策略：突破位止损
                ma10 = market_data.get("ma10", 0)
                if ma10 > 0:
                    stop_loss = ma10 * 0.97
                else:
                    stop_loss = current_price * 0.95

                take_profit = current_price * 1.15

            else:
                # 默认设置
                stop_loss = current_price * 0.95
                take_profit = current_price * 1.12

        elif signal == SignalType.SELL:
            entry = None
            stop_loss = None
            take_profit = None

        else:  # HOLD
            entry = None
            stop_loss = None
            take_profit = None

        return entry, stop_loss, take_profit

    def _create_neutral_signal(self, reason: str) -> StrategySignal:
        """创建中性信号"""
        return StrategySignal(
            strategy_name="neutral",
            display_name="中性",
            signal="hold",
            confidence=0.5,
            score=50,
            reasoning=reason,
        )

    def _create_empty_result(self, stock_code: str, stock_name: str) -> StrategyAnalysisResult:
        """创建空结果"""
        return StrategyAnalysisResult(
            stock_code=stock_code,
            stock_name=stock_name,
            signals=[],
            overall_signal="hold",
            overall_score=50,
            overall_confidence=0.5,
            active_strategies=[],
            analysis_time=datetime.now().isoformat(),
        )
