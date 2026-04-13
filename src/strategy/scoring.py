"""
策略评分引擎 - 根据策略规则计算评分

实现基于技术指标和市场数据的评分逻辑。
"""
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class ScoringResult:
    """评分结果"""
    score: int  # 0-100
    signal: SignalType
    confidence: float  # 0-1
    factors: List[Dict[str, Any]]  # 评分因子
    reasoning: str  # 推理说明


class ScoringRule:
    """评分规则"""

    def __init__(
        self,
        name: str,
        condition: Callable[[Dict[str, Any]], bool],
        score: int,
        reason: str,
        category: str = "general"
    ):
        self.name = name
        self.condition = condition
        self.score = score
        self.reason = reason
        self.category = category

    def evaluate(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        评估规则

        Returns:
            如果条件满足，返回评分因子；否则返回 None
        """
        if self.condition(data):
            return {
                "name": self.name,
                "score": self.score,
                "reason": self.reason,
                "category": self.category,
            }
        return None


class MomentumScoringEngine:
    """动量趋势策略评分引擎"""

    @staticmethod
    def get_rules() -> List[ScoringRule]:
        """获取动量趋势策略的所有评分规则"""
        return [
            # 动量确认规则
            ScoringRule(
                name="strong_momentum",
                condition=lambda d: d.get("n20_gain_pct", 0) > 15,
                score=15,
                reason="20日涨幅超过15%，动量强劲",
                category="momentum"
            ),
            ScoringRule(
                name="strong_momentum_extreme",
                condition=lambda d: d.get("n20_gain_pct", 0) > 25,
                score=20,
                reason="20日涨幅超过25%，动量极强",
                category="momentum"
            ),
            ScoringRule(
                name="moderate_momentum",
                condition=lambda d: 5 < d.get("n20_gain_pct", 0) <= 15,
                score=8,
                reason="20日涨幅5%-15%，动量适中",
                category="momentum"
            ),
            ScoringRule(
                name="weak_momentum",
                condition=lambda d: 0 < d.get("n20_gain_pct", 0) <= 5,
                score=3,
                reason="20日涨幅0%-5%，动量偏弱",
                category="momentum"
            ),
            ScoringRule(
                name="negative_momentum",
                condition=lambda d: d.get("n20_gain_pct", 0) < -5,
                score=-15,
                reason="20日跌幅超过5%，动量转弱",
                category="momentum"
            ),

            # 趋势规则
            ScoringRule(
                name="bullish_alignment",
                condition=lambda d: (
                    d.get("ma5", 0) > d.get("ma10", 0) > d.get("ma20", 0)
                ),
                score=15,
                reason="MA5 > MA10 > MA20 多头排列",
                category="trend"
            ),
            ScoringRule(
                name="ma20_trending_up",
                condition=lambda d: d.get("ma20_slope", 0) > 0,
                score=8,
                reason="MA20 斜率向上，趋势良好",
                category="trend"
            ),
            ScoringRule(
                name="price_above_ma5",
                condition=lambda d: d.get("close", 0) > d.get("ma5", 0),
                score=5,
                reason="价格站上 MA5",
                category="trend"
            ),
            ScoringRule(
                name="price_above_ma20",
                condition=lambda d: d.get("close", 0) > d.get("ma20", 0),
                score=5,
                reason="价格站上 MA20",
                category="trend"
            ),
            ScoringRule(
                name="bearish_alignment",
                condition=lambda d: (
                    d.get("ma5", 0) < d.get("ma10", 0) < d.get("ma20", 0)
                ),
                score=-20,
                reason="MA5 < MA10 < MA20 空头排列",
                category="trend"
            ),
            ScoringRule(
                name="price_below_ma20",
                condition=lambda d: d.get("close", 0) < d.get("ma20", 0),
                score=-10,
                reason="价格跌破 MA20",
                category="trend"
            ),

            # 资金流向规则
            ScoringRule(
                name="strong_inflow",
                condition=lambda d: d.get("main_net_inflow_ratio", 0) > 20,
                score=12,
                reason="主力净流入占比超过20%",
                category="money_flow"
            ),
            ScoringRule(
                name="moderate_inflow",
                condition=lambda d: 5 < d.get("main_net_inflow_ratio", 0) <= 20,
                score=7,
                reason="主力净流入占比5%-20%",
                category="money_flow"
            ),
            ScoringRule(
                name="continuous_inflow_3d",
                condition=lambda d: d.get("continuous_inflow_days", 0) >= 3,
                score=8,
                reason="主力连续3日净流入",
                category="money_flow"
            ),
            ScoringRule(
                name="strong_outflow",
                condition=lambda d: d.get("main_net_inflow_ratio", 0) < -15,
                score=-15,
                reason="主力大幅净流出",
                category="money_flow"
            ),

            # 量价关系规则
            ScoringRule(
                name="volume_breakout",
                condition=lambda d: d.get("volume_ratio", 1) > 2.0,
                score=10,
                reason="放量突破（量比>2）",
                category="volume_price"
            ),
            ScoringRule(
                name="moderate_volume_increase",
                condition=lambda d: 1.5 < d.get("volume_ratio", 1) <= 2.0,
                score=5,
                reason="适度放量（量比1.5-2）",
                category="volume_price"
            ),
            ScoringRule(
                name="shrink_pullback",
                condition=lambda d: (
                    0.5 < d.get("volume_ratio", 1) < 0.8 and
                    d.get("close", 0) > d.get("ma10", 0)
                ),
                score=10,
                reason="缩量回踩MA10",
                category="volume_price"
            ),
            ScoringRule(
                name="high_volume_stagnation",
                condition=lambda d: (
                    d.get("volume_ratio", 1) > 1.5 and
                    d.get("change_pct", 0) < 1
                ),
                score=-12,
                reason="放量滞涨",
                category="volume_price"
            ),

            # 价格位置规则
            ScoringRule(
                name="pullback_to_ma5",
                condition=lambda d: (
                    0 < d.get("close", 0) - d.get("ma5", 0) < d.get("ma5", 0) * 0.02
                ),
                score=12,
                reason="缩量回踩MA5附近",
                category="position"
            ),
            ScoringRule(
                name="pullback_to_ma10",
                condition=lambda d: (
                    0 < d.get("close", 0) - d.get("ma10", 0) < d.get("ma10", 0) * 0.03
                ),
                score=10,
                reason="回踩MA10附近",
                category="position"
            ),
            ScoringRule(
                name="far_from_ma5",
                condition=lambda d: (
                    d.get("close", 0) - d.get("ma5", 0) > d.get("ma5", 0) * 0.05
                ),
                score=-8,
                reason="价格远离MA5超过5%，追高风险",
                category="position"
            ),
            ScoringRule(
                name="high_bias_warning",
                condition=lambda d: abs(d.get("bias_ma5", 0)) > 5,
                score=-10,
                reason="乖离率超过5%，不追高",
                category="position"
            ),
        ]

    @classmethod
    def calculate(cls, market_data: Dict[str, Any], financial_data: Optional[Dict] = None) -> ScoringResult:
        """
        计算动量趋势策略评分

        Args:
            market_data: 市场数据
            financial_data: 财务数据（可选）

        Returns:
            评分结果
        """
        factors = []
        total_score = 50  # 基础分数

        # 评估所有规则
        for rule in cls.get_rules():
            factor = rule.evaluate(market_data)
            if factor:
                factors.append(factor)
                total_score += factor["score"]

        # 限制分数范围
        total_score = max(0, min(100, total_score))

        # 确定信号
        if total_score >= 70:
            signal = SignalType.BUY
            confidence = min(1.0, (total_score - 60) / 40)
        elif total_score <= 30:
            signal = SignalType.SELL
            confidence = min(1.0, (40 - total_score) / 40)
        else:
            signal = SignalType.HOLD
            confidence = 0.5

        # 生成推理文本
        reasoning = cls._generate_reasoning(factors, total_score)

        return ScoringResult(
            score=total_score,
            signal=signal,
            confidence=confidence,
            factors=factors,
            reasoning=reasoning
        )

    @classmethod
    def _generate_reasoning(cls, factors: List[Dict], score: int) -> str:
        """生成推理文本"""
        lines = ["**动量趋势分析**", ""]

        # 按类别分组
        by_category = {}
        for f in factors:
            cat = f.get("category", "general")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(f)

        # 输出各类别的分析
        category_names = {
            "momentum": "[动量分析]",
            "trend": "[趋势分析]",
            "money_flow": "[资金流向]",
            "volume_price": "[量价关系]",
            "position": "[价格位置]"
        }

        for cat, cat_factors in by_category.items():
            lines.append(f"{category_names.get(cat, cat)}:")
            for f in cat_factors:
                score_str = f"+{f['score']}" if f['score'] > 0 else f['score']
                lines.append(f"  - {f['reason']} ({score_str})")
            lines.append("")

        # 总结
        lines.append(f"**综合评分: {score}/100**")

        if score >= 70:
            lines.append("[OK] 建议买入 - 动量强劲，趋势向上")
        elif score <= 30:
            lines.append("[X] 建议卖出 - 动量转弱，注意风险")
        else:
            lines.append("[WAIT] 观望 - 等待更好的入场时机")

        return "\n".join(lines)


class ValueReversalScoringEngine:
    """价值反转策略评分引擎"""

    @staticmethod
    def get_rules() -> List[ScoringRule]:
        """获取价值反转策略的所有评分规则"""
        return [
            # 估值规则
            ScoringRule(
                name="low_pe",
                condition=lambda d: d.get("pe", 100) < 10,
                score=15,
                reason="PE < 10，估值极低",
                category="valuation"
            ),
            ScoringRule(
                name="moderate_low_pe",
                condition=lambda d: 10 <= d.get("pe", 100) < 15,
                score=10,
                reason="PE 在 10-15，估值较低",
                category="valuation"
            ),
            ScoringRule(
                name="high_pe",
                condition=lambda d: d.get("pe", 0) > 50,
                score=-10,
                reason="PE > 50，估值偏高",
                category="valuation"
            ),

            ScoringRule(
                name="low_pb",
                condition=lambda d: d.get("pb", 10) < 1.0,
                score=12,
                reason="PB < 1，破净资产",
                category="valuation"
            ),
            ScoringRule(
                name="moderate_low_pb",
                condition=lambda d: 1.0 <= d.get("pb", 10) < 1.5,
                score=8,
                reason="PB 在 1-1.5，估值合理",
                category="valuation"
            ),

            # 盈利能力规则
            ScoringRule(
                name="high_roe",
                condition=lambda d: d.get("roe", 0) > 15,
                score=12,
                reason="ROE > 15%，盈利能力强",
                category="profitability"
            ),
            ScoringRule(
                name="moderate_roe",
                condition=lambda d: 10 < d.get("roe", 0) <= 15,
                score=8,
                reason="ROE 在 10-15%，盈利能力良好",
                category="profitability"
            ),
            ScoringRule(
                name="low_roe",
                condition=lambda d: d.get("roe", 0) < 8,
                score=-10,
                reason="ROE < 8%，盈利能力偏弱",
                category="profitability"
            ),

            # 股息规则
            ScoringRule(
                name="high_dividend",
                condition=lambda d: d.get("dividend_yield", 0) > 5,
                score=10,
                reason="股息率 > 5%，高股息",
                category="dividend"
            ),
            ScoringRule(
                name="moderate_dividend",
                condition=lambda d: 3 < d.get("dividend_yield", 0) <= 5,
                score=6,
                reason="股息率 3-5%，股息适中",
                category="dividend"
            ),

            # 反转信号规则
            ScoringRule(
                name="deep_drop",
                condition=lambda d: d.get("from_high_drop_pct", 0) < -40,
                score=15,
                reason="距高点跌幅超过40%，深度超跌",
                category="reversal"
            ),
            ScoringRule(
                name="moderate_drop",
                condition=lambda d: -40 <= d.get("from_high_drop_pct", 0) < -25,
                score=10,
                reason="距高点跌幅25-40%，中度超跌",
                category="reversal"
            ),
            ScoringRule(
                name="oversold_rsi",
                condition=lambda d: d.get("rsi", 50) < 30,
                score=8,
                reason="RSI < 30，超卖区域",
                category="reversal"
            ),

            # 风险规则
            ScoringRule(
                name="high_debt",
                condition=lambda d: d.get("debt_ratio", 0) > 70,
                score=-12,
                reason="负债率超过70%，财务风险较高",
                category="risk"
            ),
            ScoringRule(
                name="moderate_high_debt",
                condition=lambda d: 60 < d.get("debt_ratio", 0) <= 70,
                score=-6,
                reason="负债率60-70%，关注财务风险",
                category="risk"
            ),
        ]

    @classmethod
    def calculate(cls, market_data: Dict[str, Any], financial_data: Optional[Dict] = None) -> ScoringResult:
        """计算价值反转策略评分"""
        if not financial_data:
            return ScoringResult(
                score=50,
                signal=SignalType.HOLD,
                confidence=0.3,
                factors=[],
                reasoning="缺少财务数据，无法进行价值分析"
            )

        factors = []
        total_score = 50

        # 合并市场数据和财务数据
        combined_data = {**market_data, **financial_data}

        # 评估所有规则
        for rule in cls.get_rules():
            factor = rule.evaluate(combined_data)
            if factor:
                factors.append(factor)
                total_score += factor["score"]

        # 限制分数范围
        total_score = max(0, min(100, total_score))

        # 确定信号
        if total_score >= 70:
            signal = SignalType.BUY
            confidence = min(1.0, (total_score - 60) / 40)
        elif total_score <= 30:
            signal = SignalType.SELL
            confidence = min(1.0, (40 - total_score) / 40)
        else:
            signal = SignalType.HOLD
            confidence = 0.5

        # 生成推理文本
        reasoning = cls._generate_reasoning(factors, total_score)

        return ScoringResult(
            score=total_score,
            signal=signal,
            confidence=confidence,
            factors=factors,
            reasoning=reasoning
        )

    @classmethod
    def _generate_reasoning(cls, factors: List[Dict], score: int) -> str:
        """生成推理文本"""
        lines = ["**价值反转分析**", ""]

        # 按类别分组
        by_category = {}
        for f in factors:
            cat = f.get("category", "general")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(f)

        # 输出各类别的分析
        category_names = {
            "valuation": "[估值分析]",
            "profitability": "[盈利能力]",
            "dividend": "[股息分析]",
            "reversal": "[反转信号]",
            "risk": "[风险提示]"
        }

        for cat, cat_factors in by_category.items():
            lines.append(f"{category_names.get(cat, cat)}:")
            for f in cat_factors:
                score_str = f"+{f['score']}" if f['score'] > 0 else f['score']
                lines.append(f"  - {f['reason']} ({score_str})")
            lines.append("")

        # 总结
        lines.append(f"**综合评分: {score}/100**")

        if score >= 70:
            lines.append("[OK] 建议买入 - 价值被低估，反转机会")
        elif score <= 30:
            lines.append("[X] 建议卖出 - 估值偏高或基本面恶化")
        else:
            lines.append("[WAIT] 观望 - 等待更好的左侧布局时机")

        return "\n".join(lines)


class BreakoutVolumeScoringEngine:
    """放量突破策略评分引擎"""

    @staticmethod
    def get_rules() -> List[ScoringRule]:
        """获取放量突破策略的所有评分规则"""
        return [
            # 突破确认规则
            ScoringRule(
                name="strong_breakout",
                condition=lambda d: d.get("volume_ratio", 1) > 2.5,
                score=18,
                reason="强势放量突破（量比>2.5）",
                category="breakout"
            ),
            ScoringRule(
                name="moderate_breakout",
                condition=lambda d: 1.5 < d.get("volume_ratio", 1) <= 2.5,
                score=12,
                reason="适度放量突破（量比1.5-2.5）",
                category="breakout"
            ),
            ScoringRule(
                name="weak_volume",
                condition=lambda d: d.get("volume_ratio", 1) < 1.2,
                score=-10,
                reason="突破但成交量不足",
                category="breakout"
            ),

            # 位置规则
            ScoringRule(
                name="break_resistance",
                condition=lambda d: d.get("breakout_ratio", 0) > 0.03,
                score=10,
                reason="有效突破阻力位3%以上",
                category="position"
            ),
            ScoringRule(
                name="close_high",
                condition=lambda d: (
                    d.get("close", 0) / d.get("high", 1) > 0.98
                ),
                score=8,
                reason="收盘价接近当日最高价",
                category="position"
            ),

            # 横盘时长规则
            ScoringRule(
                name="long_consolidation",
                condition=lambda d: d.get("consolidation_days", 0) >= 30,
                score=10,
                reason="横盘整理超过30天",
                category="pattern"
            ),
            ScoringRule(
                name="moderate_consolidation",
                condition=lambda d: 15 <= d.get("consolidation_days", 0) < 30,
                score=6,
                reason="横盘整理15-30天",
                category="pattern"
            ),

            # 假突破识别
            ScoringRule(
                name="fake_breakout_risk",
                condition=lambda d: (
                    d.get("volume_ratio", 1) > 1.5 and
                    d.get("close_near_low", False)
                ),
                score=-20,
                reason="放量但收盘接近最低价，假突破风险",
                category="risk"
            ),
            ScoringRule(
                name="pullback_risk",
                condition=lambda d: d.get("next_day_drop", 0) < -0.02,
                score=-15,
                reason="次日大幅回落，突破失败",
                category="risk"
            ),
        ]

    @classmethod
    def calculate(cls, market_data: Dict[str, Any], financial_data: Optional[Dict] = None) -> ScoringResult:
        """计算放量突破策略评分"""
        factors = []
        total_score = 50

        # 评估所有规则
        for rule in cls.get_rules():
            factor = rule.evaluate(market_data)
            if factor:
                factors.append(factor)
                total_score += factor["score"]

        # 限制分数范围
        total_score = max(0, min(100, total_score))

        # 确定信号
        if total_score >= 70:
            signal = SignalType.BUY
            confidence = min(1.0, (total_score - 60) / 40)
        elif total_score <= 30:
            signal = SignalType.SELL
            confidence = min(1.0, (40 - total_score) / 40)
        else:
            signal = SignalType.HOLD
            confidence = 0.5

        # 生成推理文本
        reasoning = cls._generate_reasoning(factors, total_score)

        return ScoringResult(
            score=total_score,
            signal=signal,
            confidence=confidence,
            factors=factors,
            reasoning=reasoning
        )

    @classmethod
    def _generate_reasoning(cls, factors: List[Dict], score: int) -> str:
        """生成推理文本"""
        lines = ["**放量突破分析**", ""]

        # 按类别分组
        by_category = {}
        for f in factors:
            cat = f.get("category", "general")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(f)

        # 输出各类别的分析
        category_names = {
            "breakout": "[突破确认]",
            "position": "[位置分析]",
            "pattern": "[形态分析]",
            "risk": "[风险提示]"
        }

        for cat, cat_factors in by_category.items():
            lines.append(f"{category_names.get(cat, cat)}:")
            for f in cat_factors:
                score_str = f"+{f['score']}" if f['score'] > 0 else f['score']
                lines.append(f"  - {f['reason']} ({score_str})")
            lines.append("")

        # 总结
        lines.append(f"**综合评分: {score}/100**")

        if score >= 70:
            lines.append("[OK] 建议买入 - 真实放量突破")
        elif score <= 30:
            lines.append("[X] 建议卖出 - 假突破或突破失败")
        else:
            lines.append("[WAIT] 观望 - 等待确认有效突破")

        return "\n".join(lines)


# 策略引擎映射
STRATEGY_ENGINES = {
    "momentum_trend": MomentumScoringEngine,
    "value_reversal": ValueReversalScoringEngine,
    "breakout_vol": BreakoutVolumeScoringEngine,
}


def get_strategy_engine(strategy_name: str):
    """获取策略评分引擎"""
    return STRATEGY_ENGINES.get(strategy_name)
