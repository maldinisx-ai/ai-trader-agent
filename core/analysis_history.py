# -*- coding: utf-8 -*-
"""
分析历史记录存储

保存和查询股票分析历史记录。
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AnalysisRecord(BaseModel):
    """分析记录"""
    id: int = Field(default=None, description="记录ID")
    stock_code: str = Field(..., description="股票代码")
    stock_name: str = Field(..., description="股票名称")
    analysis_time: str = Field(..., description="分析时间")
    overall_signal: str = Field(..., description="总体信号")
    overall_score: int = Field(..., description="总体得分")
    current_price: Optional[float] = Field(None, description="当前价格")
    change_pct: Optional[float] = Field(None, description="涨跌幅")
    active_strategies: List[str] = Field(default_factory=list, description="激活的策略")
    signals: List[Dict[str, Any]] = Field(default_factory=list, description="策略信号")
    market_data: Optional[Dict[str, Any]] = Field(None, description="市场数据摘要")


class AnalysisHistoryStore:
    """分析历史记录存储"""

    def __init__(self, db_path: str = "data/analysis_history.db"):
        """
        初始化存储

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT NOT NULL,
                    analysis_time TEXT NOT NULL,
                    overall_signal TEXT NOT NULL,
                    overall_score INTEGER NOT NULL,
                    current_price REAL,
                    change_pct REAL,
                    active_strategies TEXT,
                    signals TEXT,
                    market_data TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 创建索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_stock_code
                ON analysis_history(stock_code)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_analysis_time
                ON analysis_history(analysis_time)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_overall_signal
                ON analysis_history(overall_signal)
            """)

            conn.commit()

    def store_analysis(self, record: AnalysisRecord) -> int:
        """
        存储分析记录

        Args:
            record: 分析记录

        Returns:
            记录ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO analysis_history (
                    stock_code, stock_name, analysis_time, overall_signal, overall_score,
                    current_price, change_pct, active_strategies, signals, market_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.stock_code,
                record.stock_name,
                record.analysis_time,
                record.overall_signal,
                record.overall_score,
                record.current_price,
                record.change_pct,
                json.dumps(record.active_strategies, ensure_ascii=False),
                json.dumps(record.signals, ensure_ascii=False),
                json.dumps(record.market_data, ensure_ascii=False) if record.market_data else None,
            ))

            record_id = cursor.lastrowid
            conn.commit()

            logger.debug(f"存储分析记录: {record.stock_code} -> {record.overall_signal}")
            return record_id

    def get_history(
        self,
        stock_code: Optional[str] = None,
        signal: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AnalysisRecord]:
        """
        获取分析历史

        Args:
            stock_code: 可选，股票代码筛选
            signal: 可选，信号筛选
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            分析记录列表
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 构建查询
            query = "SELECT * FROM analysis_history WHERE 1=1"
            params = []

            if stock_code:
                query += " AND stock_code = ?"
                params.append(stock_code)

            if signal:
                query += " AND overall_signal = ?"
                params.append(signal)

            query += " ORDER BY analysis_time DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            records = []
            for row in rows:
                records.append(AnalysisRecord(
                    id=row["id"],
                    stock_code=row["stock_code"],
                    stock_name=row["stock_name"],
                    analysis_time=row["analysis_time"],
                    overall_signal=row["overall_signal"],
                    overall_score=row["overall_score"],
                    current_price=row["current_price"],
                    change_pct=row["change_pct"],
                    active_strategies=json.loads(row["active_strategies"]) if row["active_strategies"] else [],
                    signals=json.loads(row["signals"]) if row["signals"] else [],
                    market_data=json.loads(row["market_data"]) if row["market_data"] else None,
                ))

            return records

    def get_latest_analysis(self, stock_code: str) -> Optional[AnalysisRecord]:
        """
        获取股票的最新分析

        Args:
            stock_code: 股票代码

        Returns:
            最新分析记录，如果不存在返回 None
        """
        records = self.get_history(stock_code=stock_code, limit=1)
        return records[0] if records else None

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计数据
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 总记录数
            cursor.execute("SELECT COUNT(*) FROM analysis_history")
            total = cursor.fetchone()[0]

            # 各信号数量
            cursor.execute("""
                SELECT overall_signal, COUNT(*) as count
                FROM analysis_history
                GROUP BY overall_signal
            """)
            signal_counts = {row[0]: row[1] for row in cursor.fetchall()}

            # 各股票分析次数
            cursor.execute("""
                SELECT stock_code, COUNT(*) as count
                FROM analysis_history
                GROUP BY stock_code
                ORDER BY count DESC
                LIMIT 10
            """)
            top_stocks = [{"code": row[0], "count": row[1]} for row in cursor.fetchall()]

            # 最近分析时间
            cursor.execute("SELECT MAX(analysis_time) FROM analysis_history")
            last_analysis = cursor.fetchone()[0]

            return {
                "total_records": total,
                "signal_counts": signal_counts,
                "top_stocks": top_stocks,
                "last_analysis": last_analysis,
            }

    def delete_old_records(self, days: int = 30) -> int:
        """
        删除旧记录

        Args:
            days: 保留天数

        Returns:
            删除的记录数
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM analysis_history
                WHERE datetime(analysis_time) < datetime('now', '-' || ? || ' days')
            """, (days,))

            deleted = cursor.rowcount
            conn.commit()

            logger.info(f"删除 {deleted} 条旧记录（超过 {days} 天）")
            return deleted

    def clear_stock(self, stock_code: str) -> int:
        """
        清除指定股票的所有记录

        Args:
            stock_code: 股票代码

        Returns:
            删除的记录数
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("DELETE FROM analysis_history WHERE stock_code = ?", (stock_code,))
            deleted = cursor.rowcount
            conn.commit()

            logger.info(f"删除 {stock_code} 的 {deleted} 条记录")
            return deleted


# 全局单例
_instance: Optional[AnalysisHistoryStore] = None


def get_analysis_history_store(db_path: str = "data/analysis_history.db") -> AnalysisHistoryStore:
    """
    获取分析历史存储单例

    Args:
        db_path: 数据库文件路径

    Returns:
        AnalysisHistoryStore 实例
    """
    global _instance
    if _instance is None:
        _instance = AnalysisHistoryStore(db_path=db_path)
    return _instance
