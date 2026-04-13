# -*- coding: utf-8 -*-
"""
测试分析历史记录存储
"""

import gc
import json
import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import time
import shutil

# 确保模块被导入以正确收集覆盖率
import core.analysis_history
from core.analysis_history import AnalysisRecord, AnalysisHistoryStore, get_analysis_history_store


def cleanup_db_files(tmpdir):
    """清理数据库文件（Windows 兼容）"""
    # 强制垃圾回收，确保所有连接被关闭
    gc.collect()
    time.sleep(0.1)  # 给 SQLite 一点时间释放文件

    # 删除所有数据库相关文件
    tmpdir_path = Path(tmpdir)
    for pattern in ["*.db", "*.db-wal", "*.db-shm"]:
        for f in tmpdir_path.glob(pattern):
            try:
                f.unlink()
            except (PermissionError, OSError):
                pass  # 忽略删除失败

    # 删除临时目录
    try:
        tmpdir_path.rmdir()
    except (PermissionError, OSError):
        pass  # 忽略删除失败


class TestAnalysisRecord:
    """测试分析记录"""

    def test_record_creation_minimal(self):
        """测试创建最小记录"""
        record = AnalysisRecord(
            stock_code="600519.SH",
            stock_name="贵州茅台",
            analysis_time=datetime.now().isoformat(),
            overall_signal="buy",
            overall_score=75
        )

        assert record.stock_code == "600519.SH"
        assert record.stock_name == "贵州茅台"
        assert record.overall_signal == "buy"
        assert record.overall_score == 75
        assert record.active_strategies == []
        assert record.signals == []

    def test_record_creation_full(self):
        """测试创建完整记录"""
        record = AnalysisRecord(
            stock_code="600519.SH",
            stock_name="贵州茅台",
            analysis_time=datetime.now().isoformat(),
            overall_signal="buy",
            overall_score=75,
            current_price=1680.0,
            change_pct=1.52,
            active_strategies=["momentum", "fundamental"],
            signals=[
                {"strategy": "momentum", "signal": "buy", "score": 80},
                {"strategy": "fundamental", "signal": "hold", "score": 60}
            ],
            market_data={
                "regime": "bull",
                "volatility": 0.02
            }
        )

        assert record.current_price == 1680.0
        assert record.change_pct == 1.52
        assert len(record.active_strategies) == 2
        assert len(record.signals) == 2
        assert record.market_data is not None


class TestAnalysisHistoryStoreInit:
    """测试存储初始化"""

    def test_init_default(self):
        """测试默认初始化"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            store = AnalysisHistoryStore(db_path=str(db_path))
            assert store.db_path == db_path
        finally:
            cleanup_db_files(tmpdir)

    def test_database_created(self):
        """测试数据库被创建"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            assert not db_path.exists()

            store = AnalysisHistoryStore(db_path=str(db_path))
            assert db_path.exists()
        finally:
            cleanup_db_files(tmpdir)

    def test_init_with_custom_path(self):
        """测试使用自定义路径"""
        store = AnalysisHistoryStore(db_path="custom/path/test.db")
        assert store.db_path == Path("custom/path/test.db")


