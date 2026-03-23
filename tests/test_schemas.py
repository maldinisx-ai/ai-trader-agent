# -*- coding: utf-8 -*-
"""
测试核心数据模型

TDD 流程:
1. RED: 此文件先创建，测试失败
2. GREEN: 实现 schemas.py 使测试通过
3. REFACTOR: 重构优化
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError

from core.schemas import (
    # 基础模型
    QuoteData,
    Order,
    Position,
    Trade,
    AgentResponse,
    AgentContext,
    Decision,
    PolicyResult,
    # 枚举
    SurvivalLevel,
    MarketRegime,
    OrderSide,
    OrderType,
    OrderStatus,
)


class TestQuoteData:
    """测试行情数据模型"""

    def test_create_valid_quote(self):
        """测试创建有效行情数据"""
        quote = QuoteData(
            symbol="600519",
            name="贵州茅台",
            price=1680.00,
            change=1.2,
            volume=1234567,
            amount=2100000000.0,
        )
        assert quote.symbol == "600519"
        assert quote.price == 1680.00
        assert quote.change == 1.2

    def test_quote_price_must_be_positive(self):
        """测试价格必须大于0"""
        with pytest.raises(ValidationError) as exc:
            QuoteData(
                symbol="600519",
                name="贵州茅台",
                price=-100.0,  # 无效价格
                change=1.2,
                volume=1000,
                amount=100000.0,
            )
        assert "greater than 0" in str(exc.value)

    def test_quote_change_range(self):
        """测试涨跌幅范围（-11% 到 +11%，考虑涨跌停）"""
        # 正常涨跌幅
        QuoteData(symbol="600519", name="贵州茅台", price=1680.0, change=10.0, volume=1000, amount=100000.0)
        QuoteData(symbol="600519", name="贵州茅台", price=1680.0, change=-10.0, volume=1000, amount=100000.0)

        # 超出范围
        with pytest.raises(ValidationError):
            QuoteData(symbol="600519", name="贵州茅台", price=1680.0, change=12.0, volume=1000, amount=100000.0)

        with pytest.raises(ValidationError):
            QuoteData(symbol="600519", name="贵州茅台", price=1680.0, change=-12.0, volume=1000, amount=100000.0)


class TestOrder:
    """测试订单模型"""

    def test_create_valid_buy_order(self):
        """测试创建有效买入订单"""
        order = Order(
            order_id="ord_001",
            symbol="600519",
            side="buy",
            quantity=1000,
            price=1680.0,
            order_type="limit",
        )
        assert order.order_id == "ord_001"
        assert order.side == "buy"
        assert order.quantity == 1000

    def test_order_quantity_must_be_multiple_of_100(self):
        """测试数量必须是100的整数倍"""
        with pytest.raises(ValidationError):
            Order(
                order_id="ord_001",
                symbol="600519",
                side="buy",
                quantity=150,  # 不是100的倍数
                price=1680.0,
                order_type="limit",
            )

    def test_order_side_must_be_valid(self):
        """测试订单方向必须是 buy 或 sell"""
        with pytest.raises(ValidationError):
            Order(
                order_id="ord_001",
                symbol="600519",
                side="invalid",  # 无效方向
                quantity=100,
                price=1680.0,
                order_type="limit",
            )


class TestPosition:
    """测试持仓模型"""

    def test_create_valid_position(self):
        """测试创建有效持仓"""
        position = Position(
            symbol="600519",
            shares=1000,
            avg_cost=1650.0,
            current_price=1680.0,
            opened_at=datetime.now(),
        )
        assert position.symbol == "600519"
        assert position.shares == 1000
        assert position.pnl == (1680.0 - 1650.0) * 1000
        assert position.pnl_ratio == (1680.0 - 1650.0) / 1650.0


class TestTrade:
    """测试交易记录模型"""

    def test_create_valid_trade(self):
        """测试创建有效交易记录"""
        trade = Trade(
            trade_id="trade_001",
            symbol="600519",
            side="buy",
            shares=1000,
            price=1680.0,
            amount=1680000.0,
            timestamp=datetime.now(),
        )
        assert trade.trade_id == "trade_001"
        assert trade.amount == 1680000.0


class TestAgentResponse:
    """测试Agent响应模型"""

    def test_create_success_response(self):
        """测试创建成功响应"""
        response = AgentResponse(
            success=True,
            message="交易成功",
            execution_time=1.5,
        )
        assert response.success is True
        assert response.message == "交易成功"


class TestDecision:
    """测试决策模型"""

    def test_create_buy_decision(self):
        """测试创建买入决策"""
        decision = Decision(
            action="buy",
            symbol="600519",
            quantity=1000,
            confidence=0.85,
            reasoning="技术指标显示买入信号",
        )
        assert decision.action == "buy"
        assert decision.confidence == 0.85


class TestPolicyResult:
    """测试风控结果模型"""

    def test_allow_decision(self):
        """测试允许决策"""
        result = PolicyResult(allowed=True)
        assert result.allowed is True
        assert result.reason is None

    def test_reject_decision(self):
        """测试拒绝决策"""
        result = PolicyResult(
            allowed=False,
            reason="资金不足",
            policy="FundCheckPolicy",
        )
        assert result.allowed is False
        assert result.reason == "资金不足"


class TestAgentContext:
    """测试Agent上下文模型"""

    def test_create_context(self):
        """测试创建上下文"""
        context = AgentContext(
            user_input="买入1000股茅台",
            current_cash=1000000.0,
            total_value=1000000.0,
            initial_cash=1000000.0,
            positions=[],
            survival_level=SurvivalLevel.NORMAL,
            market_regime=MarketRegime.BULL,
        )
        assert context.user_input == "买入1000股茅台"
        assert context.survival_level == SurvivalLevel.NORMAL


class TestSurvivalLevel:
    """测试生存等级枚举"""

    def test_survival_levels(self):
        """测试生存等级定义"""
        assert SurvivalLevel.NORMAL.value == "normal"
        assert SurvivalLevel.LOW_COMPUTE.value == "low_compute"
        assert SurvivalLevel.CRITICAL.value == "critical"
        assert SurvivalLevel.DEAD.value == "dead"


class TestMarketRegime:
    """测试市场状态枚举"""

    def test_market_regimes(self):
        """测试市场状态定义"""
        assert MarketRegime.BULL.value == "bull"
        assert MarketRegime.BEAR.value == "bear"
        assert MarketRegime.SIDEWAYS.value == "sideways"
