# -*- coding: utf-8 -*-
"""
记忆系统测试
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import uuid

from core.memory import TradeHistory, ReflectionStore, MemoryQuery
from core.schemas import (
    Trade,
    OrderSide,
    SurvivalLevel,
    MarketRegime,
    ErrorType,
)


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def temp_db():
    """临时数据库 fixture"""
    temp_dir = Path("D:/projects/ai-trader-agent/data/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    db_path = temp_dir / f"test_memory_{uuid.uuid4().hex}.db"

    # 压力测试，确保目录存在
    db_path.parent.mkdir(parents=True, exist_ok=True)

    yield str(db_path)

    # 清理 - Windows 需要先关闭连接
    try:
        import gc
        gc.collect()  # 触发垃圾回收，关闭可能残留的连接
        if Path(db_path).exists():
            Path(db_path).unlink()
    except PermissionError:
        # 如果无法删除（Windows 锁定），跳过清理
        pass


@pytest.fixture
def trade_history(temp_db):
    """交易历史存储 fixture"""
    return TradeHistory(db_path=temp_db)


@pytest.fixture
def reflection_store(temp_db):
    """反思记录存储 fixture"""
    return ReflectionStore(db_path=temp_db)


@pytest.fixture
def memory_query(temp_db):
    """记忆查询 fixture"""
    return MemoryQuery(db_path=temp_db)


@pytest.fixture
def sample_trade():
    """示例交易 fixture"""
    return Trade(
        trade_id="test_trade_001",
        symbol="600519",
        side=OrderSide.BUY,
        shares=100,
        price=1680.00,
        amount=168000.00,
        commission=50.40,
        stamp_duty=0.0,
        slippage=84.00,
        timestamp=datetime.now(),
    )


# ============================================
# TradeHistory 测试
# ============================================

class TestTradeHistory:
    """交易历史存储测试"""

    def test_init_database(self, temp_db):
        """测试数据库初始化"""
        th = TradeHistory(db_path=temp_db)

        # 验证表已创建
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='trade_history'
        """)
        assert cursor.fetchone() is not None

        # 验证索引已创建
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND tbl_name='trade_history'
        """)
        indexes = [row[0] for row in cursor.fetchall()]
        assert "idx_trade_history_symbol" in indexes
        assert "idx_trade_history_timestamp" in indexes

        conn.close()

    def test_record_trade(self, trade_history, sample_trade):
        """测试记录交易"""
        result = trade_history.record_trade(
            trade=sample_trade,
            survival_level=SurvivalLevel.NORMAL,
            market_regime=MarketRegime.SIDEWAYS,
            model_used="claude-sonnet-4.6",
            order_id="order_001",
        )

        assert result is True

        # 验证记录已保存
        trade = trade_history.get_trade(sample_trade.trade_id)
        assert trade is not None
        assert trade["trade_id"] == sample_trade.trade_id
        assert trade["symbol"] == sample_trade.symbol
        assert trade["side"] == sample_trade.side.value
        assert trade["survival_level"] == SurvivalLevel.NORMAL.value

    def test_record_duplicate_trade(self, trade_history, sample_trade):
        """测试记录重复交易"""
        trade_history.record_trade(sample_trade, SurvivalLevel.NORMAL)

        # 再次记录相同交易ID应该失败
        result = trade_history.record_trade(sample_trade, SurvivalLevel.NORMAL)
        assert result is False

    def test_get_trade_not_found(self, trade_history):
        """测试获取不存在的交易"""
        trade = trade_history.get_trade("nonexistent")
        assert trade is None

    def test_get_trades(self, trade_history, sample_trade):
        """测试获取交易列表"""
        # 记录多笔交易
        for i in range(5):
            trade = Trade(
                trade_id=f"test_trade_{i:03d}",
                symbol="600519" if i % 2 == 0 else "000001",
                side=OrderSide.BUY if i % 2 == 0 else OrderSide.SELL,
                shares=100,
                price=1680.00,
                amount=168000.00,
                commission=50.40,
                stamp_duty=0.0,
                slippage=84.00,
                timestamp=datetime.now() - timedelta(hours=i),
            )
            trade_history.record_trade(trade, SurvivalLevel.NORMAL)

        trades = trade_history.get_trades(limit=10)
        assert len(trades) == 5
        # 应该按时间倒序
        assert trades[0]["trade_id"] == "test_trade_000"

    def test_get_trades_with_filters(self, trade_history):
        """测试带过滤器的交易查询"""
        # 记录多笔交易
        for i in range(4):
            trade = Trade(
                trade_id=f"test_trade_{i:03d}",
                symbol="600519" if i < 2 else "000001",
                side=OrderSide.BUY if i < 2 else OrderSide.SELL,
                shares=100,
                price=1680.00,
                amount=168000.00,
                commission=50.40,
                stamp_duty=0.0,
                slippage=84.00,
                timestamp=datetime.now(),
            )
            trade_history.record_trade(trade, SurvivalLevel.NORMAL)

        # 按股票代码过滤
        trades = trade_history.get_trades(symbol="600519")
        assert len(trades) == 2
        assert all(t["symbol"] == "600519" for t in trades)

        # 按买卖方向过滤
        trades = trade_history.get_trades(side=OrderSide.SELL)
        assert len(trades) == 2
        assert all(t["side"] == "sell" for t in trades)

    def test_get_trades_by_symbol(self, trade_history, sample_trade):
        """测试获取指定股票的交易"""
        trade_history.record_trade(sample_trade, SurvivalLevel.NORMAL)

        # 添加另一只股票的交易
        other_trade = Trade(
            trade_id="test_trade_002",
            symbol="000001",
            side=OrderSide.BUY,
            shares=100,
            price=1000.00,
            amount=100000.00,
            commission=30.00,
            stamp_duty=0.0,
            slippage=50.00,
            timestamp=datetime.now(),
        )
        trade_history.record_trade(other_trade, SurvivalLevel.NORMAL)

        trades = trade_history.get_trades_by_symbol("600519")
        assert len(trades) == 1
        assert trades[0]["symbol"] == "600519"

    def test_get_recent_trades(self, trade_history):
        """测试获取最近交易"""
        # 记录不同时间的交易
        for hours in [1, 2, 5, 10, 25]:
            trade = Trade(
                trade_id=f"trade_{hours}h",
                symbol="600519",
                side=OrderSide.BUY,
                shares=100,
                price=1680.00,
                amount=168000.00,
                commission=50.40,
                stamp_duty=0.0,
                slippage=84.00,
                timestamp=datetime.now() - timedelta(hours=hours),
            )
            trade_history.record_trade(trade, SurvivalLevel.NORMAL)

        # 获取最近24小时内的交易
        recent_trades = trade_history.get_recent_trades(hours=24)
        assert len(recent_trades) == 4
        assert all(t["symbol"] == "600519" for t in recent_trades)

    def test_get_statistics(self, trade_history):
        """测试获取交易统计"""
        # 记录多笔交易
        for i in range(6):
            trade = Trade(
                trade_id=f"test_trade_{i:03d}",
                symbol="600519",
                side=OrderSide.BUY if i < 3 else OrderSide.SELL,
                shares=100,
                price=1680.00,
                amount=168000.00,
                commission=50.40,
                stamp_duty=0.0,
                slippage=84.00,
                timestamp=datetime.now(),
            )
            trade_history.record_trade(trade, SurvivalLevel.NORMAL)

        stats = trade_history.get_statistics()
        assert stats["total_trades"] == 6
        assert stats["buy_trades"] == 3
        assert stats["sell_trades"] == 3
        assert stats["total_amount"] > 0

    def test_count_trades(self, trade_history, sample_trade):
        """测试统计交易数量"""
        trade_history.record_trade(sample_trade, SurvivalLevel.NORMAL)

        count = trade_history.count_trades()
        assert count == 1

        count = trade_history.count_trades(symbol="600519")
        assert count == 1

        count = trade_history.count_trades(symbol="000001")
        assert count == 0

    def test_delete_trade(self, trade_history, sample_trade):
        """测试删除交易"""
        trade_history.record_trade(sample_trade, SurvivalLevel.NORMAL)

        # 验证交易存在
        assert trade_history.get_trade(sample_trade.trade_id) is not None

        # 删除交易
        result = trade_history.delete_trade(sample_trade.trade_id)
        assert result is True

        # 验证交易已删除
        assert trade_history.get_trade(sample_trade.trade_id) is None

    def test_clear_trades(self, trade_history):
        """测试清空交易"""
        # 记录多笔交易
        for i in range(3):
            trade = Trade(
                trade_id=f"test_trade_{i:03d}",
                symbol="600519",
                side=OrderSide.BUY,
                shares=100,
                price=1680.00,
                amount=168000.00,
                commission=50.40,
                stamp_duty=0.0,
                slippage=84.00,
                timestamp=datetime.now(),
            )
            trade_history.record_trade(trade, SurvivalLevel.NORMAL)

        # 清空
        trade_history.clear_trades()

        # 验证已清空
        assert trade_history.count_trades() == 0


# ============================================
# ReflectionStore 测试
# ============================================

class TestReflectionStore:
    """反思记录存储测试"""

    def test_init_database(self, temp_db):
        """测试数据库初始化"""
        rs = ReflectionStore(db_path=temp_db)

        # 验证表已创建
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='reflections'
        """)
        assert cursor.fetchone() is not None

        # 验证索引已创建
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND tbl_name='reflections'
        """)
        indexes = [row[0] for row in cursor.fetchall()]
        assert "idx_reflections_trade_id" in indexes
        assert "idx_reflections_error_type" in indexes

        conn.close()

    def test_record_reflection(self, reflection_store):
        """测试记录反思"""
        result = reflection_store.record_reflection(
            trade_id="test_trade_001",
            error_type=ErrorType.ENTRY,
            analysis="在趋势不明时过早入场",
            lesson="等待趋势确认后再入场",
            avoid_action="观察20日均线和成交量",
            confidence=0.8,
        )

        assert result is True

        # 验证记录已保存
        reflections = reflection_store.get_reflections_by_trade_id("test_trade_001")
        assert len(reflections) == 1
        assert reflections[0]["error_type"] == ErrorType.ENTRY.value

    def test_get_reflections_by_trade_id(self, reflection_store):
        """测试获取指定交易的反思"""
        reflection_store.record_reflection(
            trade_id="test_trade_001",
            error_type=ErrorType.ENTRY,
            analysis="分析内容",
            lesson="经验教训",
            avoid_action="避免措施",
        )

        reflections = reflection_store.get_reflections_by_trade_id("test_trade_001")
        assert len(reflections) == 1

        reflections = reflection_store.get_reflections_by_trade_id("nonexistent")
        assert len(reflections) == 0

    def test_get_reflections_by_error_type(self, reflection_store):
        """测试按错误类型获取反思"""
        for error_type in [ErrorType.ENTRY, ErrorType.EXIT, ErrorType.POSITION]:
            reflection_store.record_reflection(
                trade_id=f"trade_{error_type.value}",
                error_type=error_type,
                analysis=f"{error_type.value} 分析",
                lesson=f"{error_type.value} 教训",
                avoid_action=f"{error_type.value} 措施",
            )

        reflections = reflection_store.get_reflections_by_error_type(ErrorType.ENTRY)
        assert len(reflections) == 1
        assert reflections[0]["error_type"] == ErrorType.ENTRY.value

    def test_get_recent_reflections(self, reflection_store):
        """测试获取最近反思"""
        # 记录不同时间的反思
        for i, hours in enumerate([1, 2, 5, 10]):
            reflection_store.record_reflection(
                trade_id=f"trade_{i}_hours",
                error_type=ErrorType.ENTRY,
                analysis="分析",
                lesson="教训",
                avoid_action="措施",
                timestamp=datetime.now() - timedelta(hours=hours),
            )

        # 6小时内应该有 1, 2, 5 小时前的 3 个反思
        recent = reflection_store.get_recent_reflections(hours=6)
        assert len(recent) == 3

    def test_get_error_type_statistics(self, reflection_store):
        """测试错误类型统计"""
        for i in range(3):
            reflection_store.record_reflection(
                trade_id=f"trade_entry_{i}",
                error_type=ErrorType.ENTRY,
                analysis="分析",
                lesson="教训",
                avoid_action="措施",
            )

        for i in range(2):
            reflection_store.record_reflection(
                trade_id=f"trade_exit_{i}",
                error_type=ErrorType.EXIT,
                analysis="分析",
                lesson="教训",
                avoid_action="措施",
            )

        stats = reflection_store.get_error_type_statistics()
        assert stats["total"] == 5
        assert stats["by_type"][ErrorType.ENTRY.value] == 3
        assert stats["by_type"][ErrorType.EXIT.value] == 2

    def test_get_lessons_by_error_type(self, reflection_store):
        """测试获取指定错误类型的教训"""
        reflection_store.record_reflection(
            trade_id="trade_1",
            error_type=ErrorType.ENTRY,
            analysis="分析",
            lesson="等待趋势确认",
            avoid_action="观察均线",
        )

        reflection_store.record_reflection(
            trade_id="trade_2",
            error_type=ErrorType.ENTRY,
            analysis="分析",
            lesson="控制仓位",
            avoid_action="限制比例",
        )

        lessons = reflection_store.get_lessons_by_error_type(ErrorType.ENTRY)
        assert len(lessons) == 2
        assert "等待趋势确认" in lessons

    def test_count_reflections(self, reflection_store):
        """测试统计反思数量"""
        for _ in range(3):
            reflection_store.record_reflection(
                trade_id=f"trade_{_}",
                error_type=ErrorType.ENTRY,
                analysis="分析",
                lesson="教训",
                avoid_action="措施",
            )

        assert reflection_store.count_reflections() == 3
        assert reflection_store.count_reflections(ErrorType.ENTRY) == 3
        assert reflection_store.count_reflections(ErrorType.EXIT) == 0

    def test_delete_reflection(self, reflection_store):
        """测试删除反思"""
        reflection_store.record_reflection(
            trade_id="test_trade",
            error_type=ErrorType.ENTRY,
            analysis="分析",
            lesson="教训",
            avoid_action="措施",
        )

        reflections = reflection_store.get_all_reflections()
        reflection_id = reflections[0]["reflection_id"]

        result = reflection_store.delete_reflection(reflection_id)
        assert result is True

        assert reflection_store.count_reflections() == 0

    def test_clear_reflections(self, reflection_store):
        """测试清空反思"""
        for _ in range(3):
            reflection_store.record_reflection(
                trade_id=f"trade_{_}",
                error_type=ErrorType.ENTRY,
                analysis="分析",
                lesson="教训",
                avoid_action="措施",
            )

        reflection_store.clear_reflections()
        assert reflection_store.count_reflections() == 0


# ============================================
# MemoryQuery 测试
# ============================================

class TestMemoryQuery:
    """记忆查询引擎测试"""

    def test_get_trades(self, memory_query, sample_trade):
        """测试查询交易"""
        memory_query.trade_history.record_trade(sample_trade, SurvivalLevel.NORMAL)

        trades = memory_query.get_trades()
        assert len(trades) == 1

    def test_get_trade_with_reflection(self, memory_query):
        """测试获取交易及其反思"""
        # 记录交易
        trade = Trade(
            trade_id="test_trade_001",
            symbol="600519",
            side=OrderSide.BUY,
            shares=100,
            price=1680.00,
            amount=168000.00,
            commission=50.40,
            stamp_duty=0.0,
            slippage=84.00,
            timestamp=datetime.now(),
        )
        memory_query.trade_history.record_trade(trade, SurvivalLevel.NORMAL)

        # 记录反思
        memory_query.reflection_store.record_reflection(
            trade_id="test_trade_001",
            error_type=ErrorType.ENTRY,
            analysis="分析",
            lesson="教训",
            avoid_action="措施",
        )

        result = memory_query.get_trade_with_reflection("test_trade_001")
        assert result is not None
        assert result["trade"]["trade_id"] == "test_trade_001"
        assert len(result["reflections"]) == 1

    def test_get_recommendations(self, memory_query):
        """测试获取交易建议"""
        # 记录反思
        memory_query.reflection_store.record_reflection(
            trade_id="trade_1",
            error_type=ErrorType.ENTRY,
            analysis="追高买入",
            lesson="不要追高",
            avoid_action="等待回调至5日均线",
        )

        recommendations = memory_query.get_recommendations()
        assert len(recommendations) > 0
        assert recommendations[0]["type"] == "avoid"
        assert "不要追高" in recommendations[0]["lesson"]

    def test_get_recent_activity(self, memory_query, sample_trade):
        """测试获取最近活动"""
        memory_query.trade_history.record_trade(sample_trade, SurvivalLevel.NORMAL)

        activity = memory_query.get_recent_activity(hours=24)
        assert activity["total_trades"] == 1
        assert activity["buy_trades"] == 1

    def test_get_symbol_performance(self, memory_query):
        """测试获取股票表现"""
        # 记录多笔交易
        for i in range(3):
            trade = Trade(
                trade_id=f"trade_{i}",
                symbol="600519",
                side=OrderSide.BUY if i < 2 else OrderSide.SELL,
                shares=100,
                price=1680.00,
                amount=168000.00,
                commission=50.40,
                stamp_duty=0.0,
                slippage=84.00,
                timestamp=datetime.now(),
            )
            memory_query.trade_history.record_trade(trade, SurvivalLevel.NORMAL)

        performance = memory_query.get_symbol_performance("600519")
        assert performance["symbol"] == "600519"
        assert performance["total_trades"] == 3

    def test_get_full_statistics(self, memory_query, sample_trade):
        """测试获取完整统计"""
        memory_query.trade_history.record_trade(sample_trade, SurvivalLevel.NORMAL)
        memory_query.reflection_store.record_reflection(
            trade_id=sample_trade.trade_id,
            error_type=ErrorType.ENTRY,
            analysis="分析",
            lesson="教训",
            avoid_action="措施",
        )

        stats = memory_query.get_full_statistics()
        assert "trades" in stats
        assert "reflections" in stats
        assert stats["trades"]["total_trades"] == 1

    def test_close(self, memory_query):
        """测试关闭连接"""
        memory_query.close()
        # 不应该抛出异常
        memory_query.close()

    def test_get_reflections(self, memory_query):
        """测试查询反思记录"""
        # 记录反思
        memory_query.reflection_store.record_reflection(
            trade_id="trade_1",
            error_type=ErrorType.ENTRY,
            analysis="分析",
            lesson="教训",
            avoid_action="措施",
        )

        # 查询所有反思
        reflections = memory_query.get_reflections()
        assert len(reflections) == 1

        # 按错误类型查询
        reflections = memory_query.get_reflections(error_type=ErrorType.ENTRY)
        assert len(reflections) == 1

        # 按错误类型查询（不匹配）
        reflections = memory_query.get_reflections(error_type=ErrorType.EXIT)
        assert len(reflections) == 0

    def test_get_lessons_for_error_type(self, memory_query):
        """测试获取指定错误类型的教训"""
        memory_query.reflection_store.record_reflection(
            trade_id="trade_1",
            error_type=ErrorType.ENTRY,
            analysis="分析",
            lesson="等待趋势确认",
            avoid_action="观察均线",
        )

        memory_query.reflection_store.record_reflection(
            trade_id="trade_2",
            error_type=ErrorType.ENTRY,
            analysis="分析",
            lesson="控制仓位",
            avoid_action="限制比例",
        )

        lessons = memory_query.get_lessons_for_error_type(ErrorType.ENTRY)
        assert len(lessons) == 2
        assert "等待趋势确认" in lessons
        assert "控制仓位" in lessons

    def test_get_avoid_actions_for_error_type(self, memory_query):
        """测试获取指定错误类型的避免措施"""
        memory_query.reflection_store.record_reflection(
            trade_id="trade_1",
            error_type=ErrorType.ENTRY,
            analysis="分析",
            lesson="教训",
            avoid_action="等待回调",
        )

        actions = memory_query.get_avoid_actions_for_error_type(ErrorType.ENTRY)
        assert len(actions) == 1
        assert "等待回调" in actions

    def test_get_loss_pattern_summary(self, memory_query):
        """测试获取亏损模式总结"""
        # 记录亏损交易和反思
        trade = Trade(
            trade_id="loss_trade",
            symbol="600519",
            side=OrderSide.SELL,
            shares=100,
            price=1650.00,
            amount=165000.00,
            commission=50.40,
            stamp_duty=0.0,
            slippage=84.00,
            timestamp=datetime.now(),
        )

        # 模拟有 pnl 字段的 Trade
        from dataclasses import dataclass
        @dataclass
        class TradeWithPnl:
            trade_id: str
            symbol: str
            side: OrderSide
            shares: int
            price: float
            amount: float
            commission: float
            stamp_duty: float
            slippage: float
            timestamp: datetime
            pnl: float

        trade_with_pnl = TradeWithPnl(
            trade_id="loss_trade",
            symbol="600519",
            side=OrderSide.SELL,
            shares=100,
            price=1650.00,
            amount=165000.00,
            commission=50.40,
            stamp_duty=0.0,
            slippage=84.00,
            timestamp=datetime.now(),
            pnl=-1000.00,
        )

        memory_query.trade_history.record_trade(trade_with_pnl, SurvivalLevel.NORMAL)
        memory_query.reflection_store.record_reflection(
            trade_id="loss_trade",
            error_type=ErrorType.ENTRY,
            analysis="追高",
            lesson="不要追高",
            avoid_action="等待回调",
        )

        summary = memory_query.get_loss_pattern_summary(hours=24)
        assert "total_loss_trades" in summary
        assert summary["total_loss_trades"] >= 0

    def test_get_symbol_performance_with_reflections(self, memory_query):
        """测试获取股票表现（含反思）"""
        # 记录交易
        for i in range(3):
            trade = Trade(
                trade_id=f"trade_{i}",
                symbol="600519",
                side=OrderSide.BUY if i < 2 else OrderSide.SELL,
                shares=100,
                price=1680.00,
                amount=168000.00,
                commission=50.40,
                stamp_duty=0.0,
                slippage=84.00,
                timestamp=datetime.now(),
            )
            memory_query.trade_history.record_trade(trade, SurvivalLevel.NORMAL)

        # 记录反思
        memory_query.reflection_store.record_reflection(
            trade_id="trade_0",
            error_type=ErrorType.ENTRY,
            analysis="分析",
            lesson="教训",
            avoid_action="措施",
        )

        performance = memory_query.get_symbol_performance("600519")
        assert performance["symbol"] == "600519"
        assert performance["reflection_count"] == 1