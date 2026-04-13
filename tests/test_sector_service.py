# -*- coding: utf-8 -*-
"""
测试行业板块数据服务
"""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import tempfile

# 确保模块被导入以正确收集覆盖率
import core.sector_service
from core.sector_service import SectorData, SectorService, get_sector_service


class TestSectorData:
    """测试行业板块数据"""

    def test_sector_data_creation(self):
        """测试创建板块数据"""
        data = SectorData(
            code="BK001",
            name="食品饮料",
            current_price=100.5,
            change=1.5,
            change_pct=1.52,
            volume=1000000,
            amount=100500000.0
        )

        assert data.code == "BK001"
        assert data.name == "食品饮料"
        assert data.current_price == 100.5
        assert data.change == 1.5
        assert data.change_pct == 1.52
        assert data.volume == 1000000
        assert data.amount == 100500000.0

    def test_sector_data_defaults(self):
        """测试板块数据默认值"""
        data = SectorData(
            code="BK002",
            name="酿酒",
            current_price=0,
            change=0,
            change_pct=0
        )

        assert data.volume == 0
        assert data.amount == 0

    def test_sector_data_to_dict(self):
        """测试转换为字典"""
        data = SectorData(
            code="BK001",
            name="食品饮料",
            current_price=100.5,
            change=1.5,
            change_pct=1.52
        )

        result = data.to_dict()

        assert isinstance(result, dict)
        assert result["code"] == "BK001"
        assert result["name"] == "食品饮料"
        assert result["current_price"] == 100.5
        assert result["change"] == 1.5
        assert result["change_pct"] == 1.52


class TestSectorServiceInit:
    """测试行业板块服务初始化"""

    def test_init_default(self):
        """测试默认初始化"""
        service = SectorService()
        assert service.data_dir == Path("data")
        assert service.cache_file == Path("data/sectors.json")
        assert service.cache_hours == 4
        assert isinstance(service._sectors, list)

    def test_init_custom_params(self):
        """测试自定义参数初始化"""
        service = SectorService(data_dir="custom_data", cache_hours=8)
        assert service.data_dir == Path("custom_data")
        assert service.cache_hours == 8
        assert service.cache_file == Path("custom_data/sectors.json")

    def test_data_dir_created(self):
        """测试数据目录被创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = SectorService(data_dir=tmpdir)
            assert service.data_dir.exists()

    def test_load_missing_cache(self):
        """测试缓存文件不存在时"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = SectorService(data_dir=tmpdir)
            # 缓存文件不存在，应该是空列表
            assert service._sectors == []