class TestAnalysisHistoryStore:
    """测试存储功能"""

    def test_store_analysis_basic(self):
        """测试存储基本分析"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            store = AnalysisHistoryStore(db_path=str(db_path))

            record = AnalysisRecord(
                stock_code="600519.SH",
                stock_name="贵州茅台",
                analysis_time=datetime.now().isoformat(),
                overall_signal="buy",
                overall_score=75
            )

            record_id = store.store_analysis(record)
            assert record_id > 0
            assert isinstance(record_id, int)
        finally:
            cleanup_db_files(tmpdir)

    def test_store_analysis_full(self):
        """测试存储完整分析"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            store = AnalysisHistoryStore(db_path=str(db_path))

            record = AnalysisRecord(
                stock_code="600519.SH",
                stock_name="贵州茅台",
                analysis_time=datetime.now().isoformat(),
                overall_signal="buy",
                overall_score=75,
                current_price=1680.0,
                change_pct=1.52,
                active_strategies=["momentum"],
                signals=[{"strategy": "test", "signal": "buy"}],
                market_data={"regime": "bull"}
            )

            record_id = store.store_analysis(record)
            assert record_id > 0
        finally:
            cleanup_db_files(tmpdir)

    def test_store_multiple_records(self):
        """测试存储多条记录"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            store = AnalysisHistoryStore(db_path=str(db_path))

            for i in range(5):
                record = AnalysisRecord(
                    stock_code=f"6005{i}.SH",
                    stock_name=f"股票{i}",
                    analysis_time=datetime.now().isoformat(),
                    overall_signal="buy",
                    overall_score=70 + i
                )
                store.store_analysis(record)

            # 验证可以查询
            history = store.get_history(limit=10)
            assert len(history) == 5
        finally:
            cleanup_db_files(tmpdir)


class TestAnalysisHistoryQuery:
    """测试查询功能"""

    def test_get_history_all(self):
        """测试获取所有历史"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            store = AnalysisHistoryStore(db_path=str(db_path))

            # 添加一些记录
            for i in range(3):
                record = AnalysisRecord(
                    stock_code=f"6005{i}.SH",
                    stock_name=f"股票{i}",
                    analysis_time=datetime.now().isoformat(),
                    overall_signal="buy",
                    overall_score=70 + i
                )
                store.store_analysis(record)

            history = store.get_history()
            assert len(history) == 3
        finally:
            cleanup_db_files(tmpdir)

    def test_get_history_with_limit(self):
        """测试获取历史（带限制）"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            store = AnalysisHistoryStore(db_path=str(db_path))

            # 添加5条记录
            for i in range(5):
                record = AnalysisRecord(
                    stock_code=f"6005{i}.SH",
                    stock_name=f"股票{i}",
                    analysis_time=datetime.now().isoformat(),
                    overall_signal="buy",
                    overall_score=70 + i
                )
                store.store_analysis(record)

            history = store.get_history(limit=3)
            assert len(history) == 3
        finally:
            cleanup_db_files(tmpdir)

    def test_get_history_with_offset(self):
        """测试获取历史（带偏移）"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            store = AnalysisHistoryStore(db_path=str(db_path))

            # 添加5条记录
            for i in range(5):
                record = AnalysisRecord(
                    stock_code=f"6005{i}.SH",
                    stock_name=f"股票{i}",
                    analysis_time=datetime.now().isoformat(),
                    overall_signal="buy",
                    overall_score=70 + i
                )
                store.store_analysis(record)

            history = store.get_history(limit=2, offset=2)
            assert len(history) == 2
        finally:
            cleanup_db_files(tmpdir)

    def test_get_history_filter_by_stock(self):
        """测试按股票代码筛选"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            store = AnalysisHistoryStore(db_path=str(db_path))

            # 添加不同股票的记录
            for code in ["600519.SH", "000001.SZ", "600519.SH"]:
                record = AnalysisRecord(
                    stock_code=code,
                    stock_name="测试股票",
                    analysis_time=datetime.now().isoformat(),
                    overall_signal="buy",
                    overall_score=75
                )
                store.store_analysis(record)

            history = store.get_history(stock_code="600519.SH")
            assert len(history) == 2
            for h in history:
                assert h.stock_code == "600519.SH"
        finally:
            cleanup_db_files(tmpdir)

    def test_get_history_filter_by_signal(self):
        """测试按信号筛选"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            store = AnalysisHistoryStore(db_path=str(db_path))

            # 添加不同信号的记录
            for signal in ["buy", "sell", "buy"]:
                record = AnalysisRecord(
                    stock_code="600519.SH",
                    stock_name="测试股票",
                    analysis_time=datetime.now().isoformat(),
                    overall_signal=signal,
                    overall_score=75
                )
                store.store_analysis(record)

            history = store.get_history(signal="buy")
            assert len(history) == 2
            for h in history:
                assert h.overall_signal == "buy"
        finally:
            cleanup_db_files(tmpdir)

    def test_get_latest_analysis(self):
        """测试获取最新分析"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            store = AnalysisHistoryStore(db_path=str(db_path))

            # 添加记录
            record1 = AnalysisRecord(
                stock_code="600519.SH",
                stock_name="贵州茅台",
                analysis_time=datetime.now().isoformat(),
                overall_signal="buy",
                overall_score=75
            )
            store.store_analysis(record1)

            record2 = AnalysisRecord(
                stock_code="600519.SH",
                stock_name="贵州茅台",
                analysis_time=datetime.now().isoformat(),
                overall_signal="sell",
                overall_score=65
            )
            store.store_analysis(record2)

            latest = store.get_latest_analysis("600519.SH")
            assert latest is not None
            assert latest.overall_signal == "sell"  # 最新的
        finally:
            cleanup_db_files(tmpdir)

    def test_get_latest_analysis_not_found(self):
        """测试获取不存在的股票分析"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            store = AnalysisHistoryStore(db_path=str(db_path))

            latest = store.get_latest_analysis("999999.SH")
            assert latest is None
        finally:
            cleanup_db_files(tmpdir)

    def test_get_statistics_empty(self):
        """测试空数据库的统计"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            store = AnalysisHistoryStore(db_path=str(db_path))

            stats = store.get_statistics()
            assert stats["total_records"] == 0
            assert stats["signal_counts"] == {}
            assert stats["top_stocks"] == []
            assert stats["last_analysis"] is None
        finally:
            cleanup_db_files(tmpdir)

    def test_get_statistics(self):
        """测试数据库统计"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            store = AnalysisHistoryStore(db_path=str(db_path))

            # 添加记录
            for i in range(5):
                signal = "buy" if i % 2 == 0 else "sell"
                record = AnalysisRecord(
                    stock_code=f"6005{i}.SH",
                    stock_name=f"股票{i}",
                    analysis_time=datetime.now().isoformat(),
                    overall_signal=signal,
                    overall_score=70 + i
                )
                store.store_analysis(record)

            stats = store.get_statistics()
            assert stats["total_records"] == 5
            assert len(stats["signal_counts"]) == 2
            assert "buy" in stats["signal_counts"]
            assert "sell" in stats["signal_counts"]
            assert len(stats["top_stocks"]) > 0
            assert stats["last_analysis"] is not None
        finally:
            cleanup_db_files(tmpdir)


