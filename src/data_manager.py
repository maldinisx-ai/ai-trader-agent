# -*- coding: utf-8 -*-
"""
数据管理器

管理真实行情数据获取、缓存和限流。
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import akshare as ak
import pandas as pd

from core.schemas import QuoteData


logger = logging.getLogger(__name__)


# ============================================
# 数据源配置
# ============================================

class DataSourceConfig:
    """数据源配置"""

    # 请求限流（每秒）
    RATE_LIMIT = 10

    # 缓存过期时间（秒）
    CACHE_TTL = 60

    # 批量获取大小
    BATCH_SIZE = 50

    # 重试次数
    MAX_RETRIES = 3


# ============================================
# 数据管理器
# ============================================

class DataManager:
    """
    数据管理器

    负责行情数据的获取、缓存和限流控制。
    """

    def __init__(self, config: Optional[DataSourceConfig] = None):
        """
        初始化数据管理器

        Args:
            config: 数据源配置
        """
        self.config = config or DataSourceConfig()

        # 数据缓存 {symbol: (data, expire_time)}
        self._cache: Dict[str, tuple[QuoteData, datetime]] = {}

        # 请求限流
        self._semaphore = asyncio.Semaphore(self.config.RATE_LIMIT)

        # 全量行情数据（定期更新）
        self._all_quotes: Optional[pd.DataFrame] = None
        self._all_quotes_updated: Optional[datetime] = None

    async def get_quote(self, symbol: str, use_cache: bool = True) -> QuoteData:
        """
        获取单只股票行情

        Args:
            symbol: 股票代码
            use_cache: 是否使用缓存

        Returns:
            QuoteData: 行情数据
        """
        # 检查缓存
        if use_cache:
            cached = self._get_cached(symbol)
            if cached is not None:
                return cached

        # 获取新数据
        async with self._semaphore:
            try:
                # 尝试从全量数据中获取
                quote = await self._get_from_all_quotes(symbol)
                if quote:
                    self._set_cache(symbol, quote)
                    return quote

                # 如果全量数据没有，单独获取
                quote = await self._fetch_quote(symbol)
                self._set_cache(symbol, quote)
                return quote

            except Exception as e:
                logger.error(f"[DataManager] 获取 {symbol} 行情失败: {e}")
                raise

    async def get_quotes(self, symbols: List[str], use_cache: bool = True) -> Dict[str, QuoteData]:
        """
        批量获取多只股票行情

        Args:
            symbols: 股票代码列表
            use_cache: 是否使用缓存

        Returns:
            Dict[str, QuoteData]: 股票代码到行情的映射
        """
        results = {}

        # 先从缓存获取
        if use_cache:
            for symbol in symbols:
                cached = self._get_cached(symbol)
                if cached:
                    results[symbol] = cached

        # 批量获取未缓存的股票
        uncached = [s for s in symbols if s not in results]

        if uncached:
            async with self._semaphore:
                for symbol in uncached:
                    try:
                        quote = await self.get_quote(symbol, use_cache=False)
                        results[symbol] = quote
                    except Exception as e:
                        logger.warning(f"[DataManager] 获取 {symbol} 失败: {e}")
                        results[symbol] = None

        return results

    async def get_all_quotes(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        获取所有 A 股实时行情

        Args:
            force_refresh: 是否强制刷新

        Returns:
            pd.DataFrame: 行情数据
        """
        # 检查是否需要更新
        if (not force_refresh and
            self._all_quotes is not None and
            self._all_quotes_updated and
            (datetime.now() - self._all_quotes_updated).total_seconds() < self.config.CACHE_TTL):
            return self._all_quotes

        # 获取新数据
        async with self._semaphore:
            self._all_quotes = await self._fetch_all_quotes()
            self._all_quotes_updated = datetime.now()
            logger.info(f"[DataManager] 更新全量行情数据，共 {len(self._all_quotes)} 只股票")

        return self._all_quotes

    async def get_history(self, symbol: str, period: str = "daily") -> pd.DataFrame:
        """
        获取历史 K 线数据

        Args:
            symbol: 股票代码
            period: 周期 (daily, weekly)

        Returns:
            pd.DataFrame: K 线数据
        """
        async with self._semaphore:
            try:
                # 使用 AkShare 获取历史数据
                if period == "daily":
                    df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="")
                elif period == "weekly":
                    df = ak.stock_zh_a_hist(symbol=symbol, period="weekly", adjust="")
                else:
                    raise ValueError(f"不支持的周期: {period}")

                return df

            except Exception as e:
                logger.error(f"[DataManager] 获取 {symbol} 历史数据失败: {e}")
                raise

    def clear_cache(self, symbol: Optional[str] = None):
        """
        清除缓存

        Args:
            symbol: 股票代码，None 表示清除全部
        """
        if symbol:
            self._cache.pop(symbol, None)
        else:
            self._cache.clear()

    # ============================================
    # 私有方法
    # ============================================

    def _get_cached(self, symbol: str) -> Optional[QuoteData]:
        """从缓存获取数据"""
        if symbol in self._cache:
            data, expire_time = self._cache[symbol]
            if datetime.now() < expire_time:
                return data
            # 过期删除
            del self._cache[symbol]
        return None

    def _set_cache(self, symbol: str, data: QuoteData, ttl: Optional[float] = None):
        """设置缓存"""
        if ttl is None:
            ttl = self.config.CACHE_TTL
        expire_time = datetime.now() + timedelta(seconds=ttl)
        self._cache[symbol] = (data, expire_time)

    async def _fetch_quote(self, symbol: str) -> QuoteData:
        """
        从 AkShare 获取单只股票行情

        Args:
            symbol: 股票代码

        Returns:
            QuoteData: 行情数据
        """
        # 在线程池中执行（因为 AkShare 是同步的）
        loop = asyncio.get_event_loop()
        stock_zh_a_spot_em = await loop.run_in_executor(
            None, ak.stock_zh_a_spot_em
        )

        # 查找目标股票
        stock_info = stock_zh_a_spot_em[
            stock_zh_a_spot_em['代码'] == symbol
        ]

        if stock_info.empty:
            raise ValueError(f"未找到股票代码: {symbol}")

        row = stock_info.iloc[0]

        return self._row_to_quote(row)

    async def _fetch_all_quotes(self) -> pd.DataFrame:
        """获取所有 A 股实时行情"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, ak.stock_zh_a_spot_em)

    async def _get_from_all_quotes(self, symbol: str) -> Optional[QuoteData]:
        """从全量数据中获取股票行情"""
        if self._all_quotes is None:
            return None

        # 检查是否需要更新全量数据
        if (self._all_quotes_updated is None or
            (datetime.now() - self._all_quotes_updated).total_seconds() > self.config.CACHE_TTL):
            return None

        stock_info = self._all_quotes[
            self._all_quotes['代码'] == symbol
        ]

        if stock_info.empty:
            return None

        return self._row_to_quote(stock_info.iloc[0])

    def _row_to_quote(self, row: pd.Series) -> QuoteData:
        """将 DataFrame 行转换为 QuoteData"""
        return QuoteData(
            symbol=str(row['代码']),
            name=str(row['名称']),
            price=float(row['最新价']),
            change=float(row['涨跌幅']),
            volume=int(row['成交量'] / 100),  # 转换为手
            amount=float(row['成交额']),
            high=float(row['最高']),
            low=float(row['最低']),
            open=float(row['今开']),
            upper_limit=float(row['最高']) if row['涨跌幅'] >= 9.9 else None,
            lower_limit=float(row['最低']) if row['涨跌幅'] <= -9.9 else None,
            is_suspended=False,
            timestamp=datetime.now(),
        )


# ============================================
# 全局单例
# ============================================

_global_data_manager: Optional[DataManager] = None


def get_data_manager() -> DataManager:
    """获取全局数据管理器单例"""
    global _global_data_manager
    if _global_data_manager is None:
        _global_data_manager = DataManager()
    return _global_data_manager


def reset_data_manager():
    """重置全局数据管理器"""
    global _global_data_manager
    _global_data_manager = None