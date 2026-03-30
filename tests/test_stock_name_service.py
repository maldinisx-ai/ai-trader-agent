# -*- coding: utf-8 -*-
"""
测试股票名称映射服务
"""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
import tempfile

# 确保模块被导入以正确收集覆盖率
import core.stock_name_service
from core.stock_name_service import StockNameService, get_stock_name_service


class TestStockNameServiceInit:
    """测试股票名称服务初始化"""

    def test_init_default(self):
        """测试默认初始化"""
        service = StockNameService()
        assert service.data_dir == Path("data")
        assert service.cache_file == Path("data/stock_names.json")
        assert service.cache_days == 7
        assert isinstance(service._name_map, dict)
        assert isinstance(service._code_map, dict)

    def test_init_custom_params(self):
        """测试自定义参数初始化"""
        service = StockNameService(data_dir="custom_data", cache_days=30)
        assert service.data_dir == Path("custom_data")
        assert service.cache_days == 30
        assert service.cache_file == Path("custom_data/stock_names.json")

    def test_data_dir_created(self):
        """测试数据目录被创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = StockNameService(data_dir=tmpdir)
            assert service.data_dir.exists()

    def test_load_missing_cache(self):
        """测试缓存文件不存在时"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = StockNameService(data_dir=tmpdir)
            assert service._name_map == {}
            assert service._code_map == {}


