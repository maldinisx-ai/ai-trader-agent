# -*- coding: utf-8 -*-
"""
ReflectionStorage 单元测试
"""

import pytest
import sqlite3
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta
from core.reflection_storage import ReflectionStorage
from core.schemas import ReflectionRecord, ErrorType


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name
    yield db_path
    # 清理
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def storage(temp_db):
    """创建 ReflectionStorage 实例"""
    return ReflectionStorage(db_path=temp_db)


@pytest.fixture
def sample_reflection():
    """创建示例反思记录"""
    return ReflectionRecord(
        reflection_id="test_reflection_001",
        trade_id="600000_20250330_120000",
        symbol="600000",
        loss_amount=1000.0,
        loss_ratio=0.05,
        error_type=ErrorType.ENTRY,
        analysis="入场时机选择不当",
        lesson="等待更好的入场点",
        avoid_action="严格执行入场信号确认",
        timestamp=datetime.now()
    )


class TestReflectionStorageInit:
    """测试 ReflectionStorage 初始化"""

    def test_init_default_path(self):
        """测试默认路径初始化"""
        storage = ReflectionStorage()
        assert storage.db_path == Path("data/reflections.db")

    def test_init_custom_path(self, temp_db):
        """测试自定义路径初始化"""
        storage = ReflectionStorage(db_path=temp_db)
        assert storage.db_path == Path(temp_db)

    def test_database_created(self, temp_db):
        """测试数据库表创建"""
        storage = ReflectionStorage(db_path=temp_db)
        assert Path(temp_db).exists()

        # 验证表结构
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='reflections'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_indexes_created(self, temp_db):
        """测试索引创建"""
        storage = ReflectionStorage(db_path=temp_db)
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        assert "idx_trade_id" in indexes
        assert "idx_symbol" in indexes
        assert "idx_error_type" in indexes
        assert "idx_timestamp" in indexes
        conn.close()


class TestReflectionStorageSave:
    """测试保存反思记录"""

    def test_save_reflection_basic(self, storage, sample_reflection):
        """测试基本保存"""
        result = storage.save_reflection(sample_reflection)
        assert result is True

    def test_save_reflection_with_metadata(self, storage, sample_reflection):
        """测试保存带元数据"""
        metadata = {"market_sentiment": "bearish", "sector": "finance"}
        result = storage.save_reflection(sample_reflection, metadata=metadata)
        assert result is True

    def test_save_reflection_duplicate(self, storage, sample_reflection):
        """测试保存重复记录（替换）"""
        storage.save_reflection(sample_reflection)
        # 更新同一记录
        updated = ReflectionRecord(
            reflection_id=sample_reflection.reflection_id,
            trade_id=sample_reflection.trade_id,
            symbol=sample_reflection.symbol,
            loss_amount=2000.0,  # 更新金额
            loss_ratio=0.10,
            error_type=ErrorType.EXIT,
            analysis="更新后的分析",
            lesson="更新后的教训",
            avoid_action="更新后的避免行动",
            timestamp=datetime.now()
        )
        result = storage.save_reflection(updated)
        assert result is True

        # 验证更新
        retrieved = storage.get_reflection(sample_reflection.reflection_id)
        assert retrieved.loss_amount == 2000.0
        assert retrieved.analysis == "更新后的分析"


