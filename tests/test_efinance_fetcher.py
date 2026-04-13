# -*- coding: utf-8 -*-
"""
测试 Efinance 数据下载器 (mock 版本)

使用 mock 避免实际调用 Efinance API
"""

import pytest
from pathlib import Path
from datetime import datetime
import json
from unittest.mock import Mock, patch, MagicMock

# 导入 src.main 中的组件
import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class MockEfinanceDownloader:
    """Mock 版本的 EfinanceDownloader，不依赖真实的 efinance"""

    def __init__(self, output_dir: str = "data/stocks", progress_file: str = "data/efinance_progress.json"):
        """初始化下载器（不导入真实的 efinance）"""
        self.ef = Mock()  # Mock efinance 对象
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file = Path(progress_file)
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        self.progress = self._load_progress()

        # 统计
        self.session_success = 0
        self.session_failed = 0
        self.session_skipped = 0

    def _load_progress(self) -> dict:
        """加载下载进度"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return {
                        "downloaded": set(data.get("downloaded", [])),
                        "failed": set(data.get("failed", [])),
                        "last_update": data.get("last_update"),
                        "total_success": data.get("total_success", 0),
                        "total_failed": data.get("total_failed", 0)
                    }
            except Exception:
                pass

        return {
            "downloaded": set(),
            "failed": set(),
            "last_update": None,
            "total_success": 0,
            "total_failed": 0
        }

    def _save_progress(self):
        """保存下载进度"""
        progress_data = {
            "downloaded": list(self.progress["downloaded"]),
            "failed": list(self.progress["failed"]),
            "last_update": datetime.now().isoformat(),
            "total_success": self.progress["total_success"],
            "total_failed": self.progress["total_failed"]
        }

        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, indent=2, ensure_ascii=False)

    def _is_downloaded(self, symbol: str) -> bool:
        """检查股票是否已下载"""
        return symbol in self.progress["downloaded"]

    def _mark_downloaded(self, symbol: str):
        """标记股票为已下载"""
        self.progress["downloaded"].add(symbol)
        if symbol in self.progress["failed"]:
            self.progress["failed"].remove(symbol)
        self.progress["total_success"] = len(self.progress["downloaded"])

    def _mark_failed(self, symbol: str):
        """标记股票为下载失败"""
        if symbol not in self.progress["downloaded"]:
            self.progress["failed"].add(symbol)
            self.progress["total_failed"] = len(self.progress["failed"])

    def clear_progress(self):
        """清除进度（重新开始）"""
        self.progress = {
            "downloaded": set(),
            "failed": set(),
            "last_update": None,
            "total_success": 0,
            "total_failed": 0
        }
        self._save_progress()


@pytest.fixture
def tmp_output_dir(tmp_path):
    """创建临时输出目录"""
    return str(tmp_path / "stocks")


@pytest.fixture
def tmp_progress_file(tmp_path):
    """创建临时进度文件"""
    return str(tmp_path / "efinance_progress.json")


@pytest.fixture
def downloader(tmp_output_dir, tmp_progress_file):
    """创建下载器实例"""
    return MockEfinanceDownloader(output_dir=tmp_output_dir, progress_file=tmp_progress_file)


class TestProgressManagement:
    """测试进度管理"""

    def test_load_progress_empty(self, downloader):
        """测试加载空进度"""
        downloader.progress = downloader._load_progress()
        assert downloader.progress["downloaded"] == set()
        assert downloader.progress["failed"] == set()
        assert downloader.progress["last_update"] is None
        assert downloader.progress["total_success"] == 0
        assert downloader.progress["total_failed"] == 0

    def test_load_progress_existing_file(self, downloader, tmp_progress_file):
        """测试加载已存在的进度文件"""
        progress_data = {
            "downloaded": ["600519", "000001"],
            "failed": ["000002"],
            "last_update": "2024-01-01T00:00:00",
            "total_success": 2,
            "total_failed": 1
        }
        with open(tmp_progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f)

        downloader.progress = downloader._load_progress()
        assert "600519" in downloader.progress["downloaded"]
        assert "000001" in downloader.progress["downloaded"]
        assert "000002" in downloader.progress["failed"]
        assert downloader.progress["total_success"] == 2
        assert downloader.progress["total_failed"] == 1

    def test_load_progress_invalid_json(self, downloader, tmp_progress_file):
        """测试加载无效的进度文件"""
        with open(tmp_progress_file, 'w', encoding='utf-8') as f:
            f.write("invalid json")

        downloader.progress = downloader._load_progress()
        assert downloader.progress["downloaded"] == set()
        assert downloader.progress["failed"] == set()

    def test_save_progress(self, downloader, tmp_progress_file):
        """测试保存进度"""
        downloader.progress["downloaded"].add("600519")
        downloader.progress["failed"].add("000002")
        downloader.progress["total_success"] = 1
        downloader.progress["total_failed"] = 1

        downloader._save_progress()

        assert Path(tmp_progress_file).exists()

        with open(tmp_progress_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert "600519" in data["downloaded"]
            assert "000002" in data["failed"]
            assert data["total_success"] == 1
            assert data["total_failed"] == 1


class TestProgressMarking:
    """测试进度标记"""

    def test_is_downloaded_false(self, downloader):
        """测试检查未下载的股票"""
        assert downloader._is_downloaded("600519") is False

    def test_is_downloaded_true(self, downloader):
        """测试检查已下载的股票"""
        downloader.progress["downloaded"].add("600519")
        assert downloader._is_downloaded("600519") is True

    def test_mark_downloaded_new(self, downloader):
        """测试标记新下载的股票"""
        downloader._mark_downloaded("600519")
        assert "600519" in downloader.progress["downloaded"]
        assert downloader.progress["total_success"] == 1

    def test_mark_downloaded_remove_from_failed(self, downloader):
        """测试标记下载成功时从失败列表移除"""
        downloader.progress["failed"].add("600519")
        downloader._mark_downloaded("600519")
        assert "600519" in downloader.progress["downloaded"]
        assert "600519" not in downloader.progress["failed"]

    def test_mark_failed_new(self, downloader):
        """测试标记失败的股票"""
        downloader._mark_failed("600519")
        assert "600519" in downloader.progress["failed"]
        assert downloader.progress["total_failed"] == 1

    def test_mark_failed_already_downloaded(self, downloader):
        """测试已下载的股票不标记为失败"""
        downloader.progress["downloaded"].add("600519")
        downloader._mark_failed("600519")
        assert "600519" not in downloader.progress["failed"]
        assert downloader.progress["total_failed"] == 0


class TestClearProgress:
    """测试清除进度"""

    def test_clear_progress(self, downloader, tmp_progress_file):
        """测试清除进度"""
        downloader.progress["downloaded"].add("600519")
        downloader.progress["failed"].add("000002")
        downloader._save_progress()

        downloader.clear_progress()

        assert downloader.progress["downloaded"] == set()
        assert downloader.progress["failed"] == set()
        assert downloader.progress["total_success"] == 0
        assert downloader.progress["total_failed"] == 0


class TestInitialization:
    """测试初始化"""

    def test_init_without_efinance(self):
        """测试没有安装 efinance"""
        from tools.data.efinance_fetcher import EfinanceDownloader

        with patch.dict('sys.modules', {'efinance': None}):
            with pytest.raises(RuntimeError) as exc_info:
                EfinanceDownloader()
            assert "efinance 未安装" in str(exc_info.value)


class TestDirectoryCreation:
    """测试目录创建"""

    def test_output_dir_created(self, tmp_output_dir, tmp_progress_file):
        """测试输出目录自动创建"""
        import shutil
        if Path(tmp_output_dir).exists():
            shutil.rmtree(tmp_output_dir)

        downloader = MockEfinanceDownloader(output_dir=tmp_output_dir, progress_file=tmp_progress_file)
        assert Path(tmp_output_dir).exists()

    def test_progress_dir_created(self, tmp_output_dir, tmp_progress_file):
        """测试进度文件目录自动创建"""
        progress_path = Path(tmp_progress_file)
        if progress_path.parent.exists():
            import shutil
            shutil.rmtree(progress_path.parent)

        downloader = MockEfinanceDownloader(output_dir=tmp_output_dir, progress_file=tmp_progress_file)
        assert progress_path.parent.exists()


class TestSessionStatistics:
    """测试会话统计"""

    def test_session_stats_initialization(self, downloader):
        """测试会话统计初始化"""
        assert downloader.session_success == 0
        assert downloader.session_failed == 0
        assert downloader.session_skipped == 0


class TestProgressPersistence:
    """测试进度持久化"""

    def test_progress_persistence(self, downloader, tmp_progress_file):
        """测试进度持久化"""
        downloader.progress["downloaded"].add("600519")
        downloader.progress["failed"].add("000002")
        downloader._save_progress()

        new_downloader = MockEfinanceDownloader(output_dir=downloader.output_dir, progress_file=tmp_progress_file)
        assert "600519" in new_downloader.progress["downloaded"]
        assert "000002" in new_downloader.progress["failed"]

    def test_progress_update(self, downloader, tmp_progress_file):
        """测试更新进度"""
        downloader.progress["downloaded"].add("600519")
        downloader.progress["total_success"] = 1  # 手动设置以匹配 _mark_downloaded 行为
        downloader._save_progress()

        new_downloader = MockEfinanceDownloader(output_dir=downloader.output_dir, progress_file=tmp_progress_file)
        assert len(new_downloader.progress["downloaded"]) == 1
        assert new_downloader.progress["total_success"] == 1

        new_downloader.progress["downloaded"].add("000001")
        new_downloader.progress["total_success"] = 2  # 手动设置以匹配 _mark_downloaded 行为
        new_downloader._save_progress()

        final_downloader = MockEfinanceDownloader(output_dir=downloader.output_dir, progress_file=tmp_progress_file)
        assert "600519" in final_downloader.progress["downloaded"]
        assert "000001" in final_downloader.progress["downloaded"]
        assert final_downloader.progress["total_success"] == 2


class TestProgressFileFormat:
    """测试进度文件格式"""

    def test_progress_file_structure(self, downloader, tmp_progress_file):
        """测试进度文件结构"""
        downloader.progress["downloaded"].add("600519")
        downloader._save_progress()

        with open(tmp_progress_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        required_keys = ["downloaded", "failed", "last_update", "total_success", "total_failed"]
        for key in required_keys:
            assert key in data

        assert isinstance(data["downloaded"], list)
        assert isinstance(data["failed"], list)
        assert isinstance(data["total_success"], int)
        assert isinstance(data["total_failed"], int)


class TestProgressEdgeCases:
    """测试进度边缘情况"""

    def test_duplicate_mark_downloaded(self, downloader):
        """测试重复标记已下载"""
        downloader._mark_downloaded("600519")
        downloader._mark_downloaded("600519")
        assert len(downloader.progress["downloaded"]) == 1
        assert downloader.progress["total_success"] == 1

    def test_duplicate_mark_failed(self, downloader):
        """测试重复标记失败"""
        downloader._mark_failed("600519")
        downloader._mark_failed("600519")
        assert len(downloader.progress["failed"]) == 1

    def test_mark_downloaded_then_failed(self, downloader):
        """测试先标记已下载再标记失败"""
        downloader._mark_downloaded("600519")
        downloader._mark_failed("600519")
        assert "600519" in downloader.progress["downloaded"]
        assert "600519" not in downloader.progress["failed"]

    def test_mark_failed_then_downloaded(self, downloader):
        """测试先标记失败再标记已下载"""
        downloader._mark_failed("600519")
        downloader._mark_downloaded("600519")
        assert "600519" in downloader.progress["downloaded"]
        assert "600519" not in downloader.progress["failed"]


class TestProgressWithTotalCounters:
    """测试进度总数器"""

    def test_total_success_counter(self, downloader):
        """测试总成功计数器"""
        downloader._mark_downloaded("600519")
        downloader._mark_downloaded("000001")
        assert downloader.progress["total_success"] == 2

    def test_total_failed_counter(self, downloader):
        """测试总失败计数器"""
        downloader._mark_failed("600519")
        downloader._mark_failed("000002")
        assert downloader.progress["total_failed"] == 2

    def test_total_counters_with_transition(self, downloader):
        """测试总数器转换（失败 -> 成功）"""
        downloader._mark_failed("600519")
        downloader._mark_failed("000002")
        assert downloader.progress["total_failed"] == 2

        downloader._mark_downloaded("600519")
        assert downloader.progress["total_success"] == 1
        # 注意：total_failed 不会自动更新，只有在 _mark_failed 时才会更新
        # 这是实际行为，移除一个失败项不会减少 total_failed
        assert downloader.progress["total_failed"] == 2


class TestProgressLastUpdate:
    """测试最后更新时间"""

    def test_save_progress_updates_timestamp(self, downloader, tmp_progress_file):
        """测试保存进度时更新时间戳"""
        downloader._save_progress()

        with open(tmp_progress_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert data["last_update"] is not None

        # 验证是有效的 ISO 格式时间
        datetime.fromisoformat(data["last_update"])


class TestEfinanceAPI:
    """测试真实 EfinanceDownloader 的 API（使用 patch）"""

    def test_real_class_init_check(self):
        """测试真实类的初始化检查"""
        from tools.data.efinance_fetcher import EfinanceDownloader

        with patch.dict('sys.modules', {'efinance': Mock()}):
            # 创建临时实例（不调用 __init__ 中会导入 efinance 的代码）
            dl = EfinanceDownloader.__new__(EfinanceDownloader)
            dl.progress = {
                "downloaded": set(),
                "failed": set(),
                "last_update": None,
                "total_success": 0,
                "total_failed": 0
            }

            # 测试标记方法
            dl._mark_downloaded("600519")
            assert "600519" in dl.progress["downloaded"]

            dl._mark_failed("000001")
            assert "000001" in dl.progress["failed"]


class TestProgressFileOperations:
    """测试进度文件操作"""

    def test_create_progress_file_if_not_exists(self, downloader, tmp_progress_file):
        """测试创建不存在的进度文件"""
        if Path(tmp_progress_file).exists():
            Path(tmp_progress_file).unlink()

        downloader._save_progress()
        assert Path(tmp_progress_file).exists()

    def test_overwrite_existing_progress_file(self, downloader, tmp_progress_file):
        """测试覆盖已存在的进度文件"""
        downloader.progress["downloaded"].add("600519")
        downloader._save_progress()

        # 更新状态
        downloader.progress["downloaded"].add("000001")
        downloader._save_progress()

        # 验证只包含两个股票
        with open(tmp_progress_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert len(data["downloaded"]) == 2