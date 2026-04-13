# -*- coding: utf-8 -*-
"""
基本面评分器

基于财务指标评估股票的基本面质量。
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FundamentalScore:
    """基本面评分结果"""
    total_score: int              # 总分 0-100
    roe_score: int                # ROE得分 0-25
    growth_score: int             # 成长性得分 0-25
    valuation_score: int          # 估值得分 0-25
    quality_score: int            # 质量得分 0-25

    reasons: list[str] = field(default_factory=list)      # 买入理由
    risk_factors: list[str] = field(default_factory=list) # 风险因素

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'total_score': self.total_score,
            'roe_score': self.roe_score,
            'growth_score': self.growth_score,
            'valuation_score': self.valuation_score,
            'quality_score': self.quality_score,
            'reasons': self.reasons,
            'risk_factors': self.risk_factors,
        }


class FundamentalScorer:
    """基本面评分器"""

    # 评分阈值
    WEIGHTS = {
        'roe': 25,
        'growth': 25,
        'valuation': 25,
        'quality': 25,
    }

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.fundamentals_dir = self.data_dir / "fundamentals"
        self.financial_dir = self.data_dir / "financial"

    def _load_financial_indicator(self, symbol: str) -> Optional[pd.DataFrame]:
        """加载财务指标数据"""
        try:
            filename = f"indicator_{symbol.replace('.', '_')}.csv"
            filepath = self.fundamentals_dir / filename
            if not filepath.exists():
                return None
            return pd.read_csv(filepath)
        except Exception as e:
            logger.warning(f"加载财务指标失败 {symbol}: {e}")
            return None

    def _load_income_statement(self, symbol: str) -> Optional[pd.DataFrame]:
        """加载利润表"""
        try:
            filename = f"income_{symbol.replace('.', '_')}.csv"
            filepath = self.financial_dir / filename
            if not filepath.exists():
                return None
            return pd.read_csv(filepath)
        except Exception as e:
            logger.warning(f"加载利润表失败 {symbol}: {e}")
            return None

    def score_roe(self, df: pd.DataFrame) -> tuple[int, list[str]]:
        """
        评分 ROE (净资产收益率)

        评分标准:
        - ≥20%: 25分 (优秀)
        - 15-20%: 20分 (良好)
        - 10-15%: 15分 (一般)
        - 5-10%: 10分 (较低)
        - <5%: 5分 (差)
        """
        if df is None or df.empty:
            return 5, ["ROE数据缺失"]

        # 获取最新一期的 ROE
        latest = df.iloc[0]
        roe_col = None

        # 查找 ROE 列
        for col in ['roe', 'ROE', '净资产收益率', 'roeAvg', 'roe_ttm']:
            if col in latest:
                roe_col = col
                break

        if roe_col is None:
            return 5, ["ROE列未找到"]

        roe = pd.to_numeric(latest[roe_col], errors='coerce')

        if pd.isna(roe):
            return 5, ["ROE数据无效"]

        if roe >= 20:
            return 25, ["ROE优秀"]
        elif roe >= 15:
            return 20, ["ROE良好"]
        elif roe >= 10:
            return 15, ["ROE一般"]
        elif roe >= 5:
            return 10, ["ROE较低"]
        else:
            return 5, ["ROE差"]

    def score_growth(self, df_income: pd.DataFrame) -> tuple[int, list[str]]:
        """
        评分成长性

        评分标准:
        - 营收增长率和净利润增长率都 >20%: 25分
        - 都 >10%: 20分
        - 至少一个 >10%: 15分
        - 都 >0: 10分
        - 负增长: 5分
        """
        if df_income is None or df_income.empty or len(df_income) < 2:
            return 5, ["成长性数据不足"]

        try:
            latest = df_income.iloc[0]
            prev = df_income.iloc[1]

            # 查找营收列
            revenue_col = None
            for col in ['operatingRevenue', 'totalOperatingRevenue', '营业总收入', 'revenue']:
                if col in latest:
                    revenue_col = col
                    break

            # 查找净利润列
            profit_col = None
            for col in ['netProfit', 'netProfitToParent', '净利润', '归属母公司所有者的净利润']:
                if col in latest:
                    profit_col = col
                    break

            if revenue_col is None or profit_col is None:
                return 5, ["成长性列未找到"]

            revenue_latest = pd.to_numeric(latest[revenue_col], errors='coerce')
            revenue_prev = pd.to_numeric(prev[revenue_col], errors='coerce')
            profit_latest = pd.to_numeric(latest[profit_col], errors='coerce')
            profit_prev = pd.to_numeric(prev[profit_col], errors='coerce')

            # 计算增长率
            revenue_growth = 0
            profit_growth = 0

            if revenue_prev and revenue_prev > 0:
                revenue_growth = (revenue_latest - revenue_prev) / revenue_prev

            if profit_prev and profit_prev > 0:
                profit_growth = (profit_latest - profit_prev) / profit_prev

            if revenue_growth > 0.2 and profit_growth > 0.2:
                return 25, ["营收和净利润高增长"]
            elif revenue_growth > 0.1 and profit_growth > 0.1:
                return 20, ["营收和净利润良好增长"]
            elif revenue_growth > 0.1 or profit_growth > 0.1:
                return 15, ["中等增长"]
            elif revenue_growth > 0 and profit_growth > 0:
                return 10, ["小幅增长"]
            else:
                return 5, ["负增长"]

        except Exception as e:
            logger.warning(f"成长性评分失败: {e}")
            return 5, ["成长性评分失败"]

    def score_valuation(self, df: pd.DataFrame, current_price: float) -> tuple[int, list[str], list[str]]:
        """
        评分估值水平

        评分标准 (基于PE和PB历史分位数):
        - 低估值 (PE和PB都<30分位数): 25分
        - 中低估值 (30-50分位数): 20分
        - 中等估值 (50-70分位数): 15分
        - 中高估值 (70-90分位数): 10分
        - 高估值 (>90分位数): 5分
        """
        # 这里需要历史估值数据，简化处理
        # 如果没有历史数据，给出中性评分
        reasons = []
        risks = []

        if current_price > 0:
            # 简化：价格越低估值越有利
            # 实际应该使用历史PE/PB分位数
            if current_price < 50:
                reasons.append("价格相对较低")
                return 20, reasons, risks
            elif current_price < 100:
                return 15, reasons, risks
            else:
                risks.append("价格相对较高")
                return 10, reasons, risks

        return 15, reasons, risks

    def score_quality(self, df: pd.DataFrame) -> tuple[int, list[str]]:
        """
        评分质量

        评分标准 (基于毛利率和资产负债率):
        - 毛利率 >50% 且 资产负债率 <40%: 25分
        - 毛利率 >40% 且 资产负债率 <60%: 20分
        - 毛利率 >30% 且 资产负债率 <70%: 15分
        - 其他: 10分
        """
        if df is None or df.empty:
            return 10, ["质量数据不足"]

        try:
            latest = df.iloc[0]

            # 查找毛利率
            gross_margin_col = None
            for col in ['grossProfitMargin', 'grossmargin', '销售毛利率', '销售毛利率(%)']:
                if col in latest:
                    gross_margin_col = col
                    break

            # 查找资产负债率
            debt_ratio_col = None
            for col in ['assetsLiabilityRatio', 'debt_to_assets', '资产负债率', '资产负债率(%)']:
                if col in latest:
                    debt_ratio_col = col
                    break

            gross_margin = pd.to_numeric(latest[gross_margin_col], errors='coerce') if gross_margin_col else None
            debt_ratio = pd.to_numeric(latest[debt_ratio_col], errors='coerce') if debt_ratio_col else None

            if pd.isna(gross_margin) or pd.isna(debt_ratio):
                return 10, ["质量指标缺失"]

            # 评分
            if gross_margin > 50 and debt_ratio < 40:
                return 25, ["高毛率低负债"]
            elif gross_margin > 40 and debt_ratio < 60:
                return 20, ["毛率和负债良好"]
            elif gross_margin > 30 and debt_ratio < 70:
                return 15, ["质量一般"]
            else:
                return 10, ["质量一般"]

        except Exception as e:
            logger.warning(f"质量评分失败: {e}")
            return 10, ["质量评分失败"]

    def score(self, symbol: str, current_price: float = 0) -> FundamentalScore:
        """
        计算综合基本面评分

        Args:
            symbol: 股票代码
            current_price: 当前价格（用于估值评分）

        Returns:
            基本面评分结果
        """
        # 加载数据
        df_indicator = self._load_financial_indicator(symbol)
        df_income = self._load_income_statement(symbol)

        # 各维度评分
        roe_score, roe_reasons = self.score_roe(df_indicator)
        growth_score, growth_reasons = self.score_growth(df_income)
        valuation_score, valuation_reasons, valuation_risks = self.score_valuation(df_indicator, current_price)
        quality_score, quality_reasons = self.score_quality(df_indicator)

        # 总分
        total_score = (
            roe_score + growth_score + valuation_score + quality_score
        )

        # 汇总
        reasons = roe_reasons + growth_reasons + valuation_reasons + quality_reasons
        risk_factors = valuation_risks

        return FundamentalScore(
            total_score=total_score,
            roe_score=roe_score,
            growth_score=growth_score,
            valuation_score=valuation_score,
            quality_score=quality_score,
            reasons=reasons,
            risk_factors=risk_factors,
        )