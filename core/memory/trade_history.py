# -*- coding: utf-8 -*-
"""
交易历史存储

负责交易记录的持久化和查询。
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from core.schemas import (
    Trade,
    OrderSide,
    SurvivalLevel,
    MarketRegime,
)


logger = logging.getLogger(__name__)


# ============================================
# 数据库表定义
# ============================================

TRADE_HISTORY_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS trade_history (
    trade_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    shares INTEGER NOT NULL CHECK (shares > 0),
    price REAL NOT NULL CHECK (price > 0),
    amount REAL NOT NULL CHECK (amount > 0),
    commission REAL NOT NULL CHECK (commission >= 0),
    stamp_duty REAL NOT NULL CHECK (stamp_duty >= 0),
    slippage REAL NOT NULL CHECK (slippage >= 0),
    pnl REAL,
    survival_level TEXT NOT NULL CHECK (survival_level IN ('normal', 'low_compute', 'critical', 'dead')),
    market_regime TEXT CHECK (market_regime IN ('bull', 'bear', 'sideways')),
    model_used TEXT,
    decision_chain TEXT,
    timestamp TEXT NOT NULL,
    order_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_trade_history_symbol ON trade_history(symbol);
CREATE INDEX IF NOT EXISTS idx_trade_history_timestamp ON trade_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_trade_history_survival ON trade_history(survival_level);
"""


# ============================================
# 交易历史存储
# ============================================

