# -*- coding: utf-8 -*-
"""
测试本地数据加载器
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

import pandas as pd
import pytest

from tools.data.local_data_loader import LocalDataLoader


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def sample_klines_data():
    """创建样例K线数据"""
    return pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=30, freq='D'),
        'open': [100.0 + i for i in range(30)],
        'close': [101.0 + i for i in range(30)],
        'high': [102.0 + i for i in range(30)],
        'low': [99.0 + i for i in range(30)],
        'volume': [1000000 + i * 10000 for i in range(30)],
        'amount': [100000000.0 + i * 1000000.0 for i in range(30)],
    })


@pytest.fixture
def sample_indices_data():
    """创建样例指数数据"""
    return pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=5, freq='D'),
        'close': [3000.0 + i * 10 for i in range(5)],
        'volume': [100000000 + i * 1000000 for i in range(5)],
    })


@pytest.fixture
def sample_industry_flow_data():
    """创建样例行业资金流向数据"""
    return pd.DataFrame({
        '行业': ['金融', '科技', '医药', '消费', '制造'],
        '净额': [100000000, 80000000, 60000000, -50000000, -30000000],
        '流入资金': [500000000, 400000000, 300000000, 200000000, 150000000],
        '流出资金': [400000000, 320000000, 240000000, 250000000, 180000000],
        '行业-涨跌幅': [2.5, 3.0, 1.8, -1.2, -0.8],
        '领涨股': ['A600519', 'A000001', 'A000002', '600036', '601318'],
        '领涨股-涨跌幅': [5.0, 6.0, 4.0, -2.0, -1.5],
    })


@pytest.fixture
def sample_stock_industry_data():
    """创建样例股票行业映射数据"""
    # 使用字母开头的代码避免被解析为整数
    return pd.DataFrame({
        '股票代码': ['A600519', 'A000001', 'A000002'],
        '行业名称': ['食品饮料', '银行', '房地产'],
        '行业代码': ['CP01', 'BK01', 'RE01'],
    })


@pytest.fixture
def temp_data_dir(sample_klines_data, sample_indices_data, sample_industry_flow_data, sample_stock_industry_data):
    """创建临时数据目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_path = Path(tmpdir)

        # 创建 klines 目录
        klines_dir = data_path / "klines"
        klines_dir.mkdir()

        # 创建K线文件（新格式）
        for symbol in ['A600519', 'A000001', 'A000002']:
            csv_path = klines_dir / f"{symbol}_SH.csv"
            sample_klines_data.to_csv(csv_path, index=False)

        # 创建指数文件
        for index_name in ['sh', 'sz', 'cyb']:
            csv_path = data_path / f"index_{index_name}.csv"
            sample_indices_data.to_csv(csv_path, index=False)

        # 创建行业资金流向文件
        industry_flow_path = data_path / "industry_fund_flow.csv"
        sample_industry_flow_data.to_csv(industry_flow_path, index=False)

        # 创建股票行业映射文件
        stock_industry_path = data_path / "stock_industry_mapping.csv"
        sample_stock_industry_data.to_csv(stock_industry_path, index=False)

        yield str(data_path)


# ============================================
# 初始化测试
# ============================================

class TestLocalDataLoaderInit:
    """测试初始化"""

    def test_init_default(self):
        """测试默认初始化"""
        loader = LocalDataLoader()
        assert loader.data_dir == Path("data")
        assert loader._cache == {}

    def test_init_custom_dir(self):
        """测试自定义数据目录"""
        loader = LocalDataLoader(data_dir="/custom/path")
        assert loader.data_dir == Path("/custom/path")
        assert loader._cache == {}


# ============================================
# get_available_symbols 测试
# ============================================