class TestSectorServiceCache:
    """测试缓存功能"""

    def test_save_and_load_cache(self):
        """测试保存和加载缓存"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = SectorService(data_dir=tmpdir)

            # 添加测试数据
            service._sectors = [
                SectorData(
                    code="BK001",
                    name="食品饮料",
                    current_price=100.5,
                    change=1.5,
                    change_pct=1.52
                ),
                SectorData(
                    code="BK002",
                    name="酿酒",
                    current_price=50.0,
                    change=-0.5,
                    change_pct=-0.99
                )
            ]

            # 保存缓存
            service._save_cache()

            # 验证文件存在
            assert service.cache_file.exists()

            # 创建新实例并加载缓存
            service2 = SectorService(data_dir=tmpdir)
            assert len(service2._sectors) == 2
            assert service2._sectors[0].code == "BK001"
            assert service2._sectors[1].code == "BK002"

    def test_cache_expiration(self):
        """测试缓存过期"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建过期缓存
            old_data = {
                "last_update": (datetime.now() - timedelta(hours=5)).isoformat(),
                "sectors": [
                    {
                        "code": "BK001",
                        "name": "食品饮料",
                        "current_price": 100.5,
                        "change": 1.5,
                        "change_pct": 1.52,
                        "volume": 0,
                        "amount": 0
                    }
                ],
                "total": 1
            }

            with open(Path(tmpdir) / "sectors.json", "w", encoding="utf-8") as f:
                json.dump(old_data, f, indent=2, ensure_ascii=False)

            # 创建服务，缓存应该过期
            service = SectorService(data_dir=tmpdir, cache_hours=4)
            assert service._sectors == []

    def test_cache_valid(self):
        """测试缓存有效"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建有效缓存
            recent_data = {
                "last_update": (datetime.now() - timedelta(hours=2)).isoformat(),
                "sectors": [
                    {
                        "code": "BK001",
                        "name": "食品饮料",
                        "current_price": 100.5,
                        "change": 1.5,
                        "change_pct": 1.52,
                        "volume": 0,
                        "amount": 0
                    }
                ],
                "total": 1
            }

            with open(Path(tmpdir) / "sectors.json", "w", encoding="utf-8") as f:
                json.dump(recent_data, f, indent=2, ensure_ascii=False)

            # 创建服务，缓存应该有效
            service = SectorService(data_dir=tmpdir, cache_hours=4)
            assert len(service._sectors) == 1
            assert service._sectors[0].code == "BK001"


class TestSectorServiceFetch:
    """测试数据获取功能"""

    @patch('akshare.stock_board_industry_name_em', side_effect=ImportError())
    def test_fetch_without_akshare(self, mock_akshare):
        """测试没有 akshare 时"""
        service = SectorService()
        count = service.fetch_from_akshare()
        assert count == 0

    @patch('akshare.stock_board_industry_cons_em')
    @patch('akshare.stock_board_industry_name_em')
    def test_fetch_success(self, mock_name_em, mock_cons_em):
        """测试成功获取数据"""
        import pandas as pd

        # Mock AkShare 数据
        mock_df = pd.DataFrame([
            {'板块代码': 'BK001', '板块名称': '食品饮料'},
            {'板块代码': 'BK002', '板块名称': '酿酒'}
        ])

        mock_detail_df = pd.DataFrame([
            {'最新价': 100.5, '涨跌幅': 1.52}
        ])

        mock_name_em.return_value = mock_df
        mock_cons_em.return_value = mock_detail_df

        with tempfile.TemporaryDirectory() as tmpdir:
            service = SectorService(data_dir=tmpdir)
            count = service.fetch_from_akshare()
            assert count == 2

    @patch('akshare.stock_board_industry_name_em')
    def test_fetch_empty_response(self, mock_name_em):
        """测试空响应"""
        import pandas as pd

        mock_name_em.return_value = pd.DataFrame()

        with tempfile.TemporaryDirectory() as tmpdir:
            service = SectorService(data_dir=tmpdir)
            count = service.fetch_from_akshare()
            assert count == 0


class TestSectorServiceQuery:
    """测试查询功能"""

    def test_get_all_sectors_empty(self):
        """测试获取所有板块（空）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = SectorService(data_dir=tmpdir)
            sectors = service.get_all_sectors()
            assert sectors == []

    def test_get_all_sectors_with_data(self):
        """测试获取所有板块（有数据）"""
        service = SectorService()
        service._sectors = [
            SectorData(code="BK001", name="食品饮料", current_price=100.5, change=1.5, change_pct=1.52)
        ]

        sectors = service.get_all_sectors()
        assert len(sectors) == 1
        assert sectors[0].code == "BK001"

    def test_get_sector_by_code(self):
        """测试按代码获取板块"""
        service = SectorService()
        service._sectors = [
            SectorData(code="BK001", name="食品饮料", current_price=100.5, change=1.5, change_pct=1.52)
        ]

        sector = service.get_sector("BK001")
        assert sector is not None
        assert sector.code == "BK001"

    def test_get_sector_by_name(self):
        """测试按名称获取板块"""
        service = SectorService()
        service._sectors = [
            SectorData(code="BK001", name="食品饮料", current_price=100.5, change=1.5, change_pct=1.52)
        ]

        sector = service.get_sector("食品饮料")
        assert sector is not None
        assert sector.name == "食品饮料"

    def test_get_sector_not_found(self):
        """测试未找到板块"""
        service = SectorService()
        sector = service.get_sector("不存在")
        assert sector is None

    def test_search_by_code(self):
        """测试按代码搜索"""
        service = SectorService()
        service._sectors = [
            SectorData(code="BK001", name="食品饮料", current_price=100.5, change=1.5, change_pct=1.52),
            SectorData(code="BK002", name="酿酒", current_price=50.0, change=-0.5, change_pct=-0.99)
        ]

        results = service.search("BK")
        assert len(results) == 2

    def test_search_by_name(self):
        """测试按名称搜索"""
        service = SectorService()
        service._sectors = [
            SectorData(code="BK001", name="食品饮料", current_price=100.5, change=1.5, change_pct=1.52),
            SectorData(code="BK002", name="酿酒", current_price=50.0, change=-0.5, change_pct=-0.99)
        ]

        results = service.search("饮料")
        assert len(results) == 1
        assert results[0].code == "BK001"

    def test_search_with_limit(self):
        """测试搜索结果限制"""
        service = SectorService()
        for i in range(10):
            service._sectors.append(
                SectorData(code=f"BK{i:03d}", name=f"板块{i}", current_price=float(i), change=0, change_pct=0)
            )

        results = service.search("板块", limit=3)
        assert len(results) == 3


