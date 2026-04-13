# -*- coding: utf-8 -*-
"""
测试数据管理器模块

测试行情数据获取、缓存和限流
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import pandas as pd

# 添加项目根目录到路径
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_manager import (
    DataManager,
    DataSourceConfig,
    get_data_manager,
    reset_data_manager
)
from core.schemas import QuoteData


class TestDataSourceConfig:
    """测试数据源配置"""

    def test_default_values(self):
        """测试默认配置值"""
        config = DataSourceConfig()

        assert config.RATE_LIMIT == 10
        assert config.CACHE_TTL == 60
        assert config.BATCH_SIZE == 50
        assert config.MAX_RETRIES == 3


class TestDataManagerInitialization:
    """测试数据管理器初始化"""

    def test_init_with_default_config(self):
        """测试使用默认配置初始化"""
        manager = DataManager()

        assert manager.config.RATE_LIMIT == 10
        assert manager.config.CACHE_TTL == 60
        assert len(manager._cache) == 0
        assert manager._all_quotes is None
        assert manager._all_quotes_updated is None

    def test_init_with_custom_config(self):
        """测试使用自定义配置初始化"""
        custom_config = DataSourceConfig()
        custom_config.RATE_LIMIT = 20
        custom_config.CACHE_TTL = 120

        manager = DataManager(config=custom_config)

        assert manager.config.RATE_LIMIT == 20
        assert manager.config.CACHE_TTL == 120


class TestDataManagerCache:
    """测试数据管理器缓存"""

    @pytest.mark.asyncio
    async def test_set_cache(self):
        """测试设置缓存"""
        manager = DataManager()

        quote = QuoteData(
            symbol="600519",
            name="测试",
            price=100.0,
            change=0.05,
            volume=1000000,
            amount=100000000.0,
            high=105.0,
            low=95.0,
            upper_limit=110.0,
            lower_limit=90.0,
        )

        manager._set_cache("600519", quote, ttl=60)

        assert "600519" in manager._cache
        cached_data, expire_time = manager._cache["600519"]
        assert cached_data.symbol == "600519"
        assert expire_time > datetime.now()

    @pytest.mark.asyncio
    async def test_get_cached_valid(self):
        """测试获取有效缓存"""
        manager = DataManager()

        quote = QuoteData(
            symbol="600519",
            name="测试",
            price=100.0,
            change=0.05,
            volume=1000000,
            amount=100000000.0,
            high=105.0,
            low=95.0,
            upper_limit=110.0,
            lower_limit=90.0,
        )

        manager._set_cache("600519", quote, ttl=60)
        cached = manager._get_cached("600519")

        assert cached is not None
        assert cached.symbol == "600519"

    @pytest.mark.asyncio
    async def test_get_cached_expired(self):
        """测试获取过期缓存"""
        manager = DataManager()

        quote = QuoteData(
            symbol="600519",
            name="测试",
            price=100.0,
            change=0.05,
            volume=1000000,
            amount=100000000.0,
            high=105.0,
            low=95.0,
            upper_limit=110.0,
            lower_limit=90.0,
        )

        # 设置很短的 TTL
        manager._set_cache("600519", quote, ttl=0.001)

        # 等待过期
        await asyncio.sleep(0.01)

        cached = manager._get_cached("600519")
        assert cached is None

    @pytest.mark.asyncio
    async def test_get_cached_nonexistent(self):
        """测试获取不存在的缓存"""
        manager = DataManager()

        cached = manager._get_cached("000001")
        assert cached is None

    @pytest.mark.asyncio
    async def test_clear_cache_single_symbol(self):
        """测试清除单个股票缓存"""
        manager = DataManager()

        quote = QuoteData(
            symbol="600519",
            name="测试",
            price=100.0,
            change=0.05,
            volume=1000000,
            amount=100000000.0,
            high=105.0,
            low=95.0,
            upper_limit=110.0,
            lower_limit=90.0,
        )

        manager._set_cache("600519", quote)
        manager._set_cache("000001", quote)

        manager.clear_cache("600519")

        assert "600519" not in manager._cache
        assert "000001" in manager._cache

    @pytest.mark.asyncio
    async def test_clear_cache_all(self):
        """测试清除所有缓存"""
        manager = DataManager()

        quote = QuoteData(
            symbol="600519",
            name="测试",
            price=100.0,
            change=0.05,
            volume=1000000,
            amount=100000000.0,
            high=105.0,
            low=95.0,
            upper_limit=110.0,
            lower_limit=90.0,
        )

        manager._set_cache("600519", quote)
        manager._set_cache("000001", quote)

        manager.clear_cache()

        assert len(manager._cache) == 0


class TestDataManagerRowToQuote:
    """测试行数据转换"""

    @pytest.mark.asyncio
    async def test_row_to_quote(self):
        """测试将 DataFrame 行转换为 QuoteData"""
        manager = DataManager()

        row = pd.Series({
            '代码': '600519',
            '名称': '贵州茅台',
            '最新价': 100.0,
            '涨跌幅': 5.0,
            '成交量': 100000000,
            '成交额': 10000000000.0,
            '最高': 105.0,
            '最低': 95.0,
            '今开': 98.0,
        })

        quote = manager._row_to_quote(row)

        assert quote.symbol == "600519"
        assert quote.name == "贵州茅台"
        assert quote.price == 100.0
        assert quote.change == 5.0
        assert quote.volume == 1000000  # 转换为手
        assert quote.high == 105.0
        assert quote.low == 95.0
        assert quote.open == 98.0

    @pytest.mark.asyncio
    async def test_row_to_quote_limit_up(self):
        """测试涨停时设置上限价"""
        manager = DataManager()

        row = pd.Series({
            '代码': '600519',
            '名称': '贵州茅台',
            '最新价': 100.0,
            '涨跌幅': 10.0,  # >= 9.9
            '成交量': 100000000,
            '成交额': 10000000000.0,
            '最高': 105.0,
            '最低': 95.0,
            '今开': 98.0,
        })

        quote = manager._row_to_quote(row)

        assert quote.upper_limit == 105.0

    @pytest.mark.asyncio
    async def test_row_to_quote_limit_down(self):
        """测试跌停时设置下限价"""
        manager = DataManager()

        row = pd.Series({
            '代码': '600519',
            '名称': '贵州茅台',
            '最新价': 100.0,
            '涨跌幅': -10.0,  # <= -9.9
            '成交量': 100000000,
            '成交额': 10000000000.0,
            '最高': 105.0,
            '最低': 95.0,
            '今开': 98.0,
        })

        quote = manager._row_to_quote(row)

        assert quote.lower_limit == 95.0


class TestGetAllQuotesCache:
    """测试获取全量行情缓存"""

    @pytest.mark.asyncio
    async def test_get_all_quotes_uses_cache(self):
        """测试使用缓存的全量行情"""
        manager = DataManager()

        # 设置缓存的行情数据
        df = pd.DataFrame({
            '代码': ['600519', '000001'],
            '名称': ['贵州茅台', '平安银行'],
            '最新价': [100.0, 50.0],
            '涨跌幅': [5.0, -2.0],
            '成交量': [100000000, 200000000],
            '成交额': [10000000000.0, 10000000000.0],
            '最高': [105.0, 55.0],
            '最低': [95.0, 45.0],
            '今开': [98.0, 52.0],
        })

        manager._all_quotes = df
        manager._all_quotes_updated = datetime.now()

        # 获取行情，应该使用缓存
        result = await manager.get_all_quotes(force_refresh=False)

        assert len(result) == 2
        assert result is df

    @pytest.mark.asyncio
    async def test_get_all_quotes_force_refresh(self):
        """测试强制刷新全量行情"""
        manager = DataManager()

        # 设置已过期的缓存
        df = pd.DataFrame({
            '代码': ['600519'],
            '名称': ['贵州茅台'],
            '最新价': [100.0],
            '涨跌幅': [5.0],
            '成交量': [100000000],
            '成交额': [10000000000.0],
            '最高': [105.0],
            '最低': [95.0],
            '今开': [98.0],
        })

        manager._all_quotes = df
        manager._all_quotes_updated = datetime.now() - timedelta(seconds=120)

        # Mock fetch_all_quotes
        new_df = pd.DataFrame({
            '代码': ['000001'],
            '名称': ['平安银行'],
            '最新价': [50.0],
            '涨跌幅': [-2.0],
            '成交量': [200000000],
            '成交额': [10000000000.0],
            '最高': [55.0],
            '最低': [45.0],
            '今开': [52.0],
        })

        manager._fetch_all_quotes = AsyncMock(return_value=new_df)

        # 强制刷新
        result = await manager.get_all_quotes(force_refresh=True)

        assert len(result) == 1
        assert result.iloc[0]['代码'] == '000001'


class TestGlobalDataManager:
    """测试全局数据管理器"""

    def setup_method(self):
        """每个测试前重置全局管理器"""
        reset_data_manager()

    def test_get_data_manager_returns_new_instance(self):
        """测试首次获取返回新实例"""
        manager = get_data_manager()

        assert isinstance(manager, DataManager)

    def test_get_data_manager_returns_singleton(self):
        """测试获取返回单例"""
        manager1 = get_data_manager()
        manager2 = get_data_manager()

        assert manager1 is manager2

    def test_reset_data_manager(self):
        """测试重置全局管理器"""
        manager1 = get_data_manager()
        reset_data_manager()

        manager2 = get_data_manager()

        assert manager1 is not manager2


class TestGetFromAllQuotes:
    """测试从全量数据获取"""

    @pytest.mark.asyncio
    async def test_get_from_all_quotes_found(self):
        """测试从全量数据找到股票"""
        manager = DataManager()

        df = pd.DataFrame({
            '代码': ['600519', '000001'],
            '名称': ['贵州茅台', '平安银行'],
            '最新价': [100.0, 50.0],
            '涨跌幅': [5.0, -2.0],
            '成交量': [100000000, 200000000],
            '成交额': [10000000000.0, 10000000000.0],
            '最高': [105.0, 55.0],
            '最低': [95.0, 45.0],
            '今开': [98.0, 52.0],
        })

        manager._all_quotes = df
        manager._all_quotes_updated = datetime.now()

        quote = await manager._get_from_all_quotes("600519")

        assert quote is not None
        assert quote.symbol == "600519"

    @pytest.mark.asyncio
    async def test_get_from_all_quotes_not_found(self):
        """测试从全量数据未找到股票"""
        manager = DataManager()

        df = pd.DataFrame({
            '代码': ['600519'],
            '名称': ['贵州茅台'],
            '最新价': [100.0],
            '涨跌幅': [5.0],
            '成交量': [100000000],
            '成交额': [10000000000.0],
            '最高': [105.0],
            '最低': [95.0],
            '今开': [98.0],
        })

        manager._all_quotes = df
        manager._all_quotes_updated = datetime.now()

        quote = await manager._get_from_all_quotes("000001")

        assert quote is None

    @pytest.mark.asyncio
    async def test_get_from_all_quotes_no_data(self):
        """测试全量数据为空"""
        manager = DataManager()

        quote = await manager._get_from_all_quotes("600519")

        assert quote is None

    @pytest.mark.asyncio
    async def test_get_from_all_quotes_expired(self):
        """测试全量数据过期"""
        manager = DataManager()

        df = pd.DataFrame({
            '代码': ['600519'],
            '名称': ['贵州茅台'],
            '最新价': [100.0],
            '涨跌幅': [5.0],
            '成交量': [100000000],
            '成交额': [10000000000.0],
            '最高': [105.0],
            '最低': [95.0],
            '今开': [98.0],
        })

        manager._all_quotes = df
        manager._all_quotes_updated = datetime.now() - timedelta(seconds=120)

        quote = await manager._get_from_all_quotes("600519")

        assert quote is None
class TestGetDataManagerExtendedCoverage:
    """扩展覆盖测试 - 未覆盖的代码行"""

    @pytest.mark.asyncio
    async def test_get_quotes_with_cache_and_fetch(self, mocker):
        """测试批量获取行情：部分命中缓存，部分需要获取"""
        manager = DataManager()

        # Mock get_quote for uncached symbols
        quote = QuoteData(
            symbol="000001",
            name="平安银行",
            price=50.0,
            change=-2.0,
            volume=2000000,
            amount=100000000.0,
        )

        with patch.object(manager, 'get_quote', new_callable=AsyncMock, return_value=quote):
            results = await manager.get_quotes(["600519", "000001"], use_cache=True)

            assert "000001" in results
            assert results["000001"].symbol == "000001"

    @pytest.mark.asyncio
    async def test_get_quotes_error_handling(self):
        """测试批量获取行情时的错误处理"""
        manager = DataManager()

        # Mock get_quote to raise exception
        async def mock_get_quote_error(symbol, use_cache=True):
            raise RuntimeError(f"Failed to fetch {symbol}")

        with patch.object(manager, 'get_quote', side_effect=mock_get_quote_error):
            results = await manager.get_quotes(["600519", "000001"], use_cache=True)

            assert "600519" in results
            assert "000001" in results
            assert results["600519"] is None
            assert results["000001"] is None

    @pytest.mark.asyncio
    async def test_get_all_quotes_without_cache(self):
        """测试获取全量行情：无缓存时获取新数据"""
        manager = DataManager()

        df = pd.DataFrame({
            "代码": ["600519"],
            "名称": ["贵州茅台"],
            "最新价": [100.0],
            "涨跌幅": [5.0],
            "成交量": [100000000],
            "成交额": [10000000000.0],
            "最高": [105.0],
            "最低": [95.0],
            "今开": [98.0],
        })

        manager._fetch_all_quotes = AsyncMock(return_value=df)

        result = await manager.get_all_quotes(force_refresh=True)

        assert len(result) == 1
        assert result.iloc[0]["代码"] == "600519"

    @pytest.mark.asyncio
    async def test_get_history_daily(self):
        """测试获取日线历史数据"""
        manager = DataManager()

        df = pd.DataFrame({
            "日期": ["2025-01-01", "2025-01-02"],
            "收盘": [100.0, 101.0],
        })

        with patch("src.data_manager.ak.stock_zh_a_hist") as mock_hist:
            mock_hist.return_value = df

            result = await manager.get_history("600519", "daily")

            assert result is not None
            mock_hist.assert_called_once_with(symbol="600519", period="daily", adjust="")

    @pytest.mark.asyncio
    async def test_get_history_weekly(self):
        """测试获取周线历史数据"""
        manager = DataManager()

        df = pd.DataFrame({
            "日期": ["2025-01-01", "2025-01-08"],
            "收盘": [100.0, 101.0],
        })

        with patch("src.data_manager.ak.stock_zh_a_hist") as mock_hist:
            mock_hist.return_value = df

            result = await manager.get_history("600519", "weekly")

            assert result is not None
            mock_hist.assert_called_once_with(symbol="600519", period="weekly", adjust="")

    @pytest.mark.asyncio
    async def test_get_history_invalid_period(self):
        """测试获取历史数据时使用无效周期"""
        manager = DataManager()

        with pytest.raises(ValueError, match="不支持的周期"):
            await manager.get_history("600519", "monthly")


class TestDataManagerExtendedCoverage:
    """扩展覆盖测试 - 数据管理器"""

    @pytest.mark.asyncio
    async def test_get_quote_uses_cache(self):
        """测试get_quote使用缓存（Lines 84-87）"""
        manager = DataManager()

        # 设置缓存
        cached_quote = QuoteData(
            symbol="600519",
            name="测试",
            price=100.0,
            change=5.0,
            volume=1000000,
            amount=100000000.0,
            high=105.0,
            low=95.0,
        )
        manager._set_cache("600519", cached_quote, ttl=60)

        # Mock _fetch_quote 以确保不会调用
        manager._fetch_quote = AsyncMock(side_effect=Exception("Should not be called"))

        # 获取行情（应该从缓存返回）
        result = await manager.get_quote("600519", use_cache=True)

        assert result.symbol == "600519"
        assert result.price == 100.0

    @pytest.mark.asyncio
    async def test_get_quote_from_all_quotes(self):
        """测试从全量数据获取（Lines 92-96）"""
        manager = DataManager()

        # 设置全量行情
        df = pd.DataFrame({
            '代码': ['600519'],
            '名称': ['贵州茅台'],
            '最新价': [100.0],
            '涨跌幅': [5.0],
            '成交量': [100000000],
            '成交额': [10000000000.0],
            '最高': [105.0],
            '最低': [95.0],
            '今开': [98.0],
        })
        manager._all_quotes = df
        manager._all_quotes_updated = datetime.now()

        # Mock _fetch_quote 以确保不会调用
        manager._fetch_quote = AsyncMock(side_effect=Exception("Should not be called"))

        # 获取行情（应该从all_quotes获取）
        result = await manager.get_quote("600519", use_cache=False)

        assert result is not None
        assert result.symbol == "600519"

    @pytest.mark.asyncio
    async def test_get_quote_fetch_new(self):
        """测试单独获取新数据（Lines 99-101）"""
        manager = DataManager()

        # 不设置缓存和all_quotes，强制单独获取
        manager._all_quotes = None

        # Mock _fetch_quote
        expected_quote = QuoteData(
            symbol="600519",
            name="贵州茅台",
            price=100.0,
            change=5.0,
            volume=1000000,
            amount=100000000.0,
            high=105.0,
            low=95.0,
        )
        manager._fetch_quote = AsyncMock(return_value=expected_quote)

        # 获取行情
        result = await manager.get_quote("600519", use_cache=False)

        assert result.symbol == "600519"
        manager._fetch_quote.assert_called_once_with("600519")

    @pytest.mark.asyncio
    async def test_get_quote_exception_handling(self):
        """测试异常处理（Lines 103-105）"""
        manager = DataManager()

        # Mock _fetch_quote 抛出异常
        manager._fetch_quote = AsyncMock(side_effect=Exception("Network error"))

        # 获取行情应该抛出异常
        with pytest.raises(Exception, match="Network error"):
            await manager.get_quote("600519", use_cache=False)

    @pytest.mark.asyncio
    async def test_get_quotes_with_uncached(self):
        """测试获取未缓存的股票（Line 125, 128-130）"""
        manager = DataManager()

        # Mock _fetch_quote
        def mock_fetch(symbol):
            return QuoteData(
                symbol=symbol,
                name="测试",
                price=100.0,
                change=5.0,
                volume=1000000,
                amount=100000000.0,
                high=105.0,
                low=95.0,
            )

        manager._fetch_quote = AsyncMock(side_effect=mock_fetch)

        # 获取多只股票行情（都不在缓存中）
        results = await manager.get_quotes(["600519", "000001"], use_cache=False)

        assert len(results) == 2
        assert "600519" in results
        assert "000001" in results

    @pytest.mark.asyncio
    async def test_fetch_quote_akshare_success(self):
        """测试从AkShare获取行情成功（Lines 238-253）"""
        manager = DataManager()

        # Mock AkShare 返回数据
        df = pd.DataFrame({
            '代码': ['600519'],
            '名称': ['贵州茅台'],
            '最新价': [100.0],
            '涨跌幅': [5.0],
            '成交量': [100000000],
            '成交额': [10000000000.0],
            '最高': [105.0],
            '最低': [95.0],
            '今开': [98.0],
        })

        with patch("src.data_manager.ak.stock_zh_a_spot_em") as mock_ak:
            mock_ak.return_value = df

            result = await manager._fetch_quote("600519")

            assert result is not None
            assert result.symbol == "600519"
            assert result.price == 100.0

    @pytest.mark.asyncio
    async def test_fetch_quote_akshare_not_found(self):
        """测试股票代码未找到（Line 249）"""
        manager = DataManager()

        # Mock AkShare 返回空数据
        df = pd.DataFrame({
            '代码': [],
            '名称': [],
            '最新价': [],
            '涨跌幅': [],
            '成交量': [],
            '成交额': [],
            '最高': [],
            '最低': [],
            '今开': [],
        })

        with patch("src.data_manager.ak.stock_zh_a_spot_em") as mock_ak:
            mock_ak.return_value = df

            with pytest.raises(ValueError, match="未找到股票代码"):
                await manager._fetch_quote("999999")

    @pytest.mark.asyncio
    async def test_fetch_all_quotes(self):
        """测试获取所有A股行情（Lines 257-258）"""
        manager = DataManager()

        # Mock AkShare 返回数据
        df = pd.DataFrame({
            '代码': ['600519', '000001'],
            '名称': ['贵州茅台', '平安银行'],
            '最新价': [100.0, 50.0],
            '涨跌幅': [5.0, -2.0],
            '成交量': [100000000, 200000000],
            '成交额': [10000000000.0, 10000000000.0],
            '最高': [105.0, 55.0],
            '最低': [95.0, 45.0],
            '今开': [98.0, 52.0],
        })

        with patch("src.data_manager.ak.stock_zh_a_spot_em") as mock_ak:
            mock_ak.return_value = df

            result = await manager._fetch_all_quotes()

            assert len(result) == 2
            assert result.iloc[0]['代码'] == '600519'
            assert result.iloc[1]['代码'] == '000001'
