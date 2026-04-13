# -*- coding: utf-8 -*-
"""
反思记录持久化

使用 SQLite 存储反思记录，实现长期记忆。
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from core.schemas import ReflectionRecord, ErrorType


class ReflectionStorage:
    """
    反思记录存储

    使用 SQLite 持久化存储反思记录，支持：
    - 保存反思记录
    - 查询反思记录（按股票、错误类型、时间范围）
    - 删除过期记录
    """

    def __init__(self, db_path: str = "data/reflections.db"):
        """
        初始化存储

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            # 尝试添加 symbol 列（如果不存在）
            try:
                conn.execute("ALTER TABLE reflections ADD COLUMN symbol TEXT")
            except:
                pass  # 列可能已存在

            conn.execute("""
                CREATE TABLE IF NOT EXISTS reflections (
                    reflection_id TEXT PRIMARY KEY,
                    trade_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    loss_amount REAL NOT NULL,
                    loss_ratio REAL NOT NULL,
                    error_type TEXT NOT NULL,
                    analysis TEXT NOT NULL,
                    lesson TEXT NOT NULL,
                    avoid_action TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT
                )
            """)

            # 创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trade_id ON reflections(trade_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON reflections(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_error_type ON reflections(error_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON reflections(timestamp)")

            conn.commit()

    def save_reflection(self, reflection: ReflectionRecord, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        保存反思记录

        Args:
            reflection: 反思记录
            metadata: 额外元数据（JSON 格式）

        Returns:
            bool: 是否保存成功
        """
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO reflections (
                        reflection_id, trade_id, symbol, loss_amount, loss_ratio,
                        error_type, analysis, lesson, avoid_action,
                        timestamp, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    reflection.reflection_id,
                    reflection.trade_id,
                    reflection.symbol,
                    reflection.loss_amount,
                    reflection.loss_ratio,
                    reflection.error_type.value,
                    reflection.analysis,
                    reflection.lesson,
                    reflection.avoid_action,
                    reflection.timestamp.isoformat(),
                    json.dumps(metadata) if metadata else None,
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"[ReflectionStorage] 保存失败: {e}")
            return False

    def get_reflection(self, reflection_id: str) -> Optional[ReflectionRecord]:
        """
        获取指定反思记录

        Args:
            reflection_id: 反思ID

        Returns:
            Optional[ReflectionRecord]: 反思记录
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM reflections WHERE reflection_id = ?",
                (reflection_id,)
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_reflection(row)
            return None

    def get_all_reflections(self, limit: int = 100) -> List[ReflectionRecord]:
        """
        获取所有反思记录

        Args:
            limit: 返回数量限制

        Returns:
            List[ReflectionRecord]: 反思记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM reflections ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            return [self._row_to_reflection(row) for row in cursor.fetchall()]

    def get_reflections_by_trade_id(self, trade_id: str) -> List[ReflectionRecord]:
        """
        获取指定交易的反思记录

        Args:
            trade_id: 交易ID

        Returns:
            List[ReflectionRecord]: 反思记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM reflections WHERE trade_id = ? ORDER BY timestamp DESC",
                (trade_id,)
            )
            return [self._row_to_reflection(row) for row in cursor.fetchall()]

    def get_reflections_by_symbol(self, symbol: str, limit: int = 20) -> List[ReflectionRecord]:
        """
        获取指定股票的反思记录

        Args:
            symbol: 股票代码
            limit: 返回数量限制

        Returns:
            List[ReflectionRecord]: 反思记录列表
        """
        with self._get_connection() as conn:
            # 直接通过 symbol 列查询（优先）
            try:
                cursor = conn.execute(
                    "SELECT * FROM reflections WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?",
                    (symbol, limit,)
                )
                reflections = [self._row_to_reflection(row) for row in cursor.fetchall()]
                if reflections:
                    return reflections
            except:
                pass  # symbol 列可能不存在，回退到旧方法

            # 回退：查询所有记录并过滤
            cursor = conn.execute(
                "SELECT * FROM reflections ORDER BY timestamp DESC LIMIT ?",
                (limit * 10,)
            )

            # 从 metadata 中提取股票代码或从 symbol 列获取
            reflections = []
            for row in cursor.fetchall():
                record = self._row_to_reflection(row)
                if record.symbol == symbol:
                    reflections.append(record)
                    if len(reflections) >= limit:
                        break

            return reflections

    def get_reflections_by_error_type(self, error_type: ErrorType, limit: int = 20) -> List[ReflectionRecord]:
        """
        获取指定错误类型的反思记录

        Args:
            error_type: 错误类型
            limit: 返回数量限制

        Returns:
            List[ReflectionRecord]: 反思记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM reflections WHERE error_type = ? ORDER BY timestamp DESC LIMIT ?",
                (error_type.value, limit,)
            )
            return [self._row_to_reflection(row) for row in cursor.fetchall()]

    def get_recent_reflections(self, days: int = 7, limit: int = 50) -> List[ReflectionRecord]:
        """
        获取最近N天的反思记录

        Args:
            days: 天数
            limit: 返回数量限制

        Returns:
            List[ReflectionRecord]: 反思记录列表
        """
        cutoff_date = datetime.now().timestamp() - (days * 86400)

        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM reflections
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (datetime.fromtimestamp(cutoff_date).isoformat(), limit))

            return [self._row_to_reflection(row) for row in cursor.fetchall()]

    def delete_reflection(self, reflection_id: str) -> bool:
        """
        删除指定反思记录

        Args:
            reflection_id: 反思ID

        Returns:
            bool: 是否删除成功
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "DELETE FROM reflections WHERE reflection_id = ?",
                    (reflection_id,)
                )
                conn.commit()
                return True
        except Exception as e:
            print(f"[ReflectionStorage] 删除失败: {e}")
            return False

    def delete_old_reflections(self, days: int = 90) -> int:
        """
        删除旧反思记录

        Args:
            days: 保留天数

        Returns:
            int: 删除的记录数
        """
        cutoff_date = datetime.now().timestamp() - (days * 86400)

        with self._get_connection() as conn:
            cursor = conn.execute("""
                DELETE FROM reflections
                WHERE timestamp < ?
            """, (datetime.fromtimestamp(cutoff_date).isoformat(),))

            deleted = cursor.rowcount
            conn.commit()
            return deleted

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        with self._get_connection() as conn:
            # 总记录数
            cursor = conn.execute("SELECT COUNT(*) FROM reflections")
            total = cursor.fetchone()[0]

            # 按错误类型统计
            cursor = conn.execute("""
                SELECT error_type, COUNT(*) as count
                FROM reflections
                GROUP BY error_type
            """)
            by_error_type = {row[0]: row[1] for row in cursor.fetchall()}

            # 最近的记录
            cursor = conn.execute("""
                SELECT timestamp, loss_amount
                FROM reflections
                ORDER BY timestamp DESC
                LIMIT 5
            """)
            recent = [
                {"timestamp": row[0], "loss_amount": row[1]}
                for row in cursor.fetchall()
            ]

            return {
                "total_reflections": total,
                "by_error_type": by_error_type,
                "recent": recent,
            }

    @staticmethod
    def _row_to_reflection(row: sqlite3.Row) -> ReflectionRecord:
        """将数据库行转换为 ReflectionRecord"""
        # 兼容旧数据库（没有 symbol 列）
        try:
            symbol = row["symbol"]
        except IndexError:
            # symbol 列不存在，从 trade_id 提取
            trade_id = row["trade_id"]
            if "_" in trade_id:
                symbol = trade_id.split("_")[0]
            else:
                symbol = trade_id[:6] if len(trade_id) > 6 else trade_id

        return ReflectionRecord(
            reflection_id=row["reflection_id"],
            trade_id=row["trade_id"],
            symbol=symbol,
            loss_amount=row["loss_amount"],
            loss_ratio=row["loss_ratio"],
            error_type=ErrorType(row["error_type"]),
            analysis=row["analysis"],
            lesson=row["lesson"],
            avoid_action=row["avoid_action"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )

    def export_to_json(self, file_path: str) -> bool:
        """
        导出反思记录到 JSON 文件

        Args:
            file_path: 输出文件路径

        Returns:
            bool: 是否导出成功
        """
        try:
            reflections = self.get_all_reflections(limit=1000)
            data = [
                {
                    "reflection_id": r.reflection_id,
                    "trade_id": r.trade_id,
                    "symbol": r.symbol,
                    "loss_amount": r.loss_amount,
                    "loss_ratio": r.loss_ratio,
                    "error_type": r.error_type.value,
                    "analysis": r.analysis,
                    "lesson": r.lesson,
                    "avoid_action": r.avoid_action,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in reflections
            ]

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            print(f"[ReflectionStorage] 导出失败: {e}")
            return False