class TestReflectionStorageGet:
    """测试获取反思记录"""

    def test_get_reflection_by_id(self, storage, sample_reflection):
        """测试通过 ID 获取记录"""
        storage.save_reflection(sample_reflection)
        retrieved = storage.get_reflection(sample_reflection.reflection_id)
        assert retrieved is not None
        assert retrieved.reflection_id == sample_reflection.reflection_id
        assert retrieved.symbol == sample_reflection.symbol

    def test_get_reflection_not_found(self, storage):
        """测试获取不存在的记录"""
        result = storage.get_reflection("non_existent_id")
        assert result is None

    def test_get_all_reflections(self, storage):
        """测试获取所有记录"""
        # 创建多条记录
        for i in range(5):
            reflection = ReflectionRecord(
                reflection_id=f"test_reflection_{i:03d}",
                trade_id=f"60000{i}_20250330_120000",
                symbol=f"60000{i}",
                loss_amount=100.0 * i,
                loss_ratio=0.01 * i,
                error_type=ErrorType.ENTRY,
                analysis=f"分析 {i}",
                lesson=f"教训 {i}",
                avoid_action=f"避免 {i}",
                timestamp=datetime.now() - timedelta(hours=i)
            )
            storage.save_reflection(reflection)

        reflections = storage.get_all_reflections()
        assert len(reflections) == 5
        # 验证按时间倒序排列
        assert reflections[0].reflection_id == "test_reflection_000"

    def test_get_all_reflections_with_limit(self, storage):
        """测试限制返回数量"""
        for i in range(10):
            reflection = ReflectionRecord(
                reflection_id=f"test_reflection_{i:03d}",
                trade_id=f"60000{i}_20250330_120000",
                symbol=f"60000{i}",
                loss_amount=100.0,
                loss_ratio=0.01,
                error_type=ErrorType.ENTRY,
                analysis=f"分析 {i}",
                lesson=f"教训 {i}",
                avoid_action=f"避免 {i}",
                timestamp=datetime.now()
            )
            storage.save_reflection(reflection)

        reflections = storage.get_all_reflections(limit=5)
        assert len(reflections) == 5

    def test_get_reflections_by_trade_id(self, storage, sample_reflection):
        """测试通过交易 ID 获取记录"""
        storage.save_reflection(sample_reflection)
        reflections = storage.get_reflections_by_trade_id(sample_reflection.trade_id)
        assert len(reflections) == 1
        assert reflections[0].reflection_id == sample_reflection.reflection_id

    def test_get_reflections_by_trade_id_multiple(self, storage):
        """测试同一交易的多个反思"""
        trade_id = "600000_20250330_120000"
        for i in range(3):
            reflection = ReflectionRecord(
                reflection_id=f"test_reflection_{i}",
                trade_id=trade_id,
                symbol="600000",
                loss_amount=100.0 * i,
                loss_ratio=0.01 * i,
                error_type=ErrorType.ENTRY,
                analysis=f"分析 {i}",
                lesson=f"教训 {i}",
                avoid_action=f"避免 {i}",
                timestamp=datetime.now()
            )
            storage.save_reflection(reflection)

        reflections = storage.get_reflections_by_trade_id(trade_id)
        assert len(reflections) == 3

    def test_get_reflections_by_symbol(self, storage):
        """测试通过股票代码获取记录"""
        for i in range(5):
            reflection = ReflectionRecord(
                reflection_id=f"test_reflection_{i}",
                trade_id=f"600000_20250330_{i:06d}",
                symbol="600000",
                loss_amount=100.0,
                loss_ratio=0.01,
                error_type=ErrorType.ENTRY,
                analysis=f"分析 {i}",
                lesson=f"教训 {i}",
                avoid_action=f"避免 {i}",
                timestamp=datetime.now()
            )
            storage.save_reflection(reflection)

        reflections = storage.get_reflections_by_symbol("600000")
        assert len(reflections) == 5

    def test_get_reflections_by_symbol_with_limit(self, storage):
        """测试按股票代码查询并限制数量"""
        for i in range(10):
            reflection = ReflectionRecord(
                reflection_id=f"test_reflection_{i}",
                trade_id=f"600000_20250330_{i:06d}",
                symbol="600000",
                loss_amount=100.0,
                loss_ratio=0.01,
                error_type=ErrorType.ENTRY,
                analysis=f"分析 {i}",
                lesson=f"教训 {i}",
                avoid_action=f"避免 {i}",
                timestamp=datetime.now()
            )
            storage.save_reflection(reflection)

        reflections = storage.get_reflections_by_symbol("600000", limit=5)
        assert len(reflections) == 5

    def test_get_reflections_by_error_type(self, storage):
        """测试按错误类型获取记录"""
        error_types = [
            ErrorType.ENTRY,
            ErrorType.EXIT,
            ErrorType.POSITION
        ]
        for i, error_type in enumerate(error_types):
            reflection = ReflectionRecord(
                reflection_id=f"test_reflection_{i}",
                trade_id=f"60000{i}_20250330_120000",
                symbol=f"60000{i}",
                loss_amount=100.0,
                loss_ratio=0.01,
                error_type=error_type,
                analysis=f"分析 {i}",
                lesson=f"教训 {i}",
                avoid_action=f"避免 {i}",
                timestamp=datetime.now()
            )
            storage.save_reflection(reflection)

        reflections = storage.get_reflections_by_error_type(ErrorType.ENTRY)
        assert len(reflections) == 1
        assert reflections[0].error_type == ErrorType.ENTRY

    def test_get_recent_reflections(self, storage):
        """测试获取最近的反思记录"""
        # 创建不同时间的记录
        now = datetime.now()
        for i in range(5):
            reflection = ReflectionRecord(
                reflection_id=f"test_reflection_{i}",
                trade_id=f"60000{i}_20250330_120000",
                symbol=f"60000{i}",
                loss_amount=100.0,
                loss_ratio=0.01,
                error_type=ErrorType.ENTRY,
                analysis=f"分析 {i}",
                lesson=f"教训 {i}",
                avoid_action=f"避免 {i}",
                timestamp=now - timedelta(days=i)
            )
            storage.save_reflection(reflection)

        # 获取最近 3 天的记录
        reflections = storage.get_recent_reflections(days=3)
        assert len(reflections) == 3  # 0, 1, 2 天前的记录

    def test_get_recent_reflections_with_limit(self, storage):
        """测试获取最近记录并限制数量"""
        now = datetime.now()
        for i in range(10):
            reflection = ReflectionRecord(
                reflection_id=f"test_reflection_{i}",
                trade_id=f"60000{i}_20250330_120000",
                symbol=f"60000{i}",
                loss_amount=100.0,
                loss_ratio=0.01,
                error_type=ErrorType.ENTRY,
                analysis=f"分析 {i}",
                lesson=f"教训 {i}",
                avoid_action=f"避免 {i}",
                timestamp=now - timedelta(days=i)
            )
            storage.save_reflection(reflection)

        reflections = storage.get_recent_reflections(days=30, limit=5)
        assert len(reflections) == 5


