# -*- coding: utf-8 -*-
"""
测试反思机制

TDD 流程: RED → GREEN → REFACTOR
"""

import pytest
from datetime import datetime

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
        from datetime import timedelta
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