class TestAnalysisHistoryDelete:
    """测试删除功能"""

    def test_delete_old_records(self):
        """测试删除旧记录"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            store = AnalysisHistoryStore(db_path=str(db_path))

            # 添加记录
            for i in range(10):
                record = AnalysisRecord(
                    stock_code="600519.SH",
                    stock_name="贵州茅台",
                    analysis_time=datetime.now().isoformat(),
                    overall_signal="buy",
                    overall_score=75
                )
                store.store_analysis(record)

            # 删除超过30天的记录（应该没有）
            deleted = store.delete_old_records(days=30)
            assert deleted == 0

            # 验证记录还在
            history = store.get_history()
            assert len(history) == 10
        finally:
            cleanup_db_files(tmpdir)

    def test_delete_stock_records(self):
        """测试删除指定股票的记录"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            store = AnalysisHistoryStore(db_path=str(db_path))

            # 添加不同股票的记录
            for code in ["600519.SH", "000001.SZ", "600519.SH", "000001.SZ"]:
                record = AnalysisRecord(
                    stock_code=code,
                    stock_name="测试股票",
                    analysis_time=datetime.now().isoformat(),
                    overall_signal="buy",
                    overall_score=75
                )
                store.store_analysis(record)

            # 删除 600519.SH 的记录
            deleted = store.clear_stock("600519.SH")
            assert deleted == 2

            # 验证只剩 000001.SZ 的记录
            history = store.get_history()
            assert len(history) == 2
            for h in history:
                assert h.stock_code == "000001.SZ"
        finally:
            cleanup_db_files(tmpdir)

    def test_delete_nonexistent_stock(self):
        """测试删除不存在的股票"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            store = AnalysisHistoryStore(db_path=str(db_path))

            deleted = store.clear_stock("999999.SH")
            assert deleted == 0
        finally:
            cleanup_db_files(tmpdir)


class TestAnalysisHistorySingleton:
    """测试单例模式"""

    def test_get_singleton(self):
        """测试获取单例"""
        # 清除全局单例
        import core.analysis_history
        core.analysis_history._instance = None

        store1 = get_analysis_history_store()
        store2 = get_analysis_history_store()
        assert store1 is store2

        # 清理
        core.analysis_history._instance = None

    def test_singleton_persistence(self):
        """测试单例持久化"""
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"

            # 清除全局单例
            import core.analysis_history
            core.analysis_history._instance = None

            store1 = get_analysis_history_store(db_path=str(db_path))
            store2 = get_analysis_history_store(db_path=str(db_path))
            assert store1 is store2

            # 清理
            core.analysis_history._instance = None
        finally:
            cleanup_db_files(tmpdir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