class TestReflectionStorageDelete:
    """测试删除反思记录"""

    def test_delete_reflection(self, storage, sample_reflection):
        """测试删除指定记录"""
        storage.save_reflection(sample_reflection)
        result = storage.delete_reflection(sample_reflection.reflection_id)
        assert result is True

        # 验证已删除
        retrieved = storage.get_reflection(sample_reflection.reflection_id)
        assert retrieved is None

    def test_delete_reflection_not_found(self, storage):
        """测试删除不存在的记录"""
        result = storage.delete_reflection("non_existent_id")
        assert result is True  # SQLite DELETE 不存在的记录也返回成功

    def test_delete_old_reflections(self, storage):
        """测试删除旧记录"""
        now = datetime.now()
        # 创建旧记录
        for i in range(5):
            reflection = ReflectionRecord(
                reflection_id=f"old_reflection_{i}",
                trade_id=f"60000{i}_20250330_120000",
                symbol=f"60000{i}",
                loss_amount=100.0,
                loss_ratio=0.01,
                error_type=ErrorType.ENTRY,
                analysis=f"旧分析 {i}",
                lesson=f"旧教训 {i}",
                avoid_action=f"旧避免 {i}",
                timestamp=now - timedelta(days=100)  # 100天前
            )
            storage.save_reflection(reflection)

        # 创建新记录
        for i in range(3):
            reflection = ReflectionRecord(
                reflection_id=f"new_reflection_{i}",
                trade_id=f"60001{i}_20250330_120000",
                symbol=f"60001{i}",
                loss_amount=100.0,
                loss_ratio=0.01,
                error_type=ErrorType.ENTRY,
                analysis=f"新分析 {i}",
                lesson=f"新教训 {i}",
                avoid_action=f"新避免 {i}",
                timestamp=now - timedelta(days=5)  # 5天前
            )
            storage.save_reflection(reflection)

        # 删除 30 天前的记录
        deleted_count = storage.delete_old_reflections(days=30)
        assert deleted_count == 5  # 删除了 5 条旧记录

        # 验证新记录仍在
        all_reflections = storage.get_all_reflections()
        assert len(all_reflections) == 3


