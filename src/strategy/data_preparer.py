"""
市场数据准备器 - 将原始数据转换为评分引擎需要的格式
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)


class MarketDataPreparer:
    """市场数据准备器"""

    # 列名映射：支持不同数据源的列名
    COLUMN_MAPPING = {
        "date": ["date", "trade_date", "timestamp", "datetime"],
        "open": ["open", "open_price", "o"],
        "high": ["high", "high_price", "h"],
        "low": ["low", "low_price", "l"],
        "close": ["close", "close_price", "c"],
        "volume": ["volume", "vol", "v", "amount"],
    }

    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化列名，将不同数据源的列名映射到统一格式

        Args:
            df: 原始 DataFrame

        Returns:
            列名标准化后的 DataFrame
        """
        df_copy = df.copy()
        reverse_mapping = {}

        # 构建反向映射：从实际列名到标准列名
        for standard_name, possible_names in MarketDataPreparer.COLUMN_MAPPING.items():
            for actual_name in possible_names:
                if actual_name in df_copy.columns:
                    reverse_mapping[actual_name] = standard_name
                    break

        # 重命名列
        df_copy = df_copy.rename(columns=reverse_mapping)

        # 检查必需列是否存在
        required = ["date", "open", "high", "low", "close", "volume"]
        missing = [col for col in required if col not in df_copy.columns]
        if missing:
            raise ValueError(f"缺少必需列: {missing}。可用列: {list(df_copy.columns)}")

        return df_copy

    @staticmethod
    def prepare_from_df(df: pd.DataFrame) -> Dict[str, Any]:
        """
        从 DataFrame 准备市场数据

        Args:
            df: K线数据 DataFrame，支持多种列名格式：
                - 标准: date, open, high, low, close, volume
                - finshare: trade_date, open_price, high_price, low_price, close_price, volume

        Returns:
            准备好的市场数据字典
        """
        if df.empty:
            logger.warning("空数据")
            return {}

        # 标准化列名
        df = MarketDataPreparer._normalize_columns(df)

        # 确保按日期排序
        df = df.sort_values('date').reset_index(drop=True)

        # 提取价格序列
        closes = df['close'].tolist()
        highs = df['high'].tolist()
        lows = df['low'].tolist()
        volumes = df['volume'].tolist()

        # 计算移动平均线
        ma5 = MarketDataPreparer._calculate_sma(closes, 5)
        ma10 = MarketDataPreparer._calculate_sma(closes, 10)
        ma20 = MarketDataPreparer._calculate_sma(closes, 20)
        ma60 = MarketDataPreparer._calculate_sma(closes, 60)

        # 计算MA斜率
        ma20_slope = MarketDataPreparer._calculate_slope(ma20)

        # 计算涨跌幅
        change_pct = ((closes[-1] - closes[-2]) / closes[-2] * 100) if len(closes) >= 2 else 0

        # 计算20日涨幅
        n20_gain_pct = ((closes[-1] - closes[-21]) / closes[-21] * 100) if len(closes) >= 21 else 0

        # 计算乖离率
        bias_ma5 = ((closes[-1] - ma5[-1]) / ma5[-1] * 100) if ma5[-1] else 0

        # 计算量比
        volume_ratio = MarketDataPreparer._calculate_volume_ratio(volumes, 5)

        # 距高点跌幅
        high_20 = max(closes[-20:]) if len(closes) >= 20 else closes[0]
        from_high_drop_pct = ((closes[-1] - high_20) / high_20 * 100)

        # 构建数据字典
        data = {
            # 基本信息
            "close": closes[-1],
            "high": highs[-1],
            "low": lows[-1],
            "volume": volumes[-1],
            "change_pct": change_pct,

            # 移动平均线
            "ma5": ma5[-1] if ma5[-1] else 0,
            "ma10": ma10[-1] if ma10[-1] else 0,
            "ma20": ma20[-1] if ma20[-1] else 0,
            "ma60": ma60[-1] if ma60[-1] else 0,
            "ma20_slope": ma20_slope,

            # 动量指标
            "n20_gain_pct": n20_gain_pct,
            "from_high_drop_pct": from_high_drop_pct,

            # 位置指标
            "bias_ma5": bias_ma5,

            # 成交量
            "volume_ratio": volume_ratio,

            # 趋势判断
            "bullish_alignment": ma5[-1] > ma10[-1] > ma20[-1] if all([ma5[-1], ma10[-1], ma20[-1]]) else False,
            "bearish_alignment": ma5[-1] < ma10[-1] < ma20[-1] if all([ma5[-1], ma10[-1], ma20[-1]]) else False,

            # 价格位置
            "above_ma5": closes[-1] > ma5[-1] if ma5[-1] else False,
            "above_ma20": closes[-1] > ma20[-1] if ma20[-1] else False,

            # 收盘位置
            "close_near_high": closes[-1] / highs[-1] > 0.98 if highs[-1] else False,
            "close_near_low": closes[-1] / lows[-1] < 1.02 if lows[-1] else False,
        }

        return data

    @staticmethod
    def prepare_from_quotes(quotes: List[Dict]) -> Dict[str, Any]:
        """
        从行情数据列表准备市场数据

        Args:
            quotes: 行情数据列表

        Returns:
            准备好的市场数据字典
        """
        df = pd.DataFrame(quotes)
        return MarketDataPreparer.prepare_from_df(df)

    @staticmethod
    def prepare_with_money_flow(
        base_data: Dict[str, Any],
        money_flow: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        添加资金流向数据

        Args:
            base_data: 基础市场数据
            money_flow: 资金流向数据

        Returns:
            合并后的数据
        """
        data = base_data.copy()

        if money_flow:
            data.update({
                "main_net_inflow": money_flow.get("net_inflow_main", 0),
                "main_net_inflow_ratio": money_flow.get("net_inflow_main_ratio", 0),
                "super_net_inflow": money_flow.get("net_inflow_super", 0),
                "continuous_inflow_days": money_flow.get("continuous_inflow_days", 0),
            })

        return data

    @staticmethod
    def prepare_with_indicators(
        base_data: Dict[str, Any],
        indicators: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        添加技术指标数据

        Args:
            base_data: 基础市场数据
            indicators: 技术指标数据

        Returns:
            合并后的数据
        """
        data = base_data.copy()

        if indicators:
            data.update({
                "rsi": indicators.get("rsi", 50),
                "macd": indicators.get("macd", 0),
                "macd_signal": indicators.get("macd_signal", 0),
                "macd_hist": indicators.get("macd_hist", 0),
                "atr": indicators.get("atr", 0),
            })

        return data

    @staticmethod
    def _calculate_sma(prices: List[float], period: int) -> List[float]:
        """计算简单移动平均"""
        if len(prices) < period:
            return [0.0] * len(prices)

        result = []
        for i in range(len(prices)):
            if i < period - 1:
                result.append(0.0)
            else:
                avg = sum(prices[i - period + 1:i + 1]) / period
                result.append(avg)

        return result

    @staticmethod
    def _calculate_slope(values: List[float], period: int = 5) -> float:
        """计算斜率"""
        if len(values) < period + 1:
            return 0.0

        recent = values[-period:]
        if recent[0] == 0:
            return 0.0

        # 简单线性回归斜率
        n = len(recent)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(recent) / n

        numerator = sum((x[i] - x_mean) * (recent[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        return numerator / denominator

    @staticmethod
    def _calculate_volume_ratio(volumes: List[int], period: int = 5) -> float:
        """计算量比"""
        if len(volumes) < period:
            return 1.0

        recent = volumes[-period:]
        avg_volume = sum(recent) / period

        if avg_volume == 0:
            return 1.0

        return volumes[-1] / avg_volume


class FinancialDataPreparer:
    """财务数据准备器"""

    @staticmethod
    def prepare_from_financials(df: pd.DataFrame) -> Dict[str, Any]:
        """
        从财务数据 DataFrame 准备财务指标

        Args:
            df: 财务数据 DataFrame，支持多种格式：
                - 财务指标表: pe, pb, ps, roe, roa, dividend_yield, debt_ratio, current_ratio, revenue_growth, profit_growth
                - finshare 指标表: eps, roe, gross_margin, netprofit_margin, current_ratio, quick_ratio, debt_to_assets

        Returns:
            准备好的财务数据字典
        """
        if df.empty:
            return {}

        # 排序数据以获取最新一期
        df_sorted = df.copy()
        if "report_date" in df_sorted.columns:
            # finshare 格式：按报告日期排序
            df_sorted = df_sorted.sort_values("report_date").reset_index(drop=True)
        elif "date" in df_sorted.columns:
            # 标准格式：按日期排序
            df_sorted = df_sorted.sort_values("date").reset_index(drop=True)

        # 获取最新一期数据（排序后的最后一行）
        latest = df_sorted.iloc[-1]

        # 检查是否是 finshare 格式
        if "fs_code" in df.columns:
            return FinancialDataPreparer._prepare_finshare_format(latest, df)
        else:
            return FinancialDataPreparer._prepare_standard_format(latest)

    @staticmethod
    def _prepare_standard_format(latest: pd.Series) -> Dict[str, Any]:
        """处理标准格式的财务数据"""
        return {
            "pe": latest.get("pe", 50) if pd.notna(latest.get("pe")) else 50,
            "pb": latest.get("pb", 3) if pd.notna(latest.get("pb")) else 3,
            "ps": latest.get("ps", 10) if pd.notna(latest.get("ps")) else 10,
            "roe": latest.get("roe", 0) if pd.notna(latest.get("roe")) else 0,
            "roa": latest.get("roa", 0) if pd.notna(latest.get("roa")) else 0,
            "dividend_yield": latest.get("dividend_yield", 0) if pd.notna(latest.get("dividend_yield")) else 0,
            "debt_ratio": latest.get("debt_ratio", 50) if pd.notna(latest.get("debt_ratio")) else 50,
            "current_ratio": latest.get("current_ratio", 1.5) if pd.notna(latest.get("current_ratio")) else 1.5,
            "revenue_growth": latest.get("revenue_growth", 0) if pd.notna(latest.get("revenue_growth")) else 0,
            "profit_growth": latest.get("profit_growth", 0) if pd.notna(latest.get("profit_growth")) else 0,
        }

    @staticmethod
    def _prepare_finshare_format(latest: pd.Series, df: pd.DataFrame) -> Dict[str, Any]:
        """处理 finshare 格式的财务数据"""
        return {
            "pe": 50,  # finshare 财务指标表不包含 PE，需要从其他数据计算
            "pb": 3,   # finshare 财务指标表不包含 PB
            "ps": 10,  # finshare 财务指标表不包含 PS
            "roe": latest.get("roe", 0) if pd.notna(latest.get("roe")) else 0,
            "roa": latest.get("roa", 0) if pd.notna(latest.get("roa")) else 0,
            "dividend_yield": 0,  # 需要从分红数据获取
            "debt_ratio": latest.get("debt_to_assets", 50) if pd.notna(latest.get("debt_to_assets")) else 50,
            "current_ratio": latest.get("current_ratio", 1.5) if pd.notna(latest.get("current_ratio")) else 1.5,
            "revenue_growth": latest.get("revenue_yoy", 0) if pd.notna(latest.get("revenue_yoy")) else 0,
            "profit_growth": latest.get("net_profit_yoy", 0) if pd.notna(latest.get("net_profit_yoy")) else 0,
        }
        """
        从财务数据 DataFrame 准备财务指标

        Args:
            df: 财务数据 DataFrame

        Returns:
            准备好的财务数据字典
        """
        if df.empty:
            return {}

        # 获取最新一期数据
        latest = df.iloc[-1]

        return {
            "pe": latest.get("pe", 50) if pd.notna(latest.get("pe")) else 50,
            "pb": latest.get("pb", 3) if pd.notna(latest.get("pb")) else 3,
            "ps": latest.get("ps", 10) if pd.notna(latest.get("ps")) else 10,
            "roe": latest.get("roe", 0) if pd.notna(latest.get("roe")) else 0,
            "roa": latest.get("roa", 0) if pd.notna(latest.get("roa")) else 0,
            "dividend_yield": latest.get("dividend_yield", 0) if pd.notna(latest.get("dividend_yield")) else 0,
            "debt_ratio": latest.get("debt_ratio", 50) if pd.notna(latest.get("debt_ratio")) else 50,
            "current_ratio": latest.get("current_ratio", 1.5) if pd.notna(latest.get("current_ratio")) else 1.5,
            "revenue_growth": latest.get("revenue_growth", 0) if pd.notna(latest.get("revenue_growth")) else 0,
            "profit_growth": latest.get("profit_growth", 0) if pd.notna(latest.get("profit_growth")) else 0,
        }

    @staticmethod
    def prepare_from_multiple(
        income_df: pd.DataFrame = None,
        balance_df: pd.DataFrame = None,
        indicator_df: pd.DataFrame = None,
        current_price: float = None
    ) -> Dict[str, Any]:
        """
        从多个数据源准备完整的财务数据

        Args:
            income_df: 利润表数据
            balance_df: 资产负债表数据
            indicator_df: 财务指标数据
            current_price: 当前股价（用于计算PE、PB）

        Returns:
            准备好的财务数据字典
        """
        data = {
            "pe": 50,
            "pb": 3,
            "ps": 10,
            "roe": 0,
            "roa": 0,
            "dividend_yield": 0,
            "debt_ratio": 50,
            "current_ratio": 1.5,
            "revenue_growth": 0,
            "profit_growth": 0,
        }

        # 从财务指标表获取数据
        if indicator_df is not None and not indicator_df.empty:
            # 排序获取最新数据
            indicator_sorted = indicator_df.sort_values("report_date").reset_index(drop=True) if "report_date" in indicator_df.columns else indicator_df
            latest = indicator_sorted.iloc[-1]
            data.update({
                "roe": latest.get("roe", data["roe"]) if pd.notna(latest.get("roe")) else data["roe"],
                "debt_ratio": latest.get("debt_to_assets", data["debt_ratio"]) if pd.notna(latest.get("debt_to_assets")) else data["debt_ratio"],
                "current_ratio": latest.get("current_ratio", data["current_ratio"]) if pd.notna(latest.get("current_ratio")) else data["current_ratio"],
            })

        # 从利润表获取数据
        if income_df is not None and not income_df.empty:
            # 排序获取最新数据
            income_sorted = income_df.sort_values("report_date").reset_index(drop=True) if "report_date" in income_df.columns else income_df
            latest = income_sorted.iloc[-1]
            data.update({
                "revenue_growth": latest.get("revenue_yoy", data["revenue_growth"]) if pd.notna(latest.get("revenue_yoy")) else data["revenue_growth"],
                "profit_growth": latest.get("net_profit_yoy", data["profit_growth"]) if pd.notna(latest.get("net_profit_yoy")) else data["profit_growth"],
            })

            # 计算 PE（如果有股价和EPS）
            if current_price and "eps" in latest:
                eps = latest.get("eps", 0)
                if eps and eps > 0:
                    data["pe"] = current_price / eps

        # 从资产负债表获取数据
        if balance_df is not None and not balance_df.empty:
            # 排序获取最新数据
            balance_sorted = balance_df.sort_values("report_date").reset_index(drop=True) if "report_date" in balance_df.columns else balance_df
            latest = balance_sorted.iloc[-1]
            total_equity = latest.get("total_equity", 0)
            total_assets = latest.get("total_assets", 0)
            total_liab = latest.get("total_liab", 0)

            # 计算负债率
            if total_assets and total_assets > 0:
                data["debt_ratio"] = (total_liab / total_assets) * 100

            # 计算流动比率
            current_assets = latest.get("current_assets", 0)
            current_liab = latest.get("current_liab", 0)
            if current_liab and current_liab > 0:
                data["current_ratio"] = current_assets / current_liab

            # 计算 PB（如果有股价和每股净资产）
            if current_price and total_equity and total_equity > 0:
                # 假设股本为总股数（这里简化处理，实际需要股本数据）
                # pb = 股价 / 每股净资产 = 股价 / (总权益 / 总股本)
                # 这里我们无法准确计算，使用默认值
                pass

        return data

    @staticmethod
    def prepare_from_dict(financial_data: Dict) -> Dict[str, Any]:
        """
        从字典准备财务数据

        Args:
            financial_data: 财务数据字典

        Returns:
            准备好的财务数据字典
        """
        return {
            "pe": financial_data.get("pe", 50),
            "pb": financial_data.get("pb", 3),
            "ps": financial_data.get("ps", 10),
            "roe": financial_data.get("roe", 0),
            "roa": financial_data.get("roa", 0),
            "dividend_yield": financial_data.get("dividend_yield", 0),
            "debt_ratio": financial_data.get("debt_ratio", 50),
            "current_ratio": financial_data.get("current_ratio", 1.5),
            "revenue_growth": financial_data.get("revenue_growth", 0),
            "profit_growth": financial_data.get("profit_growth", 0),
        }
