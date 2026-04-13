# -*- coding: utf-8 -*-
"""
技术指标计算

实现常用技术分析指标：MA、MACD、RSI、BOLL等。
"""

import logging
from typing import List, Optional, Tuple
from datetime import datetime
import numpy as np

from core.schemas import QuoteData


logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """技术指标计算器"""

    @staticmethod
    def sma(prices: List[float], period: int) -> List[Optional[float]]:
        """
        简单移动平均线 (SMA)

        Args:
            prices: 价格序列
            period: 周期

        Returns:
            SMA 值序列（前面 period-1 个值为 None）
        """
        if len(prices) < period:
            return [None] * len(prices)

        result = []
        for i in range(len(prices)):
            if i < period - 1:
                result.append(None)
            else:
                avg = sum(prices[i - period + 1:i + 1]) / period
                result.append(avg)

        return result

    @staticmethod
    def ema(prices: List[float], period: int) -> List[Optional[float]]:
        """
        指数移动平均线 (EMA)

        Args:
            prices: 价格序列
            period: 周期

        Returns:
            EMA 值序列
        """
        if len(prices) < period:
            return [None] * len(prices)

        multiplier = 2 / (period + 1)
        result = [None] * period

        # 第一个 EMA 使用 SMA
        ema_value = sum(prices[:period]) / period
        result.append(ema_value)

        # 后续使用 EMA 公式
        for i in range(period, len(prices)):
            ema_value = (prices[i] - ema_value) * multiplier + ema_value
            result.append(ema_value)

        return result

    @staticmethod
    def macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
        """
        MACD 指标

        Args:
            prices: 价格序列
            fast: 快线周期 (默认12)
            slow: 慢线周期 (默认26)
            signal: 信号线周期 (默认9)

        Returns:
            (MACD线, Signal线, Histogram柱)
        """
        ema_fast = TechnicalIndicators.ema(prices, fast)
        ema_slow = TechnicalIndicators.ema(prices, slow)

        # MACD 线 = 快线 - 慢线
        macd_line = []
        for i in range(len(prices)):
            if ema_fast[i] is None or ema_slow[i] is None:
                macd_line.append(None)
            else:
                macd_line.append(ema_fast[i] - ema_slow[i])

        # Signal 线是 MACD 线的 EMA
        valid_values = [x for x in macd_line if x is not None]
        signal_line_raw = TechnicalIndicators.ema(valid_values, signal)

        # 对齐 Signal 线
        signal_line = [None] * (len(prices) - len(signal_line_raw)) + signal_line_raw

        # Histogram = MACD - Signal
        histogram = []
        for i in range(len(prices)):
            if macd_line[i] is None or signal_line[i] is None:
                histogram.append(None)
            else:
                histogram.append(macd_line[i] - signal_line[i])

        return macd_line, signal_line, histogram

    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
        """
        相对强弱指标 (RSI)

        Args:
            prices: 价格序列
            period: 周期 (默认14)

        Returns:
            RSI 值序列 (0-100)
        """
        if len(prices) < period + 1:
            return [None] * len(prices)

        # 计算价格变化
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

        result = [None] * period  # 前面 period 个值无效

        # 初始平均涨跌
        gains = [max(d, 0) for d in deltas[:period]]
        losses = [abs(min(d, 0)) for d in deltas[:period]]

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        # 第一个 RSI
        if avg_loss == 0:
            rs = 100
        else:
            rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        result.append(rsi)

        # 后续 RSI 使用 Wilder 平滑
        for i in range(period, len(deltas)):
            gain = max(deltas[i], 0)
            loss = abs(min(deltas[i], 0))

            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period

            if avg_loss == 0:
                rs = 100
            else:
                rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            result.append(rsi)

        return result

    @staticmethod
    def bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2.0) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
        """
        布林带 (BOLL)

        Args:
            prices: 价格序列
            period: 周期 (默认20)
            std_dev: 标准差倍数 (默认2)

        Returns:
            (上轨, 中轨, 下轨)
        """
        sma = TechnicalIndicators.sma(prices, period)

        upper_band = []
        lower_band = []

        for i in range(len(prices)):
            if i < period - 1:
                upper_band.append(None)
                lower_band.append(None)
            else:
                # 计算标准差
                window = prices[i - period + 1:i + 1]
                std = np.std(window)

                middle = sma[i]
                upper = middle + std_dev * std
                lower = middle - std_dev * std

                upper_band.append(upper)
                lower_band.append(lower)

        return upper_band, sma, lower_band

    @staticmethod
    def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[Optional[float]]:
        """
        平均真实波幅 (ATR)

        Args:
            highs: 最高价序列
            lows: 最低价序列
            closes: 收盘价序列
            period: 周期 (默认14)

        Returns:
            ATR 值序列
        """
        if len(closes) < period + 1:
            return [None] * len(closes)

        # 计算真实波幅
        tr_list = []
        for i in range(1, len(closes)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i - 1])
            low_close = abs(lows[i] - closes[i - 1])

            tr = max(high_low, high_close, low_close)
            tr_list.append(tr)

        # 第一个 ATR 使用 SMA
        result = [None] * period
        first_atr = sum(tr_list[:period]) / period
        result.append(first_atr)

        # 后续使用 ATR 公式
        for i in range(period, len(tr_list)):
            atr = (result[-1] * (period - 1) + tr_list[i]) / period
            result.append(atr)

        return result

    @staticmethod
    def bias(prices: List[float], ma: List[float]) -> List[Optional[float]]:
        """
        乖离率 (BIAS)

        乖离率 = (价格 - 均线) / 均线 * 100%

        用于判断价格偏离均线的程度，是"严进策略"的核心指标。
        正值表示价格高于均线（可能追高），负值表示价格低于均线（可能回踩）。

        Args:
            prices: 价格序列
            ma: 均线序列（需与 prices 长度相同）

        Returns:
            乖离率序列（百分比）
        """
        if len(prices) != len(ma):
            raise ValueError("价格序列和均线序列长度必须相同")

        result = []
        for i in range(len(prices)):
            if ma[i] is None or ma[i] == 0:
                result.append(None)
            else:
                bias_value = (prices[i] - ma[i]) / ma[i] * 100
                result.append(bias_value)

        return result

    @staticmethod
    def volume_ratio(volumes: List[int], period: int = 5) -> List[Optional[float]]:
        """
        量比

        量比 = 当日成交量 / N日均量

        用于判断放量/缩量状态：
        - 量比 > 1.5：放量
        - 量比 < 0.7：缩量
        - 量比在 0.7-1.5 之间：正常

        Args:
            volumes: 成交量序列（手数）
            period: 均量周期 (默认5)

        Returns:
            量比序列
        """
        if len(volumes) < period:
            return [None] * len(volumes)

        result = []
        for i in range(len(volumes)):
            if i < period - 1:
                result.append(None)
            else:
                # 计算过去 N 日平均成交量
                avg_volume = sum(volumes[i - period + 1:i + 1]) / period
                if avg_volume == 0:
                    result.append(None)
                else:
                    ratio = volumes[i] / avg_volume
                    result.append(ratio)

        return result