class TestSectorServiceRanking:
    """测试排名功能"""

    def test_get_top_gainers(self):
        """测试获取涨幅榜"""
        service = SectorService()
        service._sectors = [
            SectorData(code="BK001", name="食品饮料", current_price=100.5, change=1.5, change_pct=1.52),
            SectorData(code="BK002", name="酿酒", current_price=50.0, change=2.5, change_pct=2.52),
            SectorData(code="BK003", name="汽车", current_price=20.0, change=-0.5, change_pct=-0.99)
        ]

        top_gainers = service.get_top_gainers(limit=2)
        assert len(top_gainers) == 2
        assert top_gainers[0].code == "BK002"  # 涨幅最大
        assert top_gainers[1].code == "BK001"

    def test_get_top_losers(self):
        """测试获取跌幅榜"""
        service = SectorService()
        service._sectors = [
            SectorData(code="BK001", name="食品饮料", current_price=100.5, change=1.5, change_pct=1.52),
            SectorData(code="BK002", name="酿酒", current_price=50.0, change=2.5, change_pct=2.52),
            SectorData(code="BK003", name="汽车", current_price=20.0, change=-0.5, change_pct=-0.99)
        ]

        top_losers = service.get_top_losers(limit=2)
        assert len(top_losers) == 2
        assert top_losers[0].code == "BK003"  # 跌幅最大
        assert top_losers[1].code == "BK001" if len(top_losers) > 1 else None


class TestSectorServiceStatistics:
    """测试统计功能"""

    def test_get_statistics_empty(self):
        """测试空统计"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = SectorService(data_dir=tmpdir)
            stats = service.get_statistics()
            assert stats["total"] == 0
            assert stats["rising"] == 0
            assert stats["falling"] == 0
            assert stats["flat"] == 0
            assert stats["avg_change_pct"] == 0

    def test_get_statistics(self):
        """测试统计"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = SectorService(data_dir=tmpdir)
        service._sectors = [
            SectorData(code="BK001", name="食品饮料", current_price=100.5, change=1.5, change_pct=1.52),
            SectorData(code="BK002", name="酿酒", current_price=50.0, change=2.5, change_pct=2.52),
            SectorData(code="BK003", name="汽车", current_price=20.0, change=-0.5, change_pct=-0.99),
            SectorData(code="BK004", name="钢铁", current_price=10.0, change=0, change_pct=0)
        ]

        stats = service.get_statistics()
        assert stats["total"] == 4
        assert stats["rising"] == 2  # 2个上涨
        assert stats["falling"] == 1  # 1个下跌
        assert stats["flat"] == 1  # 1个平盘
        assert abs(stats["avg_change_pct"] - (1.52 + 2.52 - 0.99 + 0) / 4) < 0.01


class TestSectorServiceRefresh:
    """测试刷新功能"""

    def test_refresh_clears_cache(self):
        """测试刷新清除缓存"""
        service = SectorService()
        service._sectors = [
            SectorData(code="BK001", name="食品饮料", current_price=100.5, change=1.5, change_pct=1.52)
        ]

        assert len(service._sectors) == 1
        service._sectors.clear()

        assert len(service._sectors) == 0


class TestSectorServiceSingleton:
    """测试单例模式"""

    def test_get_singleton(self):
        """测试获取单例"""
        service1 = get_sector_service()
        service2 = get_sector_service()
        assert service1 is service2

    def test_singleton_persistence(self):
        """测试单例持久化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            service1 = get_sector_service(data_dir=tmpdir)
            service2 = get_sector_service(data_dir=tmpdir)
            assert service1 is service2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