class TestStockNameServiceCache:
    """测试缓存功能"""

    def test_save_and_load_cache(self):
        """测试保存和加载缓存"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = StockNameService(data_dir=tmpdir)

            # 添加测试数据
            service._name_map = {
                "600519.SH": "贵州茅台",
                "000001.SZ": "平安银行"
            }
            service._code_map = {
                "贵州茅台": "600519.SH",
                "平安银行": "000001.SZ"
            }

            # 保存缓存
            service._save_cache()

            # 验证文件存在
            assert service.cache_file.exists()

            # 创建新实例并加载缓存
            service2 = StockNameService(data_dir=tmpdir)
            assert "600519.SH" in service2._name_map
            assert "贵州茅台" in service2._code_map

    def test_cache_expiration(self):
        """测试缓存过期"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建过期缓存
            old_data = {
                "last_update": (datetime.now() - timedelta(days=10)).isoformat(),
                "names": {
                    "600519.SH": "贵州茅台"
                },
                "name_to_code": {
                    "贵州茅台": "600519.SH"
                },
                "total": 1
            }

            with open(Path(tmpdir) / "stock_names.json", "w", encoding="utf-8") as f:
                json.dump(old_data, f, indent=2, ensure_ascii=False)

            # 创建服务，缓存应该过期
            service = StockNameService(data_dir=tmpdir, cache_days=7)
            assert service._name_map == {}
            assert service._code_map == {}

    def test_cache_valid(self):
        """测试缓存有效"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建有效缓存
            recent_data = {
                "last_update": (datetime.now() - timedelta(days=3)).isoformat(),
                "names": {
                    "600519.SH": "贵州茅台"
                },
                "name_to_code": {
                    "贵州茅台": "600519.SH"
                },
                "total": 1
            }

            with open(Path(tmpdir) / "stock_names.json", "w", encoding="utf-8") as f:
                json.dump(recent_data, f, indent=2, ensure_ascii=False)

            # 创建服务，缓存应该有效
            service = StockNameService(data_dir=tmpdir, cache_days=7)
            assert "600519.SH" in service._name_map
            assert service._name_map["600519.SH"] == "贵州茅台"


class TestCodeNormalization:
    """测试代码标准化"""

    def test_normalize_code_standard_format(self):
        """测试标准格式"""
        service = StockNameService()
        assert service._normalize_code("600519.SH") == "600519.SH"
        assert service._normalize_code("000001.SZ") == "000001.SZ"

    def test_normalize_code_with_prefix(self):
        """测试带前缀的代码"""
        service = StockNameService()
        assert service._normalize_code("sh600519") == "600519.SH"
        assert service._normalize_code("SH600519") == "600519.SH"
        assert service._normalize_code("sz000001") == "000001.SZ"
        assert service._normalize_code("SZ000001") == "000001.SZ"

    def test_normalize_code_without_suffix(self):
        """测试无后缀的代码"""
        service = StockNameService()
        assert service._normalize_code("600519") == "600519.SH"
        assert service._normalize_code("000001") == "000001.SZ"

    def test_normalize_code_shanghai(self):
        """测试上海股票"""
        service = StockNameService()
        assert service._normalize_code("600519") == "600519.SH"
        assert service._normalize_code("689123") == "689123.SH"
        assert service._normalize_code("510000") == "510000.SH"

    def test_normalize_code_shenzhen(self):
        """测试深圳股票"""
        service = StockNameService()
        assert service._normalize_code("000001") == "000001.SZ"
        assert service._normalize_code("300001") == "300001.SZ"
        assert service._normalize_code("002594") == "002594.SZ"

    def test_normalize_code_case_insensitive(self):
        """测试大小写不敏感"""
        service = StockNameService()
        assert service._normalize_code("sh600519") == "600519.SH"
        assert service._normalize_code("SH600519") == "600519.SH"
        assert service._normalize_code("sz000001") == "000001.SZ"


class TestStockNameServiceFetch:
    """测试数据获取功能"""

    @patch('core.stock_name_service.ak')
    def test_fetch_without_akshare(self) -> None:
        """测试没有 akshare 时"""
        mock_akshare.__version__ = '1.0.0'
        mock_akshare.stock_info_a_code_name = Mock(side_effect=ImportError())

        service = StockNameService()
        count = service.fetch_from_akshare()
        assert count == 0

    @patch('core.stock_name_service.ak')
    def test_fetch_success(self, mock_akshare):
        """测试成功获取数据"""
        import pandas as pd

        # Mock AkShare 数据
        mock_df = pd.DataFrame([
            {'code': '600519', 'name': '贵州茅台'},
            {'code': '000001', 'name': '平安银行'}
        ])

        mock_akshare.stock_info_a_code_name = Mock(return_value=mock_df)

        with tempfile.TemporaryDirectory() as tmpdir:
            service = StockNameService(data_dir=tmpdir)
            count = service.fetch_from_akshare()
            assert count == 2
            assert "600519.SH" in service._name_map
            assert service._name_map["600519.SH"] == "贵州茅台"

    @patch('core.stock_name_service.ak')
    def test_fetch_empty_response(self, mock_akshare):
        """测试空响应"""
        import pandas as pd

        mock_akshare.stock_info_a_code_name = Mock(return_value=pd.DataFrame())

        with tempfile.TemporaryDirectory() as tmpdir:
            service = StockNameService(data_dir=tmpdir)
            count = service.fetch_from_akshare()
            assert count == 0


class TestStockNameServiceQuery:
    """测试查询功能"""

    def test_get_name_from_cache(self):
        """测试从缓存获取名称"""
        service = StockNameService()
        service._name_map = {
            "600519.SH": "贵州茅台"
        }

        name = service.get_name("600519.SH")
        assert name == "贵州茅台"

    def test_get_name_normalize_code(self):
        """测试获取名称时标准化代码"""
        service = StockNameService()
        service._name_map = {
            "600519.SH": "贵州茅台"
        }

        name = service.get_name("sh600519")
        assert name == "贵州茅台"

    def test_get_name_not_found(self):
        """测试未找到名称"""
        service = StockNameService()

        name = service.get_name("999999.SH")
        assert name == "999999.SH"  # 返回原代码

    def test_get_code_from_cache(self):
        """测试从缓存获取代码"""
        service = StockNameService()
        service._code_map = {
            "贵州茅台": "600519.SH"
        }

        code = service.get_code("贵州茅台")
        assert code == "600519.SH"

    def test_get_code_not_found(self):
        """测试未找到代码"""
        service = StockNameService()

        code = service.get_code("不存在股票")
        assert code is None

    def test_search_by_code(self):
        """测试按代码搜索"""
        service = StockNameService()
        service._name_map = {
            "600519.SH": "贵州茅台",
            "000001.SZ": "平安银行"
        }

        results = service.search("600")
        assert len(results) == 1
        assert results[0]["code"] == "600519.SH"

    def test_search_by_name(self):
        """测试按名称搜索"""
        service = StockNameService()
        service._name_map = {
            "600519.SH": "贵州茅台",
            "000001.SZ": "平安银行"
        }

        results = service.search("银行")
        assert len(results) == 1
        assert results[0]["name"] == "平安银行"

    def test_search_with_limit(self):
        """测试搜索结果限制"""
        service = StockNameService()
        for i in range(20):
            service._name_map[f"600{i:05d}.SH"] = f"股票{i}"

        results = service.search("股票", limit=5)
        assert len(results) == 5

    def test_get_all_names(self):
        """测试获取所有名称"""
        service = StockNameService()
        service._name_map = {
            "600519.SH": "贵州茅台",
            "000001.SZ": "平安银行"
        }

        names = service.get_all_names()
        assert len(names) == 2
        assert names["600519.SH"] == "贵州茅台"

    def test_batch_get_names(self):
        """测试批量获取名称"""
        service = StockNameService()
        service._name_map = {
            "600519.SH": "贵州茅台",
            "000001.SZ": "平安银行"
        }

        names = service.batch_get_names(["600519.SH", "000001.SZ", "999999.SH"])
        assert names["600519.SH"] == "贵州茅台"
        assert names["000001.SZ"] == "平安银行"
        assert names["999999.SH"] == "999999.SH"  # 找不到返回原代码


class TestStockNameServiceCustomMappings:
    """测试自定义映射功能"""

    def test_add_custom_mapping(self):
        """测试添加自定义映射"""
        service = StockNameService()
        assert "888888.SH" not in service._name_map

        service.add_custom("888888.SH", "测试股票")
        assert service._name_map["888888.SH"] == "测试股票"
        assert service._code_map["测试股票"] == "888888.SH"

    def test_add_custom_normalize_code(self):
        """测试添加自定义映射时标准化代码"""
        service = StockNameService()
        service.add_custom("sh600519", "贵州茅台")
        assert "600519.SH" in service._name_map

    def test_remove_custom_mapping(self):
        """测试移除自定义映射"""
        service = StockNameService()
        service.add_custom("888888.SH", "测试股票")
        assert "888888.SH" in service._name_map

        service.remove_custom("888888.SH")
        assert "888888.SH" not in service._name_map
        assert "测试股票" not in service._code_map

    def test_remove_nonexistent_mapping(self):
        """测试移除不存在的映射（不应该报错）"""
        service = StockNameService()
        # 不应该抛出异常
        service.remove_custom("999999.SH")


class TestStockNameServiceRefresh:
    """测试刷新功能"""

    def test_refresh_clears_cache(self):
        """测试刷新清除缓存"""
        service = StockNameService()
        service._name_map = {
            "600519.SH": "贵州茅台"
        }
        service._code_map = {
            "贵州茅台": "600519.SH"
        }

        service._name_map.clear()
        service._code_map.clear()

        assert len(service._name_map) == 0
        assert len(service._code_map) == 0


class TestStockNameServiceSingleton:
    """测试单例模式"""

    def test_get_singleton(self):
        """测试获取单例"""
        service1 = get_stock_name_service()
        service2 = get_stock_name_service()
        assert service1 is service2

    def test_singleton_persistence(self):
        """测试单例持久化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service1 = get_stock_name_service(data_dir=tmpdir)
            service2 = get_stock_name_service(data_dir=tmpdir)
            assert service1 is service2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
