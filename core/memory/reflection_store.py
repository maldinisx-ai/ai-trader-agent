# -*- coding: utf-8 -*-
"""
反思记录存储

负责反思记录的持久化和查询。
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from core.schemas import ErrorType


logger = logging.getLogger(__name__)


# ============================================
# 数据库表定义
# ============================================

REFLECTIONS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS reflections (
    reflection_id TEXT PRIMARY KEY,
    trade_id TEXT NOT NULL,
    error_type TEXT NOT NULL CHECK (error_type IN ('entry', 'exit', 'position', 'timing')),
    analysis TEXT NOT NULL,
    lesson TEXT NOT NULL,
    avoid_action TEXT NOT NULL,
    confidence REAL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    timestamp TEXT NOT NULL,
    FOREIGN KEY (trade_id) REFERENCES trade_history(trade_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_reflections_trade_id ON reflections(trade_id);
CREATE INDEX IF NOT EXISTS idx_reflections_error_type ON reflections(error_type);
CREATE INDEX IF NOT EXISTS idx_reflections_timestamp ON reflections(timestamp);
"""


# ============================================
# 反思记录存储
# ============================================

class ReflectionStore:
    """
    反思记录存储

    提供反思记录的 CRUD 操作和查询功能。
    """

    def __init__(self, db_path: str = "data/trading.db"):
        """
        初始化反思记录存储

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """初始化数据库"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db = sqlite3.connect(self.db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row

        # 检查表是否存在，如果不存在则创建
        cursor = self.db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reflections'")
        if cursor.fetchone() is None:
            self.db.executescript(REFLECTIONS_TABLE_SCHEMA)
            logger.info(f"[ReflectionStore] 创建反思记录表: {self.db_path}")
        else:
            logger.debug(f"[ReflectionStore] 使用现有反思记录表: {self.db_path}")

        self.db.commit()

    def record_reflection(
        self,
        trade_id: str,
        error_type: ErrorType,
        analysis: str,
        lesson: str,
        avoid_action: str,
        confidence: float = 0.0,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        记录反思

        Args:
            trade_id: 关联交易ID
            error_type: 错误类型
            analysis: 分析内容
            lesson: 经验教训
            avoid_action: 避免措施
            confidence: 置信度 (0-1)
            timestamp: 时间戳

        Returns:
            bool: 是否记录成功
        """
        reflection_id = f"ref_{trade_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        if timestamp is None:
            timestamp = datetime.now()

        try:
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT INTO reflections (
                    reflection_id, trade_id, error_type, analysis,
                    lesson, avoid_action, confidence, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                reflection_id,
                trade_id,
                error_type.value,
                analysis,
                lesson,
                avoid_action,
                confidence,
                timestamp.isoformat(),
            ))
            self.db.commit()
            logger.debug(f"[ReflectionStore] 记录反思: {reflection_id}")
            return True

        except sqlite3.IntegrityError as e:
            logger.warning(f"[ReflectionStore] 反思ID或交易ID冲突: {reflection_id} - {e}")
            return False
        except Exception as e:
            logger.error(f"[ReflectionStore] 记录反思失败: {e}", exc_info=True)
            return False

    def get_reflection(self, reflection_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单条反思记录

        Args:
            reflection_id: 反思ID

        Returns:
            Optional[Dict[str, Any]]: 反思记录，不存在返回 None
        """
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM reflections WHERE reflection_id = ?", (reflection_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return self._row_to_dict(row)

    def get_reflections_by_trade_id(self, trade_id: str) -> List[Dict[str, Any]]:
        """
        获取指定交易的所有反思记录

        Args:
            trade_id: 交易ID

        Returns:
            List[Dict[str, Any]]: 反思记录列表
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT * FROM reflections
            WHERE trade_id = ?
            ORDER BY timestamp DESC
        """, (trade_id,))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_reflections_by_error_type(
        self,
        error_type: ErrorType,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取指定错误类型的反思记录

        Args:
            error_type: 错误类型
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 反思记录列表
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT * FROM reflections
            WHERE error_type = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (error_type.value, limit))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_reflections_by_symbol(
        self,
        symbol: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取指定股票的反思记录（通过关联交易）

        Args:
            symbol: 股票代码
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 反思记录列表
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT r.* FROM reflections r
            JOIN trade_history t ON r.trade_id = t.trade_id
            WHERE t.symbol = ?
            ORDER BY r.timestamp DESC
            LIMIT ?
        """, (symbol, limit))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_recent_reflections(
        self,
        hours: int = 24,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取最近的反思记录

        Args:
            hours: 小时数
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 反思记录列表
        """
        start_time = datetime.now() - timedelta(hours=hours)

        cursor = self.db.cursor()
        cursor.execute("""
            SELECT * FROM reflections
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (start_time.isoformat(), limit))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_all_reflections(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        获取所有反思记录

        Args:
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[Dict[str, Any]]: 反思记录列表
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT * FROM reflections
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_error_type_statistics(self) -> Dict[str, Any]:
        """
        获取错误类型统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        cursor = self.db.cursor()

        # 总数
        cursor.execute("SELECT COUNT(*) FROM reflections")
        total = cursor.fetchone()[0]

        # 各类型统计
        cursor.execute("""
            SELECT error_type, COUNT(*) as count
            FROM reflections
            GROUP BY error_type
        """)

        type_stats = {row["error_type"]: row["count"] for row in cursor.fetchall()}

        # 计算比例
        type_ratios = {
            error_type: count / total if total > 0 else 0.0
            for error_type, count in type_stats.items()
        }

        return {
            "total": total,
            "by_type": type_stats,
            "by_type_ratio": type_ratios,
        }

    def get_lessons_by_error_type(self, error_type: ErrorType) -> List[str]:
        """
        获取指定错误类型的所有教训

        Args:
            error_type: 错误类型

        Returns:
            List[str]: 教训列表
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT DISTINCT lesson
            FROM reflections
            WHERE error_type = ?
        """, (error_type.value,))

        return [row["lesson"] for row in cursor.fetchall()]

    def get_avoid_actions_by_error_type(self, error_type: ErrorType) -> List[str]:
        """
        获取指定错误类型的所有避免措施

        Args:
            error_type: 错误类型

        Returns:
            List[str]: 避免措施列表
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT DISTINCT avoid_action
            FROM reflections
            WHERE error_type = ?
        """, (error_type.value,))

        return [row["avoid_action"] for row in cursor.fetchall()]

    def count_reflections(self, error_type: Optional[ErrorType] = None) -> int:
        """
        统计反思数量

        Args:
            error_type: 错误类型（可选）

        Returns:
            int: 反思数量
        """
        cursor = self.db.cursor()

        if error_type:
            cursor.execute(
                "SELECT COUNT(*) FROM reflections WHERE error_type = ?",
                (error_type.value,)
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM reflections")

        return cursor.fetchone()[0]

    def delete_reflection(self, reflection_id: str) -> bool:
        """
        删除反思记录

        Args:
            reflection_id: 反思ID

        Returns:
            bool: 是否删除成功
        """
        try:
            cursor = self.db.cursor()
            cursor.execute("DELETE FROM reflections WHERE reflection_id = ?", (reflection_id,))
            self.db.commit()
            logger.debug(f"[ReflectionStore] 删除反思: {reflection_id}")
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[ReflectionStore] 删除反思失败: {e}", exc_info=True)
            return False

    def delete_reflections_by_trade_id(self, trade_id: str) -> int:
        """
        删除指定交易的所有反思记录

        Args:
            trade_id: 交易ID

        Returns:
            int: 删除的记录数
        """
        try:
            cursor = self.db.cursor()
            cursor.execute("DELETE FROM reflections WHERE trade_id = ?", (trade_id,))
            self.db.commit()
            deleted = cursor.rowcount
            logger.debug(f"[ReflectionStore] 删除交易 {trade_id} 的 {deleted} 条反思")
            return deleted
        except Exception as e:
            logger.error(f"[ReflectionStore] 删除反思失败: {e}", exc_info=True)
            return 0

    def clear_reflections(self) -> None:
        """清空所有反思记录"""
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM reflections")
        self.db.commit()
        logger.info("[ReflectionStore] 清空所有反思记录")

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """将数据库行转换为字典"""
        return {
            "reflection_id": row["reflection_id"],
            "trade_id": row["trade_id"],
            "error_type": row["error_type"],
            "analysis": row["analysis"],
            "lesson": row["lesson"],
            "avoid_action": row["avoid_action"],
            "confidence": row["confidence"],
            "timestamp": row["timestamp"],
        }

    def close(self) -> None:
        """关闭数据库连接"""
        if hasattr(self, 'db'):
            self.db.close()
            logger.debug("[ReflectionStore] 数据库连接已关闭")