class TestGetAvailableSymbols:
    """测试获取可用股票代码"""

    def test_get_available_symbols_from_klines_dir(self, temp_data_dir):
        """测试从klines目录获取股票代码"""
        loader = LocalDataLoader(data_dir=temp_data_dir)
        symbols = loader.get_available_symbols()

        assert len(symbols) == 3
        assert 'A600519' in symbols
        assert 'A000001' in symbols
        assert 'A000002' in symbols
        assert symbols == sorted(symbols)  # 应该是排序的

    def test_get_available_symbols_old_format(self):
        """测试旧格式的K线文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = Path(tmpdir)

            # 创建旧格式文件
            for symbol in ['A600519', 'A000001']:
                csv_path = data_path / f"klines_{symbol}.csv"
                sample_data = pd.DataFrame({
                    'date': ['2024-01-01'],
                    'open': [100.0],
                    'close': [101.0],
                    'high': [102.0],
                    'low': [99.0],
                    'volume': [1000000],
                    'amount': [100000000.0],
                })
                sample_data.to_csv(csv_path, index=False)

            loader = LocalDataLoader(data_dir=str(data_path))
            symbols = loader.get_available_symbols()

            assert len(symbols) == 2
            assert 'A600519' in symbols
            assert 'A000001' in symbols

    def test_get_available_symbols_no_data(self):
        """测试没有数据时返回空列表"""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = LocalDataLoader(data_dir=tmpdir)
            symbols = loader.get_available_symbols()
            assert symbols == []


# ============================================
# _load_klines 测试
# ============================================

class TestLoadKlines:
    """测试加载K线数据"""

    def test_load_klines_success(self, temp_data_dir):
        """测试成功加载K线数据"""
        loader = LocalDataLoader(data_dir=temp_data_dir)
        df = loader._load_klines("A600519")

        assert df is not None
        assert len(df) == 30
        assert 'date' in df.columns
        assert 'ma5' in df.columns
        assert 'ma10' in df.columns
        assert 'change' in df.columns

    def test_load_klines_new_format_column_rename(self, temp_data_dir):
        """测试新格式列名转换"""
        # 创建使用新列名的文件
        data_path = Path(temp_data_dir) / "klines"
        sample_data = pd.DataFrame({
            'trade_date': ['2024-01-01', '2024-01-02'],
            'open_price': [100.0, 101.0],
            'close_price': [101.0, 102.0],
            'high_price': [102.0, 103.0],
            'low_price': [99.0, 100.0],
            'volume': [1000000, 1100000],
            'amount': [100000000.0, 110000000.0],
        })
        csv_path = data_path / "A600520_SH.csv"
        sample_data.to_csv(csv_path, index=False)

        loader = LocalDataLoader(data_dir=temp_data_dir)
        df = loader._load_klines("A600520")

        assert df is not None
        assert 'date' in df.columns  # 列名已转换
        assert 'open' in df.columns
        assert 'close' in df.columns

    def test_load_klines_not_found(self, temp_data_dir):
        """测试K线数据不存在"""
        loader = LocalDataLoader(data_dir=temp_data_dir)
        df = loader._load_klines("A999999")

        assert df is None

    def test_load_klines_cache(self, temp_data_dir):
        """测试缓存功能"""
        loader = LocalDataLoader(data_dir=temp_data_dir)

        # 第一次加载
        df1 = loader._load_klines("A600519")
        cache_key = f"klines_A600519"
        assert cache_key in loader._cache

        # 第二次加载应该使用缓存
        df2 = loader._load_klines("A600519")
        assert df1 is df2  # 应该是同一个对象


# ============================================
# _add_technical_indicators 测试
# ============================================

class TestAddTechnicalIndicators:
    """测试添加技术指标"""

    def test_add_indicators(self, sample_klines_data):
        """测试添加技术指标"""
        loader = LocalDataLoader()
        df = loader._add_technical_indicators(sample_klines_data)

        # 检查移动平均线
        assert 'ma5' in df.columns
        assert 'ma10' in df.columns
        assert 'ma20' in df.columns
        assert 'ma60' in df.columns

        # 检查价格变化
        assert 'change' in df.columns
        assert 'change_abs' in df.columns

        # 检查振幅
        assert 'amplitude' in df.columns

        # 检查成交量指标
        assert 'volume_ma5' in df.columns
        assert 'volume_ratio' in df.columns

    def test_ma_calculation(self, sample_klines_data):
        """测试移动平均线计算"""
        loader = LocalDataLoader()
        df = loader._add_technical_indicators(sample_klines_data)

        # MA5 应该从第5行开始有值
        assert pd.isna(df['ma5'].iloc[0:4]).all()
        assert not pd.isna(df['ma5'].iloc[4])

        # 验证MA5计算
        expected_ma5 = sample_klines_data['close'].iloc[0:5].mean()
        assert abs(df['ma5'].iloc[4] - expected_ma5) < 0.01


# ============================================
# _analyze_trend 测试
# ============================================

class TestAnalyzeTrend:
    """测试趋势分析"""

    def test_analyze_trend_bullish(self, sample_klines_data):
        """测试看涨趋势"""
        # 创建明显的上涨趋势
        data = sample_klines_data.copy()
        data.loc[29, 'close'] = data.loc[0, 'close'] * 1.05  # 5日涨幅超过2%
        data = LocalDataLoader()._add_technical_indicators(data)

        loader = LocalDataLoader()
        trend = loader._analyze_trend(data.tail(30))

        assert 'direction' in trend
        assert 'change_5d' in trend
        assert 'ma_alignment' in trend

    def test_analyze_trend_insufficient_data(self):
        """测试数据不足"""
        data = pd.DataFrame({
            'close': [100.0, 101.0, 102.0],
            'ma5': [pd.NA, pd.NA, pd.NA],
            'ma10': [pd.NA, pd.NA, pd.NA],
            'ma20': [pd.NA, pd.NA, pd.NA],
        })

        loader = LocalDataLoader()
        trend = loader._analyze_trend(data)

        assert trend['direction'] == 'unknown'
        assert trend['strength'] == 0


# ============================================
# _calculate_support_resistance 测试
# ============================================

class TestCalculateSupportResistance:
    """测试支撑阻力计算"""

    def test_calculate_support_resistance(self, sample_klines_data):
        """测试计算支撑阻力"""
        loader = LocalDataLoader()
        sr = loader._calculate_support_resistance(sample_klines_data)

        assert 'support' in sr
        assert 'resistance' in sr
        assert 'current_price' in sr

        # 支撑位应该有3个
        assert len(sr['support']) == 3

        # 阻力位应该有3个
        assert len(sr['resistance']) == 3

        # 支撑位应该递增
        assert sr['support'] == sorted(sr['support'])

        # 阻力位应该递减
        assert sr['resistance'] == sorted(sr['resistance'], reverse=True)

    def test_calculate_support_resistance_insufficient_data(self):
        """测试数据不足"""
        data = pd.DataFrame({
            'low': [100.0, 101.0],
            'high': [102.0, 103.0],
            'close': [101.0, 102.0],
        })

        loader = LocalDataLoader()
        sr = loader._calculate_support_resistance(data)

        assert sr['support'] is None
        assert sr['resistance'] is None


# ============================================
# load_all_data 测试
# ============================================

class TestLoadAllData:
    """测试加载所有数据"""

    def test_load_all_data_success(self, temp_data_dir):
        """测试成功加载所有数据"""
        loader = LocalDataLoader(data_dir=temp_data_dir)
        result = loader.load_all_data("A600519")

        assert result['symbol'] == "A600519"
        assert 'timestamp' in result
        assert 'klines' in result
        assert 'indices' in result
        assert 'industry_flow' in result
        # industry 可能为 None（如果映射文件没有匹配）
        assert 'industry' in result

    def test_load_all_data_no_indices(self, temp_data_dir):
        """测试没有指数数据"""
        # 删除指数文件
        data_path = Path(temp_data_dir)
        for csv_path in data_path.glob("index_*.csv"):
            csv_path.unlink()

        loader = LocalDataLoader(data_dir=temp_data_dir)
        result = loader.load_all_data("A600519")

        # 仍然应该有K线数据
        assert 'klines' in result
        # 但没有指数数据
        assert 'indices' not in result or len(result.get('indices', [])) == 0


# ============================================
# load_all_stocks 测试
# ============================================

class TestLoadAllStocks:
    """测试加载所有股票数据"""

    def test_load_all_stocks_summary(self, temp_data_dir):
        """测试加载股票摘要"""
        loader = LocalDataLoader(data_dir=temp_data_dir)
        result = loader.load_all_stocks(full_data=False, limit=2)

        assert result['type'] == 'multi_stock'
        assert result['total_count'] == 2
        assert result['full_data'] is False
        assert len(result['stocks']) == 2

    def test_load_all_stocks_full(self, temp_data_dir):
        """测试加载完整数据"""
        loader = LocalDataLoader(data_dir=temp_data_dir)
        result = loader.load_all_stocks(full_data=True, limit=1)

        assert result['full_data'] is True
        assert len(result['stocks']) == 1

        # 完整数据应该包含 recent_klines
        stock = result['stocks'][0]
        assert 'recent_klines' in stock
        assert 'klines_df' in stock

    def test_load_all_stocks_limit(self, temp_data_dir):
        """测试数量限制"""
        loader = LocalDataLoader(data_dir=temp_data_dir)

        # 不限制
        result1 = loader.load_all_stocks(full_data=False, limit=0)
        assert result1['total_count'] == 3

        # 限制为2
        result2 = loader.load_all_stocks(full_data=False, limit=2)
        assert result2['total_count'] == 2


# ============================================
# _get_stock_industry 测试
# ============================================

class TestGetStockIndustry:
    """测试获取股票行业"""

    def test_get_stock_industry_success(self, temp_data_dir):
        """测试成功获取行业"""
        loader = LocalDataLoader(data_dir=temp_data_dir)
        result = loader._get_stock_industry("A600519")

        assert result is not None
        assert result['industry'] == '食品饮料'
        assert result['industry_code'] == 'CP01'

    def test_get_stock_industry_not_found(self, temp_data_dir):
        """测试股票不存在"""
        loader = LocalDataLoader(data_dir=temp_data_dir)
        result = loader._get_stock_industry("A999999")

        assert result is None


# ============================================
# 缓存测试
# ============================================

class TestCache:
    """测试缓存功能"""

    def test_cache_klines(self, temp_data_dir):
        """测试K线缓存"""
        loader = LocalDataLoader(data_dir=temp_data_dir)

        # 第一次加载
        df1 = loader._load_klines("A600519")
        assert "klines_A600519" in loader._cache

        # 修改缓存
        loader._cache["klines_A600519"] = None

        # 第二次加载应该使用缓存（返回None）
        df2 = loader._load_klines("A600519")
        assert df2 is None

    def test_cache_industry_flow(self, temp_data_dir):
        """测试行业资金流向缓存"""
        loader = LocalDataLoader(data_dir=temp_data_dir)

        # 第一次加载
        df1 = loader._load_industry_flow()
        assert "industry_flow" in loader._cache

        # 第二次加载应该使用缓存
        df2 = loader._load_industry_flow()
        assert df1 is df2