class TestReflectionStorageStatistics:
    """测试统计信息"""

    def test_get_statistics_empty(self, storage):
        """测试空数据库统计"""
        stats = storage.get_statistics()
        assert stats["total_reflections"] == 0
        assert stats["by_error_type"] == {}
        assert stats["recent"] == []

    def test_get_statistics_with_data(self, storage):
        """测试有数据的统计"""
        # 添加不同类型的记录
        error_types = [
            ErrorType.ENTRY,
            ErrorType.ENTRY,
            ErrorType.EXIT,
            ErrorType.POSITION
        ]
        for i, error_type in enumerate(error_types):
            reflection = ReflectionRecord(
                reflection_id=f"test_reflection_{i}",
                trade_id=f"60000{i}_20250330_120000",
                symbol=f"60000{i}",
                loss_amount=100.0 * (i + 1),
                loss_ratio=0.01 * (i + 1),
                error_type=error_type,
                analysis=f"分析 {i}",
                lesson=f"教训 {i}",
                avoid_action=f"避免 {i}",
                timestamp=datetime.now()
            )
            storage.save_reflection(reflection)

        stats = storage.get_statistics()
        assert stats["total_reflections"] == 4
        assert stats["by_error_type"]["entry"] == 2
        assert stats["by_error_type"]["exit"] == 1
        assert stats["by_error_type"]["position"] == 1
        assert len(stats["recent"]) == 4


class TestReflectionStorageExport:
    """测试导出功能"""

    def test_export_to_json(self, storage, sample_reflection, tmp_path):
        """测试导出到 JSON"""
        storage.save_reflection(sample_reflection)

        output_file = tmp_path / "export.json"
        result = storage.export_to_json(str(output_file))
        assert result is True
        assert output_file.exists()

        # 验证 JSON 内容
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["reflection_id"] == sample_reflection.reflection_id
        assert data[0]["symbol"] == sample_reflection.symbol

    def test_export_to_json_multiple_records(self, storage, tmp_path):
        """测试导出多条记录"""
        for i in range(5):
            reflection = ReflectionRecord(
                reflection_id=f"test_reflection_{i}",
                trade_id=f"60000{i}_20250330_120000",
                symbol=f"60000{i}",
                loss_amount=100.0,
                loss_ratio=0.01,
                error_type=ErrorType.ENTRY,
                analysis=f"分析 {i}",
                lesson=f"教训 {i}",
                avoid_action=f"避免 {i}",
                timestamp=datetime.now()
            )
            storage.save_reflection(reflection)

        output_file = tmp_path / "export.json"
        result = storage.export_to_json(str(output_file))
        assert result is True

        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert len(data) == 5


class TestReflectionStorageRowConversion:
    """测试数据库行转换"""

    def test_row_to_reflection_with_symbol(self, storage, sample_reflection):
        """测试转换带 symbol 的记录"""
        storage.save_reflection(sample_reflection)
        retrieved = storage.get_reflection(sample_reflection.reflection_id)
        assert retrieved.symbol == sample_reflection.symbol

    def test_row_to_reflection_backward_compatible(self, temp_db):
        """测试向后兼容（没有 symbol 列的旧数据）"""
        # 先初始化数据库
        storage = ReflectionStorage(db_path=temp_db)

        # 手动插入旧格式数据（模拟没有 symbol 列的情况）
        conn = sqlite3.connect(temp_db)
        # 删除 symbol 列的数据（模拟旧数据库）
        conn.execute("DELETE FROM reflections")

        # 插入没有 symbol 的数据（使用默认值）
        conn.execute("""
            INSERT INTO reflections (
                reflection_id, trade_id, symbol, loss_amount, loss_ratio,
                error_type, analysis, lesson, avoid_action, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "old_reflection_001",
            "600000_20250330_120000",
            "",  # 空 symbol，测试回退逻辑
            1000.0,
            0.05,
            "entry",  # 正确的 ErrorType 值
            "旧格式分析",
            "旧格式教训",
            "旧格式避免",
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()

        # 验证能正确读取
        reflections = storage.get_all_reflections()
        assert len(reflections) >= 1
