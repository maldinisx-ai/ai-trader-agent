# -*- coding: utf-8 -*-
"""
模拟账户系统

实现虚拟账户管理，含原子性保证、手续费计算和 SQLite 持久化。
使用 Decimal 保证内部金额精度，使用 threading.Lock 保证并发安全。
"""

import sqlite3
import logging
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from decimal import Decimal

from core.schemas import (
    Position,
    Trade,
    Order,
    OrderSide,
    MatchResult,
    SurvivalLevel,
    MarketRegime,
    ErrorType,
)


# ============================================
# 日志配置
# ============================================

logger = logging.getLogger(__name__)


# ============================================
# 费用配置
# ============================================

class FeeConfig:
    """费用配置 - 内部使用 Decimal 保证精度"""

    # 佣金费率（万三）
    COMMISSION_RATE = Decimal("0.0003")

    # 最低佣金（5元）
    MIN_COMMISSION = Decimal("5")

    # 印花税费率（千一，仅卖出）
    STAMP_DUTY_RATE = Decimal("0.001")

    # 滑点费率（万五）
    SLIPPAGE_RATE = Decimal("0.0005")


# ============================================
# 模拟账户
# ============================================

class Account:
    """
    模拟账户

    管理虚拟资金、持仓、交易记录，支持 SQLite 持久化。
    所有资金操作保证原子性。
    """

    # 默认初始资金
    DEFAULT_INITIAL_CASH = 1_000_000.0

    def __init__(
        self,
        initial_cash: float = DEFAULT_INITIAL_CASH,
        db_path: str = "data/trading.db",
        commission_rate: float = float(FeeConfig.COMMISSION_RATE),
        min_commission: float = float(FeeConfig.MIN_COMMISSION),
        stamp_duty_rate: float = float(FeeConfig.STAMP_DUTY_RATE),
        slippage_rate: float = float(FeeConfig.SLIPPAGE_RATE),
        enable_memory: bool = True,
    ):
        """
        初始化账户

        Args:
            initial_cash: 初始资金
            db_path: 数据库路径
            commission_rate: 佣金费率
            min_commission: 最低佣金
            stamp_duty_rate: 印花税费率
            slippage_rate: 滑点费率
            enable_memory: 是否启用记忆系统
        """
        # 内部使用 Decimal 保证精度
        self.initial_cash = Decimal(str(initial_cash))
        self.db_path = db_path
        self.commission_rate = Decimal(str(commission_rate))
        self.min_commission = Decimal(str(min_commission))
        self.stamp_duty_rate = Decimal(str(stamp_duty_rate))
        self.slippage_rate = Decimal(str(slippage_rate))
        self.enable_memory = enable_memory

        # 并发安全：线程锁
        self._lock = threading.Lock()

        # 初始化数据库
        self._init_database()

        # 加载或创建账户状态
        self._load_or_create_account()

        # 初始化记忆系统
        self._memory = None
        if enable_memory:
            try:
                from core.memory import MemoryQuery
                self._memory = MemoryQuery(db_path=db_path)
                logger.info("[Account] 记忆系统已启用")
            except ImportError:
                logger.warning("[Account] 记忆系统模块导入失败，记忆功能将不可用")

    @property
    def cash(self) -> float:
        """当前现金"""
        return self._get_account_value("cash")

    @property
    def total_value(self) -> float:
        """总资产"""
        cash = self.cash
        position_value = self.position_value
        return cash + position_value

    @property
    def position_value(self) -> float:
        """持仓市值"""
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(shares * current_price), 0)
            FROM positions
        """)
        return float(cursor.fetchone()[0])

    # ============================================
    # 数据库管理
    # ============================================

    def _init_database(self) -> None:
        """初始化数据库表"""
        # 确保目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db = sqlite3.connect(self.db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row

        # 创建账户表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                initial_cash REAL NOT NULL,
                cash REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 创建持仓表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                shares INTEGER NOT NULL CHECK (shares >= 0),
                avg_cost REAL NOT NULL CHECK (avg_cost > 0),
                current_price REAL NOT NULL CHECK (current_price > 0),
                opened_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 创建交易记录表
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
                shares INTEGER NOT NULL CHECK (shares > 0),
                price REAL NOT NULL CHECK (price > 0),
                amount REAL NOT NULL CHECK (amount > 0),
                commission REAL NOT NULL CHECK (commission >= 0),
                stamp_duty REAL NOT NULL CHECK (stamp_duty >= 0),
                slippage REAL NOT NULL CHECK (slippage >= 0),
                timestamp TEXT NOT NULL,
                order_id TEXT
            )
        """)

        self.db.commit()

    def _load_or_create_account(self) -> None:
        """加载或创建账户记录 - SQLite 不支持 Decimal，需要转换"""
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM account WHERE id = 1")
        row = cursor.fetchone()

        if row is None:
            # 创建新账户 - Decimal 转换为 float 存储
            now = datetime.now().isoformat()
            cash_float = float(self.initial_cash)
            cursor.execute("""
                INSERT INTO account (id, initial_cash, cash, created_at, updated_at)
                VALUES (1, ?, ?, ?, ?)
            """, (cash_float, cash_float, now, now))
            self.db.commit()
            logger.info(f"[Account] 创建新账户，初始资金: {float(self.initial_cash):,.2f}")
        else:
            logger.info(f"[Account] 加载现有账户，现金: {row['cash']:,.2f}")

    def _get_account_value(self, column: str) -> float:
        """
        获取账户字段值

        Args:
            column: 字段名（必须是预定义的安全字段）

        Returns:
            字段值

        Raises:
            ValueError: 如果字段名不在白名单中
        """
        # 字段白名单，防止 SQL 注入
        VALID_COLUMNS = {'cash', 'initial_cash', 'created_at', 'updated_at'}

        if column not in VALID_COLUMNS:
            raise ValueError(f"无效的字段名: {column}")

        cursor = self.db.cursor()
        cursor.execute(f"SELECT {column} FROM account WHERE id = 1")
        row = cursor.fetchone()
        return float(row[0]) if row else 0.0

    # ============================================
    # 事务管理
    # ============================================

    @contextmanager
    def _transaction(self):
        """SQLite 事务上下文管理器"""
        cursor = self.db.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE")
            yield cursor
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    # ============================================
    # 费用计算
    # ============================================

    def calculate_commission(self, amount: float, side: str) -> float:
        """
        计算佣金 - 内部使用 Decimal 保证精度

        Args:
            amount: 交易金额
            side: 买卖方向

        Returns:
            float: 佣金
        """
        amt = Decimal(str(amount))
        commission = amt * self.commission_rate
        result = max(commission, self.min_commission)
        return float(result)

    def calculate_stamp_duty(self, amount: float, side: str) -> float:
        """
        计算印花税 - 内部使用 Decimal 保证精度

        Args:
            amount: 交易金额
            side: 买卖方向

        Returns:
            float: 印花税（仅卖出收取）
        """
        if side == "sell":
            amt = Decimal(str(amount))
            return float(amt * self.stamp_duty_rate)
        return 0.0

    def calculate_slippage(self, amount: float, side: str) -> float:
        """
        计算滑点 - 内部使用 Decimal 保证精度

        Args:
            amount: 交易金额
            side: 买卖方向

        Returns:
            float: 滑点
        """
        amt = Decimal(str(amount))
        return float(amt * self.slippage_rate)

    def calculate_total_fee(self, amount: float, side: str) -> Dict[str, float]:
        """
        计算所有费用 - 内部使用 Decimal 保证精度

        Args:
            amount: 交易金额
            side: 买卖方向

        Returns:
            Dict[str, float]: 费用明细
        """
        commission = self.calculate_commission(amount, side)
        stamp_duty = self.calculate_stamp_duty(amount, side)
        slippage = self.calculate_slippage(amount, side)

        return {
            "commission": commission,
            "stamp_duty": stamp_duty,
            "slippage": slippage,
            "total": commission + stamp_duty + slippage,
        }

    # ============================================
    # 持仓查询
    # ============================================

    def get_positions(self) -> List[Position]:
        """
        获取所有持仓

        Returns:
            List[Position]: 持仓列表
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT symbol, shares, avg_cost, current_price, opened_at, updated_at
            FROM positions
            WHERE shares > 0
            ORDER BY symbol
        """)

        positions = []
        for row in cursor.fetchall():
            positions.append(Position(
                symbol=row["symbol"],
                shares=row["shares"],
                avg_cost=row["avg_cost"],
                current_price=row["current_price"],
                opened_at=datetime.fromisoformat(row["opened_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            ))

        return positions

    def get_position(self, symbol: str) -> Optional[Position]:
        """
        获取指定股票持仓

        Args:
            symbol: 股票代码

        Returns:
            Optional[Position]: 持仓对象，不存在返回 None
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT symbol, shares, avg_cost, current_price, opened_at, updated_at
            FROM positions
            WHERE symbol = ? AND shares > 0
        """, (symbol,))

        row = cursor.fetchone()
        if row is None:
            return None

        return Position(
            symbol=row["symbol"],
            shares=row["shares"],
            avg_cost=row["avg_cost"],
            current_price=row["current_price"],
            opened_at=datetime.fromisoformat(row["opened_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # ============================================
    # 交易更新
    # ============================================

    def update_from_trade(self, match_result: MatchResult) -> bool:
        """
        从交易结果更新账户（原子操作，线程安全）

        Args:
            match_result: 撮合结果

        Returns:
            bool: 是否更新成功
        """
        # 并发安全：使用线程锁
        with self._lock:
            return self._update_from_trade_unsafe(match_result)

    def _update_from_trade_unsafe(self, match_result: MatchResult) -> bool:
        """
        内部方法：从交易结果更新账户（非线程安全，需在锁内调用）

        Args:
            match_result: 撮合结果

        Returns:
            bool: 是否更新成功
        """
        order = match_result.order
        filled_quantity = match_result.filled_quantity
        filled_price = match_result.filled_price

        if not match_result.fully_filled or filled_price is None:
            logger.warning(f"[Account] 订单未完全成交，跳过更新: {order.order_id}")
            return False

        side = order.side.value

        # 使用 Decimal 进行精确计算
        price = Decimal(str(filled_price))
        amount = Decimal(str(filled_quantity)) * price

        # 计算费用
        fees = self.calculate_total_fee(float(amount), side)

        try:
            with self._transaction() as cursor:
                # 更新现金
                if side == "buy":
                    # === 资金透支保护 ===
                    total_cost = amount + Decimal(str(fees["total"]))

                    # 预检查：确保资金充足
                    current_cash = Decimal(str(self.cash))
                    if total_cost > current_cash:
                        logger.error(
                            f"[Account] 资金不足: 需要 {total_cost:.2f}, "
                            f"可用 {current_cash:.2f}, 差额 {total_cost - current_cash:.2f}"
                        )
                        return False

                    # 买入：扣除金额 + 费用
                    cursor.execute("""
                        UPDATE account
                        SET cash = cash - ?, updated_at = ?
                        WHERE id = 1
                    """, (float(total_cost), datetime.now().isoformat()))
                else:
                    # 卖出：增加金额 - 费用
                    net_amount = amount - Decimal(str(fees["total"]))
                    cursor.execute("""
                        UPDATE account
                        SET cash = cash + ?, updated_at = ?
                        WHERE id = 1
                    """, (float(net_amount), datetime.now().isoformat()))

                # 更新持仓
                self._update_position(cursor, order.symbol, filled_quantity, filled_price, side)

                # 记录交易并获取交易ID（Decimal 转为 float）
                trade_id = self._record_trade(cursor, order, filled_quantity, filled_price, float(amount), fees)

                # 如果启用了记忆系统，记录到记忆中
                if self._memory and side == "sell":
                    self._record_to_memory(trade_id, order, filled_quantity, filled_price, float(amount), fees)

                logger.info(
                    f"[Account] 交易更新成功: {side} {order.symbol} "
                    f"{filled_quantity}股 @{filled_price:.2f}, "
                    f"费用: {fees['total']:.2f}"
                )

                return True

        except Exception as e:
            logger.error(f"[Account] 交易更新失败: {e}", exc_info=True)
            return False

    def _update_position(
        self,
        cursor,
        symbol: str,
        quantity: int,
        price: float,
        side: str,
    ) -> None:
        """
        更新持仓 - 使用原子 SQL 防止超卖

        Args:
            cursor: 数据库游标
            symbol: 股票代码
            quantity: 数量
            price: 成交价格
            side: 买卖方向

        Raises:
            ValueError: 持仓不足或无持仓
        """
        now = datetime.now().isoformat()

        if side == "buy":
            # === 买入：原子操作 ===
            # 获取当前持仓
            cursor.execute("""
                SELECT shares, avg_cost FROM positions WHERE symbol = ?
            """, (symbol,))
            row = cursor.fetchone()

            if row is None:
                # 新建持仓
                cursor.execute("""
                    INSERT INTO positions (symbol, shares, avg_cost, current_price, opened_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (symbol, quantity, price, price, now, now))
            else:
                # 加仓
                old_shares = row["shares"]
                old_avg_cost = row["avg_cost"]
                new_shares = old_shares + quantity
                new_avg_cost = (old_shares * old_avg_cost + quantity * price) / new_shares

                cursor.execute("""
                    UPDATE positions
                    SET shares = ?, avg_cost = ?, current_price = ?, updated_at = ?
                    WHERE symbol = ?
                """, (new_shares, new_avg_cost, price, now, symbol))
        else:
            # === 卖出：使用原子 SQL 防止超卖 ===
            # 先尝试直接原子更新
            cursor.execute("""
                UPDATE positions
                SET shares = shares - ?, current_price = ?, updated_at = ?
                WHERE symbol = ? AND shares >= ?
            """, (quantity, price, now, symbol, quantity))

            if cursor.rowcount == 0:
                # 更新失败，检查原因
                cursor.execute("""
                    SELECT shares FROM positions WHERE symbol = ?
                """, (symbol,))
                row = cursor.fetchone()
                if row is None:
                    raise ValueError(f"卖出失败：无持仓 {symbol}")
                else:
                    available = row["shares"]
                    raise ValueError(
                        f"卖出失败：持仓不足 {symbol}（持有{available}股，卖出{quantity}股）"
                    )

            # 清空持仓（如果 shares 变为 0）
            cursor.execute("DELETE FROM positions WHERE symbol = ? AND shares = 0", (symbol,))

    def _record_trade(
        self,
        cursor,
        order: Order,
        filled_quantity: int,
        filled_price: float,
        amount: float,
        fees: Dict[str, float],
    ) -> str:
        """
        记录交易 - 存储到数据库

        Args:
            cursor: 数据库游标
            order: 订单对象
            filled_quantity: 成交数量
            filled_price: 成交价格
            amount: 成交金额
            fees: 费用明细

        Returns:
            str: 交易ID
        """
        from uuid import uuid4

        trade_id = str(uuid4())
        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO trades (
                trade_id, symbol, side, shares, price, amount,
                commission, stamp_duty, slippage, timestamp, order_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_id,
            order.symbol,
            order.side.value,
            filled_quantity,
            filled_price,
            amount,
            fees["commission"],
            fees["stamp_duty"],
            fees["slippage"],
            now,
            order.order_id,
        ))

        return trade_id

    # ============================================
    # 价格更新
    # ============================================

    def update_prices(self, prices: Dict[str, float]) -> None:
        """
        批量更新持仓价格

        Args:
            prices: 股票代码到价格的映射
        """
        with self._transaction() as cursor:
            for symbol, price in prices.items():
                cursor.execute("""
                    UPDATE positions
                    SET current_price = ?, updated_at = ?
                    WHERE symbol = ?
                """, (price, datetime.now().isoformat(), symbol))

        logger.debug(f"[Account] 更新了 {len(prices)} 只股票的价格")

    # ============================================
    # 账户信息
    # ============================================

    def get_account_info(self) -> Dict[str, Any]:
        """
        获取账户信息 - Decimal 类型转换

        Returns:
            Dict[str, Any]: 账户信息
        """
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM account WHERE id = 1")
        row = cursor.fetchone()

        # 确保 total_value 和 initial_cash 类型一致
        total = Decimal(str(self.total_value)) if not isinstance(self.total_value, Decimal) else self.total_value
        initial = Decimal(str(self.initial_cash)) if not isinstance(self.initial_cash, Decimal) else self.initial_cash

        return {
            "initial_cash": float(initial),
            "cash": row["cash"],
            "total_value": float(total),
            "position_value": float(self.position_value),
            "profit_loss": float(total - initial),
            "profit_loss_ratio": float((total - initial) / initial) if initial > 0 else 0.0,
            "position_count": len(self.get_positions()),
        }

    def get_trades(
        self,
        limit: int = 100,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取交易记录

        Args:
            limit: 返回数量限制
            symbol: 股票代码过滤（可选）

        Returns:
            List[Dict[str, Any]]: 交易记录列表
        """
        cursor = self.db.cursor()

        if symbol:
            cursor.execute("""
                SELECT * FROM trades
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (symbol, limit))
        else:
            cursor.execute("""
                SELECT * FROM trades
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

        trades = []
        for row in cursor.fetchall():
            trades.append({
                "trade_id": row["trade_id"],
                "symbol": row["symbol"],
                "side": row["side"],
                "shares": row["shares"],
                "price": row["price"],
                "amount": row["amount"],
                "commission": row["commission"],
                "stamp_duty": row["stamp_duty"],
                "slippage": row["slippage"],
                "total_cost": row["amount"] + row["commission"] + row["stamp_duty"] + row["slippage"],
                "timestamp": row["timestamp"],
                "order_id": row["order_id"],
            })

        return trades

    # ============================================
    # 重置账户
    # ============================================

    def reset(self) -> None:
        """重置账户到初始状态 - Decimal 转换为 float 存储"""
        with self._transaction() as cursor:
            # 重置现金（Decimal 转为 float）
            cash_float = float(self.initial_cash)
            cursor.execute("""
                UPDATE account
                SET cash = ?, updated_at = ?
                WHERE id = 1
            """, (cash_float, datetime.now().isoformat()))

            # 清空持仓
            cursor.execute("DELETE FROM positions")

            # 清空交易记录
            cursor.execute("DELETE FROM trades")

        # 清空记忆系统
        if self._memory:
            self._memory.trade_history.clear_trades()
            self._memory.reflection_store.clear_reflections()

        logger.info(f"[Account] 账户已重置，现金: {float(self.initial_cash):,.2f}")

    # ============================================
    # 记忆系统集成
    # ============================================

    @property
    def memory(self):
        """获取记忆查询接口"""
        return self._memory

    def _record_to_memory(
        self,
        trade_id: str,
        order: Order,
        filled_quantity: int,
        filled_price: float,
        amount: float,
        fees: Dict[str, float],
    ) -> None:
        """
        记录交易到记忆系统

        Args:
            trade_id: 交易ID
            order: 订单对象
            filled_quantity: 成交数量
            filled_price: 成交价格
            amount: 成交金额
            fees: 费用明细
        """
        if not self._memory:
            return

        try:
            trade = Trade(
                trade_id=trade_id,
                symbol=order.symbol,
                side=order.side,
                shares=filled_quantity,
                price=filled_price,
                amount=amount,
                commission=fees["commission"],
                stamp_duty=fees["stamp_duty"],
                slippage=fees["slippage"],
                timestamp=datetime.now(),
                order_id=order.order_id,
            )

            # 记录到交易历史
            self._memory.trade_history.record_trade(
                trade=trade,
                survival_level=SurvivalLevel.NORMAL,
                market_regime=MarketRegime.SIDEWAYS,
            )

            logger.debug(f"[Account] 已记录交易到记忆系统: {trade_id}")

        except Exception as e:
            logger.warning(f"[Account] 记录到记忆系统失败: {e}")

    def record_reflection(
        self,
        trade_id: str,
        error_type: str,
        analysis: str,
        lesson: str,
        avoid_action: str,
        confidence: float = 0.0,
    ) -> bool:
        """
        记录反思到记忆系统

        Args:
            trade_id: 关联交易ID
            error_type: 错误类型
            analysis: 分析内容
            lesson: 经验教训
            avoid_action: 避免措施
            confidence: 置信度

        Returns:
            bool: 是否记录成功
        """
        if not self._memory:
            logger.warning("[Account] 记忆系统未启用，无法记录反思")
            return False

        try:
            error_type_enum = ErrorType(error_type)

            return self._memory.reflection_store.record_reflection(
                trade_id=trade_id,
                error_type=error_type_enum,
                analysis=analysis,
                lesson=lesson,
                avoid_action=avoid_action,
                confidence=confidence,
            )

        except ValueError:
            logger.warning(f"[Account] 无效的错误类型: {error_type}")
            return False
        except Exception as e:
            logger.error(f"[Account] 记录反思失败: {e}", exc_info=True)
            return False

    def get_trade_recommendations(self, symbol: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        基于反思记录获取交易建议

        Args:
            symbol: 股票代码（可选）
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 建议列表
        """
        if not self._memory:
            return []

        return self._memory.get_recommendations(symbol=symbol, limit=limit)

    def close(self) -> None:
        """关闭数据库连接"""
        if hasattr(self, 'db'):
            self.db.close()
            logger.info("[Account] 数据库连接已关闭")