class QuoteDataAnalyzer:
    """行情数据分析器"""

    def __init__(self, quotes: List[QuoteData]):
        """
        初始化分析器

        Args:
            quotes: 行情数据列表（按时间排序）
        """
        self.quotes = quotes
        self._prices = [q.price for q in quotes]
        self._highs = [q.high for q in quotes]
        self._lows = [q.low for q in quotes]
        self._volumes = [q.volume for q in quotes]

    def get_sma(self, period: int) -> List[Optional[float]]:
        """获取 SMA"""
        return TechnicalIndicators.sma(self._prices, period)

    def get_ema(self, period: int) -> List[Optional[float]]:
        """获取 EMA"""
        return TechnicalIndicators.ema(self._prices, period)

    def get_macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
        """获取 MACD"""
        return TechnicalIndicators.macd(self._prices, fast, slow, signal)

    def get_rsi(self, period: int = 14) -> List[Optional[float]]:
        """获取 RSI"""
        return TechnicalIndicators.rsi(self._prices, period)

    def get_bollinger_bands(self, period: int = 20, std_dev: float = 2.0) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
        """获取布林带"""
        return TechnicalIndicators.bollinger_bands(self._prices, period, std_dev)

    def get_atr(self, period: int = 14) -> List[Optional[float]]:
        """获取 ATR"""
        return TechnicalIndicators.atr(self._highs, self._lows, self._prices, period)

    def get_bias(self, ma_period: int) -> float:
        """
        获取最新乖离率

        Args:
            ma_period: 均线周期

        Returns:
            最新乖离率（百分比）
        """
        if len(self._prices) < ma_period:
            return 0.0

        ma = self.get_sma(ma_period)
        bias_values = TechnicalIndicators.bias(self._prices, ma)

        # 返回最新的有效值
        for value in reversed(bias_values):
            if value is not None:
                return value

        return 0.0

    def get_volume_ratio(self, period: int = 5) -> float:
        """
        获取最新量比

        Args:
            period: 均量周期 (默认5)

        Returns:
            最新量比
        """
        if len(self._volumes) < period:
            return 1.0

        ratios = TechnicalIndicators.volume_ratio(self._volumes, period)

        # 返回最新的有效值
        for value in reversed(ratios):
            if value is not None:
                return value

        return 1.0

    def get_latest_signals(self) -> dict:
        """
        获取最新交易信号

        Returns:
            信号字典
        """
        if len(self.quotes) < 30:
            return {"error": "数据不足"}

        signals = {}

        # RSI 信号
        rsi = self.get_rsi()
        if rsi[-1] is not None:
            if rsi[-1] < 30:
                signals["rsi"] = "oversold"  # 超卖
            elif rsi[-1] > 70:
                signals["rsi"] = "overbought"  # 超买
            else:
                signals["rsi"] = "neutral"

        # MACD 信号
        macd, signal_line, histogram = self.get_macd()
        if histogram and histogram[-1] is not None and histogram[-2] is not None:
            if histogram[-1] > 0 and histogram[-2] <= 0:
                signals["macd"] = "bullish_cross"  # 金叉
            elif histogram[-1] < 0 and histogram[-2] >= 0:
                signals["macd"] = "bearish_cross"  # 死叉
            else:
                signals["macd"] = "neutral"

        # 布林带信号
        upper, middle, lower = self.get_bollinger_bands()
        if upper[-1] is not None and lower[-1] is not None:
            current_price = self._prices[-1]
            if current_price > upper[-1]:
                signals["bollinger"] = "above_upper"  # 突破上轨
            elif current_price < lower[-1]:
                signals["bollinger"] = "below_lower"  # 跌破下轨
            else:
                signals["bollinger"] = "within_bands"

        # 趋势信号
        sma5 = self.get_sma(5)
        sma20 = self.get_sma(20)
        if sma5[-1] is not None and sma20[-1] is not None:
            if sma5[-1] > sma20[-1]:
                signals["trend"] = "uptrend"  # 上升趋势
            else:
                signals["trend"] = "downtrend"  # 下降趋势

        return signals
