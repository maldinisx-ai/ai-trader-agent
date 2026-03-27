# -*- coding: utf-8 -*-
"""
资金面评分器

基于资金流向评估股票的资金关注度。
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MoneyFlowScore:
    """资金面评分结果"""
    total_score: int              # 总分 0-100
    main_flow_score: int          # 主力流入得分 0-40
    net_flow_score: int           # 净流入得分 0-30
    margin_score: int             # 融资融券得分 0-30

    reasons: list[str] = field(default_factory=list)      # 买入理由
    risk_factors: list[str] = field(default_factory=list) # 风险因素

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'total_score': self.total_score,
            'main_flow_score': self.main_flow_score,
            'net_flow_score': self.net_flow_score,
            'margin_score': self.margin_score,
            'reasons': self.reasons,
            'risk_factors': self.risk_factors,
        }


class MoneyFlowScorer:
    """资金面评分器"""

    # 评分阈值
    WEIGHTS = {
        'main_flow': 40,
        'net_flow': 30,
        'margin': 30,
    }

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.money_flow_dir = self.data_dir / "money_flow"
        self.margin_dir = self.data_dir / "margin"

    def _load_money_flow(self, symbol: str) -> Optional[pd.DataFrame]:
        """加载资金流向数据"""
        try:
            filename = f"money_flow_{symbol.replace('.', '_')}.csv"
            filepath = self.money_flow_dir / filename
            if not filepath.exists():
                return None
            return pd.read_csv(filepath)
        except Exception as e:
            logger.warning(f"加载资金流向失败 {symbol}: {e}")
            return None

    def _load_margin_detail(self, symbol: str) -> Optional[pd.DataFrame]:
        """加载融资融券详情"""
        try:
            filename = f"margin_detail_{symbol.replace('.', '_')}.csv"
            filepath = self.margin_dir / filename
            if not filepath.exists():
                return None
            return pd.read_csv(filepath)
        except Exception as e:
            logger.warning(f"加载融资融券失败 {symbol}: {e}")
            return None

    def score_main_flow(self, df: pd.DataFrame) -> tuple[int, list[str]]:
        """
        评分主力资金流入

        评分标准:
        - 主力净流入 > 1亿: 40分
        - 主力净流入 > 5000万: 35分
        - 主力净流入 > 1000万: 25分
        - 主力净流入 > 0: 15分
        - 主力净流出: 5分
        """
        if df is None or df.empty:
            return 15, ["资金流向数据缺失"]

        try:
            # 获取最新数据
            latest = df.iloc[0]

            # 查找主力净流入列
            main_net_flow_col = None
            for col in ['mainNetInflow', '主力净流入', 'big_net_in', '超级大单净额']:
                if col in latest:
                    main_net_flow_col = col
                    break

            if main_net_flow_col is None:
                return 15, ["主力资金列未找到"]

            main_net_flow = pd.to_numeric(latest[main_net_flow_col], errors='coerce')

            if pd.isna(main_net_flow):
                return 15, ["主力资金数据无效"]

            if main_net_flow > 100000000:  # > 1亿
                return 40, ["主力大幅流入"]
            elif main_net_flow > 50000000:  # > 5000万
                return 35, ["主力明显流入"]
            elif main_net_flow > 10000000:  # > 1000万
                return 25, ["主力小幅流入"]
            elif main_net_flow > 0:
                return 15, ["主力微幅流入"]
            else:
                return 5, ["主力净流出"]

        except Exception as e:
            logger.warning(f"主力资金评分失败: {e}")
            return 15, ["主力资金评分失败"]

    def score_net_flow(self, df: pd.DataFrame) -> tuple[int, list[str]]:
        """
        评分净流入

        评分标准:
        - 连续3天净流入: 30分
        - 连续2天净流入: 25分
        - 最近1天净流入: 20分
        - 震荡: 15分
        - 净流出: 5分
        """
        if df is None or df.empty or len(df) < 3:
            return 15, ["净流入数据不足"]

        try:
            # 查找净流入列
            net_flow_col = None
            for col in ['netInflow', '净流入', 'net_amount']:
                if col in df.columns:
                    net_flow_col = col
                    break

            if net_flow_col is None:
                return 15, ["净流入列未找到"]

            # 检查最近几天的净流入
            net_flows = df[net_flow_col].head(3).apply(pd.to_numeric, errors='coerce')

            if all(flow > 0 for flow in net_flows):
                return 30, ["连续净流入"]
            elif all(flow > 0 for flow in net_flows.head(2)):
                return 25, ["连续2天净流入"]
            elif net_flows.iloc[0] > 0:
                return 20, ["当日净流入"]
            elif all(flow == 0 for flow in net_flows):
                return 15, ["资金震荡"]
            else:
                return 5, ["资金净流出"]

        except Exception as e:
            logger.warning(f"净流入评分失败: {e}")
            return 15, ["净流入评分失败"]

    def score_margin(self, df: pd.DataFrame) -> tuple[int, list[str]]:
        """
        评分融资融券

        评分标准:
        - 融资余额增长 >10%: 30分
        - 融资余额增长 >5%: 25分
        - 融资余额增长 >0: 20分
        - 融资余额下降: 10分
        - 无融资数据: 15分
        """
        if df is None or df.empty or len(df) < 2:
            return 15, ["融资融券数据不足"]

        try:
            # 查找融资余额列
            margin_col = None
            for col in ['financingBalance', '融资余额', 'fin_sum']:
                if col in df.columns:
                    margin_col = col
                    break

            if margin_col is None:
                return 15, ["融资余额列未找到"]

            # 计算融资余额变化
            margins = df[margin_col].head(2).apply(pd.to_numeric, errors='coerce')
            latest = margins.iloc[0]
            prev = margins.iloc[1]

            if pd.isna(latest) or pd.isna(prev) or prev == 0:
                return 15, ["融资余额数据无效"]

            growth = (latest - prev) / prev

            if growth > 0.10:
                return 30, ["融资余额大增"]
            elif growth > 0.05:
                return 25, ["融资余额增加"]
            elif growth > 0:
                return 20, ["融资余额微增"]
            else:
                return 10, ["融资余额下降"]

        except Exception as e:
            logger.warning(f"融资融券评分失败: {e}")
            return 15, ["融资融券评分失败"]

    def score(self, symbol: str) -> MoneyFlowScore:
        """
        计算综合资金面评分

        Args:
            symbol: 股票代码

        Returns:
            资金面评分结果
        """
        # 加载数据
        df_money_flow = self._load_money_flow(symbol)
        df_margin = self._load_margin_detail(symbol)

        # 各维度评分
        main_flow_score, main_flow_reasons = self.score_main_flow(df_money_flow)
        net_flow_score, net_flow_reasons = self.score_net_flow(df_money_flow)
        margin_score, margin_reasons = self.score_margin(df_margin)

        # 总分
        total_score = (
            main_flow_score + net_flow_score + margin_score
        )

        # 汇总
        reasons = main_flow_reasons + net_flow_reasons + margin_reasons
        risk_factors = []

        # 风险因素
        if main_flow_score < 10:
            risk_factors.append("主力资金流出")
        if net_flow_score < 10:
            risk_factors.append("资金净流出")
        if margin_score < 15:
            risk_factors.append("融资余额下降")

        return MoneyFlowScore(
            total_score=total_score,
            main_flow_score=main_flow_score,
            net_flow_score=net_flow_score,
            margin_score=margin_score,
            reasons=reasons,
            risk_factors=risk_factors,
        )