class TradeHistory:
    """
    交易历史存储

    提供交易记录的 CRUD 操作和查询功能。
    """

    def __init__(self, db_path: str = "data/trading.db"):
        """
        初始化交易历史存储

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
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trade_history'")
        if cursor.fetchone() is None:
            self.db.executescript(TRADE_HISTORY_TABLE_SCHEMA)
            logger.info(f"[TradeHistory] 创建交易历史表: {self.db_path}")
        else:
            logger.debug(f"[TradeHistory] 使用现有交易历史表: {self.db_path}")

        self.db.commit()

    def record_trade(
        self,
        trade: Trade,
        survival_level: SurvivalLevel = SurvivalLevel.NORMAL,
        market_regime: Optional[MarketRegime] = None,
        model_used: Optional[str] = None,
        decision_chain: Optional[str] = None,
        order_id: Optional[str] = None,
    ) -> bool:
        """
        记录交易

        Args:
            trade: 交易对象
            survival_level: 生存等级
            market_regime: 市场状态
            model_used: 使用的模型
            decision_chain: 决策链路 (JSON 字符串)
            order_id: 关联订单ID

        Returns:
            bool: 是否记录成功
        """
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT INTO trade_history (
                    trade_id, symbol, side, shares, price, amount,
                    commission, stamp_duty, slippage, pnl,
                    survival_level, market_regime, model_used, decision_chain,
                    timestamp, order_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.trade_id,
                trade.symbol,
                trade.side.value,
                trade.shares,
                trade.price,
                trade.amount,
                trade.commission,
                trade.stamp_duty,
                trade.slippage,
                getattr(trade, 'pnl', None),  # Trade 可能有 pnl 字段
                survival_level.value,
                market_regime.value if market_regime else None,
                model_used,
                decision_chain,
                trade.timestamp.isoformat(),
                order_id,
            ))
            self.db.commit()
            logger.debug(f"[TradeHistory] 记录交易: {trade.trade_id}")
            return True

        except sqlite3.IntegrityError:
            logger.warning(f"[TradeHistory] 交易ID已存在: {trade.trade_id}")
            return False
        except Exception as e:
            logger.error(f"[TradeHistory] 记录交易失败: {e}", exc_info=True)
            return False

    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单笔交易记录

        Args:
            trade_id: 交易ID

        Returns:
            Optional[Dict[str, Any]]: 交易记录，不存在返回 None
        """
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM trade_history WHERE trade_id = ?", (trade_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return self._row_to_dict(row)

    def get_trades(
        self,
        limit: int = 100,
        offset: int = 0,
        symbol: Optional[str] = None,
        side: Optional[OrderSide] = None,
        survival_level: Optional[SurvivalLevel] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取交易记录列表

        Args:
            limit: 返回数量限制
            offset: 偏移量
            symbol: 股票代码过滤
            side: 买卖方向过滤
            survival_level: 生存等级过滤
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            List[Dict[str, Any]]: 交易记录列表
        """
        conditions = []
        params = []

        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol)

        if side:
            conditions.append("side = ?")
            params.append(side.value)

        if survival_level:
            conditions.append("survival_level = ?")
            params.append(survival_level.value)

        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())

        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor = self.db.cursor()
        cursor.execute(f"""
            SELECT * FROM trade_history
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_trades_by_symbol(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取指定股票的交易记录

        Args:
            symbol: 股票代码
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 交易记录列表
        """
        return self.get_trades(limit=limit, symbol=symbol)

    def get_recent_trades(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取最近的交易记录

        Args:
            hours: 小时数
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 交易记录列表
        """
        start_time = datetime.now() - timedelta(hours=hours)
        return self.get_trades(limit=limit, start_time=start_time)

    def get_loss_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取亏损交易记录

        Args:
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 亏损交易列表
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT * FROM trade_history
            WHERE pnl < 0
            ORDER BY pnl ASC
            LIMIT ?
        """, (limit,))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_profit_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取盈利交易记录

        Args:
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 盈利交易列表
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT * FROM trade_history
            WHERE pnl > 0
            ORDER BY pnl DESC
            LIMIT ?
        """, (limit,))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_statistics(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        获取交易统计信息

        Args:
            symbol: 股票代码（可选）

        Returns:
            Dict[str, Any]: 统计信息
        """
        where_clause = "WHERE symbol = ?" if symbol else ""
        params = (symbol,) if symbol else ()

        cursor = self.db.cursor()

        # 总交易数
        cursor.execute(f"""
            SELECT COUNT(*) FROM trade_history {where_clause}
        """, params)
        total_trades = cursor.fetchone()[0]

        # 买入数
        cursor.execute(f"""
            SELECT COUNT(*) FROM trade_history WHERE side = 'buy' {f'AND symbol = ?' if symbol else ''}
        """, params)
        buy_trades = cursor.fetchone()[0]

        # 卖出数
        cursor.execute(f"""
            SELECT COUNT(*) FROM trade_history WHERE side = 'sell' {f'AND symbol = ?' if symbol else ''}
        """, params)
        sell_trades = cursor.fetchone()[0]

        # 总金额
        cursor.execute(f"""
            SELECT SUM(amount) FROM trade_history {where_clause}
        """, params)
        total_amount = cursor.fetchone()[0] or 0.0

        # 总盈亏
        cursor.execute(f"""
            SELECT SUM(pnl) FROM trade_history {where_clause}
        """, params)
        total_pnl = cursor.fetchone()[0] or 0.0

        # 盈利交易数
        cursor.execute(f"""
            SELECT COUNT(*) FROM trade_history WHERE pnl > 0 {f'AND symbol = ?' if symbol else ''}
        """, params)
        win_trades = cursor.fetchone()[0]

        # 亏损交易数
        cursor.execute(f"""
            SELECT COUNT(*) FROM trade_history WHERE pnl < 0 {f'AND symbol = ?' if symbol else ''}
        """, params)
        loss_trades = cursor.fetchone()[0]

        # 胜率
        win_rate = win_trades / total_trades if total_trades > 0 else 0.0

        # 平均盈亏
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0.0

        return {
            "total_trades": total_trades,
            "buy_trades": buy_trades,
            "sell_trades": sell_trades,
            "total_amount": total_amount,
            "total_pnl": total_pnl,
            "win_trades": win_trades,
            "loss_trades": loss_trades,
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
        }

    def count_trades(self, symbol: Optional[str] = None) -> int:
        """
        统计交易数量

        Args:
            symbol: 股票代码（可选）

        Returns:
            int: 交易数量
        """
        cursor = self.db.cursor()

        if symbol:
            cursor.execute("SELECT COUNT(*) FROM trade_history WHERE symbol = ?", (symbol,))
        else:
            cursor.execute("SELECT COUNT(*) FROM trade_history")

        return cursor.fetchone()[0]

    def delete_trade(self, trade_id: str) -> bool:
        """
        删除交易记录

        Args:
            trade_id: 交易ID

        Returns:
            bool: 是否删除成功
        """
        try:
            cursor = self.db.cursor()
            cursor.execute("DELETE FROM trade_history WHERE trade_id = ?", (trade_id,))
            self.db.commit()
            logger.debug(f"[TradeHistory] 删除交易: {trade_id}")
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[TradeHistory] 删除交易失败: {e}", exc_info=True)
            return False

    def clear_trades(self) -> None:
        """清空所有交易记录"""
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM trade_history")
        self.db.commit()
        logger.info("[TradeHistory] 清空所有交易记录")

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """将数据库行转换为字典"""
        return {
            "trade_id": row["trade_id"],
            "symbol": row["symbol"],
            "side": row["side"],
            "shares": row["shares"],
            "price": row["price"],
            "amount": row["amount"],
            "commission": row["commission"],
            "stamp_duty": row["stamp_duty"],
            "slippage": row["slippage"],
            "pnl": row["pnl"],
            "survival_level": row["survival_level"],
            "market_regime": row["market_regime"],
            "model_used": row["model_used"],
            "decision_chain": row["decision_chain"],
            "timestamp": row["timestamp"],
            "order_id": row["order_id"],
        }

    def close(self) -> None:
        """关闭数据库连接"""
        if hasattr(self, 'db'):
            self.db.close()
            logger.debug("[TradeHistory] 数据库连接已关闭")