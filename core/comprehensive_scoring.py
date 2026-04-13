# -*- coding: utf-8 -*-
"""
多维度综合评分策略

结合技术面、基本面、资金面的综合评分系统。
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from src.indicators import QuoteDataAnalyzer
from core.scoring import TrendScoringSystem, ScoreResult
from core.fundamental_scoring import FundamentalScorer, FundamentalScore
from core.money_flow_scoring import MoneyFlowScorer, MoneyFlowScore
from core.schemas import BuySignal

logger = logging.getLogger(__name__)


@dataclass
class ComprehensiveScore:
    """综合评分结果"""
    total_score: int              # 总分 0-100
    technical_score: int          # 技术面得分 0-100
    fundamental_score: int        # 基本面得分 0-100
    money_flow_score: int         # 资金面得分 0-100

    buy_signal: BuySignal          # 买入信号

    # 细分得分
    trend_score: int              # 趋势得分
    bias_score: int               # 乖离得分
    volume_score: int             # 量能得分
    roe_score: int                # ROE得分
    growth_score: int             # 成长性得分
    valuation_score: int          # 估值得分
    quality_score: int            # 质量得分
    main_flow_score: int          # 主力流入得分
    net_flow_score: int           # 净流入得分
    margin_score: int             # 融资融券得分

    reasons: list[str] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'total_score': self.total_score,
            'buy_signal': self.buy_signal.value,
            'technical_score': self.technical_score,
            'fundamental_score': self.fundamental_score,
            'money_flow_score': self.money_flow_score,
            'trend_score': self.trend_score,
            'bias_score': self.bias_score,
            'volume_score': self.volume_score,
            'roe_score': self.roe_score,
            'growth_score': self.growth_score,
            'valuation_score': self.valuation_score,
            'quality_score': self.quality_score,
            'main_flow_score': self.main_flow_score,
            'net_flow_score': self.net_flow_score,
            'margin_score': self.margin_score,
            'reasons': self.reasons,
            'risk_factors': self.risk_factors,
        }


class ComprehensiveScoringSystem:
    """
    多维度综合评分系统

    基于研究日志中的建议，结合：
    1. 技术面 (权重 35%): 趋势、乖离率、量能、MACD、RSI
    2. 基本面 (权重 35%): ROE、成长性、估值、质量
    3. 资金面 (权重 30%): 主力流入、净流入、融资融券

    评分阈值:
    - ≥75: 强烈买入
    - ≥60: 买入
    - ≥45: 持有
    - ≥30: 观望
    - <30: 卖出
    """

    # 综合权重配置
    COMPREHENSIVE_WEIGHTS = {
        'technical': 35,
        'fundamental': 35,
        'money_flow': 30,
    }

    # 信号阈值
    SIGNAL_THRESHOLDS = {
        'strong_buy': 75,
        'buy': 60,
        'hold': 45,
        'wait': 30,
    }

    def __init__(self, data_dir: str = "data"):
        """
        初始化评分系统

        Args:
            data_dir: 数据目录
        """
        # 初始化各评分器
        self.technical_scorer = TrendScoringSystem()
        self.fundamental_scorer = FundamentalScorer(data_dir=data_dir)
        self.money_flow_scorer = MoneyFlowScorer(data_dir=data_dir)

    def score(
        self,
        symbol: str,
        analyzer: QuoteDataAnalyzer,
        current_price: float = 0
    ) -> ComprehensiveScore:
        """
        计算综合评分

        Args:
            symbol: 股票代码
            analyzer: 行情数据分析器
            current_price: 当前价格

        Returns:
            综合评分结果
        """
        # 技术面评分
        tech_result: ScoreResult = self.technical_scorer.score(analyzer)

        # 基本面评分
        fund_result: FundamentalScore = self.fundamental_scorer.score(symbol, current_price)

        # 资金面评分
        money_result: MoneyFlowScore = self.money_flow_scorer.score(symbol)

        # 计算加权总分
        total_score = (
            tech_result.total_score * self.COMPREHENSIVE_WEIGHTS['technical'] / 100 +
            fund_result.total_score * self.COMPREHENSIVE_WEIGHTS['fundamental'] / 100 +
            money_result.total_score * self.COMPREHENSIVE_WEIGHTS['money_flow'] / 100
        )

        # 确定买入信号
        buy_signal = self._determine_signal(total_score)

        # 汇总理由和风险因素
        reasons = (
            tech_result.reasons +
            fund_result.reasons +
            money_result.reasons
        )

        risk_factors = (
            tech_result.risk_factors +
            fund_result.risk_factors +
            money_result.risk_factors
        )

        return ComprehensiveScore(
            total_score=int(total_score),
            technical_score=tech_result.total_score,
            fundamental_score=fund_result.total_score,
            money_flow_score=money_result.total_score,
            buy_signal=buy_signal,
            # 技术面细分
            trend_score=tech_result.trend_score,
            bias_score=tech_result.bias_score,
            volume_score=tech_result.volume_score,
            # 基本面细分
            roe_score=fund_result.roe_score,
            growth_score=fund_result.growth_score,
            valuation_score=fund_result.valuation_score,
            quality_score=fund_result.quality_score,
            # 资金面细分
            main_flow_score=money_result.main_flow_score,
            net_flow_score=money_result.net_flow_score,
            margin_score=money_result.margin_score,
            reasons=reasons,
            risk_factors=risk_factors,
        )

    def _determine_signal(self, total_score: float) -> BuySignal:
        """
        根据总分确定买入信号

        Args:
            total_score: 总分

        Returns:
            买入信号
        """
        if total_score >= self.SIGNAL_THRESHOLDS['strong_buy']:
            return BuySignal.STRONG_BUY
        elif total_score >= self.SIGNAL_THRESHOLDS['buy']:
            return BuySignal.BUY
        elif total_score >= self.SIGNAL_THRESHOLDS['hold']:
            return BuySignal.HOLD
        elif total_score >= self.SIGNAL_THRESHOLDS['wait']:
            return BuySignal.WAIT
        else:
            return BuySignal.SELL