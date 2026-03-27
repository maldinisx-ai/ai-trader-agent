# -*- coding: utf-8 -*-
"""
测试反思机制

TDD 流程: RED → GREEN → REFACTOR
"""

import pytest
from datetime import datetime, timedelta

from core.schemas import Trade, OrderSide, ErrorType, ReflectionRecord
from core.reflection import ReflectionEngine


class TestReflectionEngine:
    """测试反思引擎"""

    def test_reflection_creation(self):
        """测试创建反思记录"""
        reflection = ReflectionRecord(
            reflection_id="ref_001",
            trade_id="trade_001",
            loss_amount=-5000.0,
            loss_ratio=-0.05,
            error_type=ErrorType.ENTRY,
            analysis="追高买入，未设置止损",
            lesson="高位十字星需谨慎",
            avoid_action="设置3%止损",
        )

        assert reflection.reflection_id == "ref_001"
        assert reflection.loss_amount == -5000.0
        assert reflection.error_type == ErrorType.ENTRY

    def test_classify_entry_error(self):
        """测试分类入场错误"""
        engine = ReflectionEngine()

        trade = Trade(
            trade_id="trade_001",
            symbol="600519",
            side=OrderSide.BUY,
            shares=100,
            price=100.0,
            amount=10000.0,
            timestamp=datetime.now(),
        )

        # 模拟亏损离场（2小时内亏损>5%）
        trade.timestamp = datetime.now() - timedelta(hours=1)

        error_type = engine._classify_error(
            trade,
            max_price=None,
            total_value=None,
            loss_ratio=-0.06
        )
        assert error_type == ErrorType.ENTRY

    def test_classify_timing_error(self):
        """测试分类时机错误"""
        engine = ReflectionEngine()

        trade = Trade(
            trade_id="trade_001",
            symbol="600519",
            side=OrderSide.BUY,
            shares=100,
            price=100.0,
            amount=10000.0,
            timestamp=datetime.now(),
        )

        # 模拟追高（入场价接近最高价）
        error_type = engine._classify_error(
            trade,
            max_price=100.0,
            total_value=None,
            loss_ratio=-0.02
        )
        assert error_type == ErrorType.TIMING

    def test_classify_position_error(self):
        """测试分类仓位错误"""
        engine = ReflectionEngine()

        trade = Trade(
            trade_id="trade_001",
            symbol="600519",
            side=OrderSide.BUY,
            shares=1000,
            price=100.0,
            amount=100000.0,
            timestamp=datetime.now(),
        )

        # 模拟仓位过重（占比>20%）
        error_type = engine._classify_error(
            trade,
            max_price=None,
            total_value=400000.0,  # 100000/400000 = 25% > 20%
            loss_ratio=-0.02
        )
        assert error_type == ErrorType.POSITION

    def test_classify_exit_error(self):
        """测试分类出场错误"""
        engine = ReflectionEngine()

        trade = Trade(
            trade_id="trade_001",
            symbol="600519",
            side=OrderSide.BUY,
            shares=100,
            price=100.0,
            amount=10000.0,
            timestamp=datetime.now(),
        )

        # 其他情况默认为出场错误
        error_type = engine._classify_error(trade, loss_ratio=-0.03)
        assert error_type == ErrorType.EXIT

    @pytest.mark.asyncio
    async def test_reflect_on_loss_entry_error(self):
        """测试对亏损交易进行反思 - 入场错误"""
        engine = ReflectionEngine()

        trade = Trade(
            trade_id="trade_001",
            symbol="600519",
            side=OrderSide.BUY,
            shares=100,
            price=100.0,
            amount=10000.0,
            timestamp=datetime.now() - timedelta(hours=1),
        )

        reflection = await engine.reflect_on_loss(
            trade=trade,
            loss_ratio=-0.06,
            context={"max_price": 105.0, "total_value": 50000.0},
        )

        assert reflection.trade_id == "trade_001"
        assert reflection.error_type == ErrorType.ENTRY
        assert reflection.loss_ratio == 0.06
        assert "入场时机错误" in reflection.analysis

    @pytest.mark.asyncio
    async def test_reflect_on_loss_timing_error(self):
        """测试对亏损交易进行反思 - 追高错误"""
        engine = ReflectionEngine()

        trade = Trade(
            trade_id="trade_002",
            symbol="000001",
            side=OrderSide.BUY,
            shares=200,
            price=12.5,
            amount=2500.0,
            timestamp=datetime.now(),
        )

        reflection = await engine.reflect_on_loss(
            trade=trade,
            loss_ratio=-0.03,
            context={"max_price": 12.6, "total_value": 50000.0},
        )

        assert reflection.error_type == ErrorType.TIMING
        assert "追高" in reflection.analysis

    @pytest.mark.asyncio
    async def test_reflect_on_loss_position_error(self):
        """测试对亏损交易进行反思 - 仓位错误"""
        engine = ReflectionEngine()

        trade = Trade(
            trade_id="trade_003",
            symbol="000002",
            side=OrderSide.BUY,
            shares=500,
            price=10.0,
            amount=5000.0,
            timestamp=datetime.now(),
        )

        reflection = await engine.reflect_on_loss(
            trade=trade,
            loss_ratio=-0.04,
            context={"max_price": 12.0, "total_value": 20000.0},
        )

        assert reflection.error_type == ErrorType.POSITION
        assert "仓位过重" in reflection.analysis

    @pytest.mark.asyncio
    async def test_reflect_on_loss_exit_error(self):
        """测试对亏损交易进行反思 - 出场错误"""
        engine = ReflectionEngine()

        trade = Trade(
            trade_id="trade_004",
            symbol="600000",
            side=OrderSide.BUY,
            shares=100,
            price=5.0,
            amount=500.0,
            timestamp=datetime.now(),
        )

        reflection = await engine.reflect_on_loss(
            trade=trade,
            loss_ratio=-0.02,
            context={"max_price": 6.0, "total_value": 50000.0},
        )

        assert reflection.error_type == ErrorType.EXIT
        assert "出场决策错误" in reflection.analysis

    @pytest.mark.asyncio
    async def test_reflect_on_loss_without_context(self):
        """测试无上下文的反思"""
        engine = ReflectionEngine()

        trade = Trade(
            trade_id="trade_005",
            symbol="600519",
            side=OrderSide.BUY,
            shares=100,
            price=100.0,
            amount=10000.0,
            timestamp=datetime.now(),
        )

        reflection = await engine.reflect_on_loss(trade, loss_ratio=-0.02)

        assert reflection.error_type == ErrorType.EXIT  # 默认值

    @pytest.mark.asyncio
    async def test_get_reflections(self):
        """测试获取反思记录"""
        engine = ReflectionEngine()

        # 添加多条反思
        for i in range(5):
            trade = Trade(
                trade_id=f"trade_{i}",
                symbol="600519",
                side=OrderSide.BUY,
                shares=100,
                price=100.0,
                amount=10000.0,
                timestamp=datetime.now(),
            )
            await engine.reflect_on_loss(trade, loss_ratio=-0.02)

        reflections = engine.get_reflections(limit=3)
        assert len(reflections) == 3
        # 验证返回的是最后3条
        assert reflections[0].trade_id == "trade_2"

    @pytest.mark.asyncio
    async def test_get_reflections_by_symbol(self):
        """测试按股票代码获取反思记录"""
        engine = ReflectionEngine()

        # 添加不同股票的反思
        trade1 = Trade(
            trade_id="trade_600519",
            symbol="600519",
            side=OrderSide.BUY,
            shares=100,
            price=100.0,
            amount=10000.0,
            timestamp=datetime.now(),
        )
        await engine.reflect_on_loss(trade1, loss_ratio=-0.02)

        trade2 = Trade(
            trade_id="trade_000001",
            symbol="000001",
            side=OrderSide.BUY,
            shares=100,
            price=12.0,
            amount=1200.0,
            timestamp=datetime.now(),
        )
        await engine.reflect_on_loss(trade2, loss_ratio=-0.02)

        reflections = engine.get_reflections_by_symbol("600519")
        assert len(reflections) == 1
        assert "600519" in reflections[0].trade_id

    @pytest.mark.asyncio
    async def test_get_reflections_by_error_type(self):
        """测试按错误类型获取反思记录"""
        engine = ReflectionEngine()

        # 添加不同类型的错误
        trade1 = Trade(
            trade_id="trade_entry",
            symbol="600519",
            side=OrderSide.BUY,
            shares=100,
            price=100.0,
            amount=10000.0,
            timestamp=datetime.now(),
        )
        await engine.reflect_on_loss(trade1, loss_ratio=-0.06)

        trade2 = Trade(
            trade_id="trade_timing",
            symbol="000001",
            side=OrderSide.BUY,
            shares=100,
            price=12.0,
            amount=1200.0,
            timestamp=datetime.now(),
        )
        await engine.reflect_on_loss(
            trade2,
            loss_ratio=-0.02,
            context={"max_price": 12.0, "total_value": 50000.0},
        )

        reflections = engine.get_reflections_by_error_type(ErrorType.ENTRY)
        assert len(reflections) == 1
        assert reflections[0].error_type == ErrorType.ENTRY

    def test_generate_analysis_all_error_types(self):
        """测试生成所有错误类型的分析"""
        engine = ReflectionEngine()

        trade = Trade(
            trade_id="trade_test",
            symbol="600519",
            side=OrderSide.BUY,
            shares=100,
            price=100.0,
            amount=10000.0,
            timestamp=datetime.now(),
        )

        for error_type in ErrorType:
            analysis = engine._generate_analysis(trade, error_type)
            assert analysis is not None
            assert analysis.endswith("。")

    def test_generate_lesson_all_error_types(self):
        """测试生成所有错误类型的教训"""
        engine = ReflectionEngine()

        for error_type in ErrorType:
            lesson = engine._generate_lesson(error_type)
            assert lesson is not None
            assert isinstance(lesson, str)

    def test_generate_avoid_action_all_error_types(self):
        """测试生成所有错误类型的避免措施"""
        engine = ReflectionEngine()

        for error_type in ErrorType:
            action = engine._generate_avoid_action(error_type)
            assert action is not None
            assert isinstance(action, str)

    @pytest.mark.asyncio
    async def test_reflection_record_stored(self):
        """测试反思记录被正确存储"""
        engine = ReflectionEngine()

        trade = Trade(
            trade_id="trade_store",
            symbol="600519",
            side=OrderSide.BUY,
            shares=100,
            price=100.0,
            amount=10000.0,
            timestamp=datetime.now(),
        )

        reflection = await engine.reflect_on_loss(trade, loss_ratio=-0.02)

        # 验证反思已存储在引擎中
        all_reflections = engine.get_reflections(limit=100)
        assert reflection in all_reflections
