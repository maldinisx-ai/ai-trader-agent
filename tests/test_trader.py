# -*- coding: utf-8 -*-
"""
实盘交易器测试

测试 LiveTrader 和相关组件。
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from src.trader import (
    LiveTrader, TradingMetrics, TraderConfig, run_live_trader
)

# Fix import for Decision.action being a Mock in tests
from core.schemas import SurvivalLevel, Decision, MarketRegime, QuoteData


# ============================================================================
# TradingMetrics Tests
# ============================================================================

class TestTradingMetrics:
    """交易指标统计测试"""

    def test_initial_state(self):
        """测试初始状态"""
        metrics = TradingMetrics()

        assert metrics.total_decisions == 0
        assert metrics.successful_trades == 0
        assert metrics.rejected_trades == 0
        assert metrics.failed_trades == 0
        assert metrics.total_pnl == 0.0
        assert metrics.start_time is not None
        assert metrics.last_decision_time is None

    def test_record_decision(self):
        """测试记录决策"""
        metrics = TradingMetrics()

        metrics.record_decision(SurvivalLevel.NORMAL)
        assert metrics.total_decisions == 1
        assert metrics.decisions_by_survival[SurvivalLevel.NORMAL] == 1
        assert metrics.last_decision_time is not None

        metrics.record_decision(SurvivalLevel.CRITICAL)
        assert metrics.total_decisions == 2
        assert metrics.decisions_by_survival[SurvivalLevel.CRITICAL] == 1

    def test_record_trade_success(self):
        """测试记录成功交易"""
        metrics = TradingMetrics()

        metrics.record_trade(success=True, pnl=1000.0)
        assert metrics.successful_trades == 1
        assert metrics.total_pnl == 1000.0

        metrics.record_trade(success=True, pnl=-500.0)
        assert metrics.successful_trades == 2
        assert metrics.total_pnl == 500.0

    def test_record_trade_failure(self):
        """测试记录失败交易"""
        metrics = TradingMetrics()

        metrics.record_trade(success=False)
        assert metrics.failed_trades == 1
        assert metrics.total_pnl == 0.0

    def test_record_rejection(self):
        """测试记录拒绝交易"""
        metrics = TradingMetrics()

        metrics.record_rejection()
        assert metrics.rejected_trades == 1

        metrics.record_rejection()
        assert metrics.rejected_trades == 2

    def test_get_summary(self):
        """测试获取统计摘要"""
        metrics = TradingMetrics()

        metrics.record_decision(SurvivalLevel.NORMAL)
        metrics.record_trade(success=True, pnl=1000.0)
        metrics.record_rejection()

        summary = metrics.get_summary()

        assert summary["total_decisions"] == 1
        assert summary["successful_trades"] == 1
        assert summary["rejected_trades"] == 1
        assert summary["failed_trades"] == 0
        assert summary["total_pnl"] == 1000.0
        assert summary["win_rate"] == 1.0
        assert summary["uptime_seconds"] > 0
        assert "last_decision_time" in summary


# ============================================================================
# TraderConfig Tests
# ============================================================================

class TestTraderConfig:
    """交易配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = TraderConfig({})

        assert config.trading_symbols == ["600519"]
        assert config.max_position_ratio == 0.30
        assert config.decision_interval_seconds == 60
        assert config.market_open_hour == 9
        assert config.market_open_minute == 30
        assert config.market_close_hour == 15
        assert config.market_close_minute == 0
        assert config.enable_auto_trading is False
        assert config.dry_run is True

    def test_custom_config(self):
        """测试自定义配置"""
        config_dict = {
            "symbols": ["600519", "000858"],
            "max_position_ratio": 0.25,
            "decision_interval": 120,
            "market_open_hour": 8,
            "market_close_hour": 16,
            "enable_auto_trading": True,
            "dry_run": False,
        }

        config = TraderConfig(config_dict)

        assert config.trading_symbols == ["600519", "000858"]
        assert config.max_position_ratio == 0.25
        assert config.decision_interval_seconds == 120
        assert config.market_open_hour == 8
        assert config.market_close_hour == 16
        assert config.enable_auto_trading is True
        assert config.dry_run is False

    @patch('src.trader.datetime')
    def test_is_market_open_weekday(self, mock_datetime):
        """测试工作日市场开盘判断"""
        # 周一 10:00
        mock_now = Mock()
        mock_now.weekday.return_value = 0  # Monday
        mock_now.hour = 10
        mock_now.minute = 0
        mock_datetime.now.return_value = mock_now

        config = TraderConfig({})
        assert config.is_market_open() is True

    @patch('src.trader.datetime')
    def test_is_market_open_weekend(self, mock_datetime):
        """测试周末市场休市判断"""
        # 周六 10:00
        mock_now = Mock()
        mock_now.weekday.return_value = 5  # Saturday
        mock_now.hour = 10
        mock_now.minute = 0
        mock_datetime.now.return_value = mock_now

        config = TraderConfig({})
        assert config.is_market_open() is False

    @patch('src.trader.datetime')
    def test_is_market_open_before_hours(self, mock_datetime):
        """测试开盘前判断"""
        # 周一 8:00
        mock_now = Mock()
        mock_now.weekday.return_value = 0  # Monday
        mock_now.hour = 8
        mock_now.minute = 0
        mock_datetime.now.return_value = mock_now

        config = TraderConfig({})
        assert config.is_market_open() is False

    @patch('src.trader.datetime')
    def test_is_market_open_after_hours(self, mock_datetime):
        """测试收盘后判断"""
        # 周一 16:00
        mock_now = Mock()
        mock_now.weekday.return_value = 0  # Monday
        mock_now.hour = 16
        mock_now.minute = 0
        mock_datetime.now.return_value = mock_now

        config = TraderConfig({})
        assert config.is_market_open() is False


# ============================================================================
# LiveTrader Tests
# ============================================================================

@pytest.fixture
def mock_components():
    """创建模拟组件"""
    account = Mock()
    account.total_value = 1_000_000.0
    account.get_account_info.return_value = {
        "cash": 500_000.0,
        "total_value": 1_000_000.0,
        "profit_loss": 0.0,
        "profit_loss_ratio": 0.0,
        "initial_cash": 1_000_000.0,
        "position_value": 500_000.0,
        "position_count": 1,
    }
    account.get_positions.return_value = []

    policy_engine = Mock()
    policy_engine.validate_order.return_value = Mock(
        approved=True,
        reason=""
    )

    survival_rules = Mock()
    survival_rules.get_current_state.return_value = Mock(
        level=SurvivalLevel.NORMAL,
        trading_interval=60
    )

    matcher = Mock()
    matcher.update_quote = Mock()
    matcher.match = AsyncMock(return_value=Mock(
        success=True,
        filled_quantity=100,
        filled_price=100.0,
        commission=30.0,
        stamp_duty=10.0,
        pnl=0.0,
        reason="Fully filled"
    ))

    tool_executor = Mock()
    tool_executor.execute_tool = AsyncMock(return_value=Mock(
        success=True,
        data=QuoteData(
            symbol="600519",
            name="Test Stock",
            price=100.0,
            change=1.0,
            volume=1000000,
            amount=100000000.0,
        )
    ))

    return {
        "account": account,
        "policy_engine": policy_engine,
        "survival_rules": survival_rules,
        "matcher": matcher,
        "tool_executor": tool_executor,
    }


class TestLiveTrader:
    """实盘交易器测试"""

    def test_initialization(self, mock_components):
        """测试初始化"""
        config = {
            "trader": {
                "symbols": ["600519"],
                "decision_interval": 60,
                "enable_auto_trading": False,
                "dry_run": True,
            },
            "model": {},
        }

        trader = LiveTrader(
            account=mock_components["account"],
            policy_engine=mock_components["policy_engine"],
            survival_rules=mock_components["survival_rules"],
            matcher=mock_components["matcher"],
            tool_executor=mock_components["tool_executor"],
            config=config,
        )

        assert trader.running is False
        assert trader.should_stop is False
        assert trader.metrics is not None
        assert trader.config.trading_symbols == ["600519"]

    @pytest.mark.asyncio
    async def test_get_quotes_success(self, mock_components):
        """测试获取行情成功"""
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        trader = LiveTrader(
            account=mock_components["account"],
            policy_engine=mock_components["policy_engine"],
            survival_rules=mock_components["survival_rules"],
            matcher=mock_components["matcher"],
            tool_executor=mock_components["tool_executor"],
            config=config,
        )

        quotes = await trader._get_quotes()

        assert len(quotes) == 1
        assert quotes[0].symbol == "600519"

    @pytest.mark.asyncio
    async def test_get_quotes_failure(self, mock_components):
        """测试获取行情失败"""
        mock_components["tool_executor"].execute_tool = AsyncMock(
            return_value=Mock(success=False, error="Network error")
        )

        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        trader = LiveTrader(
            account=mock_components["account"],
            policy_engine=mock_components["policy_engine"],
            survival_rules=mock_components["survival_rules"],
            matcher=mock_components["matcher"],
            tool_executor=mock_components["tool_executor"],
            config=config,
        )

        quotes = await trader._get_quotes()
        assert len(quotes) == 0

    def test_update_account_values(self, mock_components):
        """测试更新账户持仓市值"""
        # 创建模拟持仓
        mock_position = Mock()
        mock_position.symbol = "600519"
        mock_position.update_market_value = Mock()

        mock_components["account"].get_positions.return_value = [mock_position]

        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        trader = LiveTrader(
            account=mock_components["account"],
            policy_engine=mock_components["policy_engine"],
            survival_rules=mock_components["survival_rules"],
            matcher=mock_components["matcher"],
            tool_executor=mock_components["tool_executor"],
            config=config,
        )

        quotes = [
            QuoteData(
                symbol="600519",
                name="Test Stock",
                price=100.0,
                change=1.0,
                volume=1000000,
                amount=100000000.0,
            )
        ]

        trader._update_account_values(quotes)

        mock_position.update_market_value.assert_called_once_with(100.0)

    @pytest.mark.asyncio
    async def test_detect_market_regime(self, mock_components):
        """测试市场状态检测"""
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        trader = LiveTrader(
            account=mock_components["account"],
            policy_engine=mock_components["policy_engine"],
            survival_rules=mock_components["survival_rules"],
            matcher=mock_components["matcher"],
            tool_executor=mock_components["tool_executor"],
            config=config,
        )

        quotes = [
            QuoteData(
                symbol="600519",
                name="Test Stock",
                price=100.0,
                change=1.0,
                volume=1000000,
                amount=100000000.0,
            )
        ]

        regime = await trader._detect_market_regime(quotes)

        assert regime in MarketRegime

    def test_build_context(self, mock_components):
        """测试构建决策上下文"""
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        trader = LiveTrader(
            account=mock_components["account"],
            policy_engine=mock_components["policy_engine"],
            survival_rules=mock_components["survival_rules"],
            matcher=mock_components["matcher"],
            tool_executor=mock_components["tool_executor"],
            config=config,
        )

        quotes = [
            QuoteData(
                symbol="600519",
                name="Test Stock",
                price=100.0,
                change=1.0,
                volume=1000000,
                amount=100000000.0,
            )
        ]

        survival_state = Mock(level=SurvivalLevel.NORMAL)
        market_regime = MarketRegime.BULL

        context = trader._build_context(quotes, survival_state, market_regime)

        assert context.survival_level == SurvivalLevel.NORMAL
        assert context.market_regime == MarketRegime.BULL
        assert context.user_input != ""
        assert "Test Stock" in context.user_input
        assert "600519" in context.user_input

    def test_create_order_from_decision(self, mock_components):
        """测试从决策创建订单"""
        from core.schemas import Order, OrderSide, OrderType

        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        trader = LiveTrader(
            account=mock_components["account"],
            policy_engine=mock_components["policy_engine"],
            survival_rules=mock_components["survival_rules"],
            matcher=mock_components["matcher"],
            tool_executor=mock_components["tool_executor"],
            config=config,
        )

        decision = Decision(
            action="buy",
            symbol="600519",
            quantity=100,
            price=100.0,
            reasoning="Test decision",
            confidence=0.8,
        )

        order = trader._create_order_from_decision(decision)

        assert order.symbol == "600519"
        assert order.side == OrderSide.BUY
        assert order.quantity == 100
        assert order.price == 100.0
        assert order.order_type == OrderType.MARKET
        assert order.order_id.startswith("LIVE_")

    @pytest.mark.asyncio
    async def test_execute_decision_success(self, mock_components):
        """测试执行决策成功"""
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        trader = LiveTrader(
            account=mock_components["account"],
            policy_engine=mock_components["policy_engine"],
            survival_rules=mock_components["survival_rules"],
            matcher=mock_components["matcher"],
            tool_executor=mock_components["tool_executor"],
            config=config,
        )

        decision = Decision(
            action="buy",
            symbol="600519",
            quantity=100,
            price=100.0,
            reasoning="Test decision",
            confidence=0.8,
        )

        await trader._execute_decision(decision)

        assert trader.metrics.successful_trades == 1

    @pytest.mark.asyncio
    async def test_execute_decision_failure(self, mock_components):
        """测试执行决策失败"""
        mock_components["matcher"].match = AsyncMock(
            return_value=Mock(success=False, reason="No liquidity")
        )

        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        trader = LiveTrader(
            account=mock_components["account"],
            policy_engine=mock_components["policy_engine"],
            survival_rules=mock_components["survival_rules"],
            matcher=mock_components["matcher"],
            tool_executor=mock_components["tool_executor"],
            config=config,
        )

        decision = Decision(
            action="buy",
            symbol="600519",
            quantity=100,
            price=100.0,
            reasoning="Test decision",
            confidence=0.8,
        )

        await trader._execute_decision(decision)

        assert trader.metrics.failed_trades == 1


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_run_live_trader(mock_components):
    """测试运行实盘交易器"""
    config = {
        "trader": {
            "symbols": ["600519"],
            "decision_interval": 1,
            "enable_auto_trading": False,
            "dry_run": True,
        },
        "model": {},
    }

    # 模拟市场休市，快速退出
    with patch('src.trader.TraderConfig') as MockConfig:
        mock_config = Mock()
        mock_config.is_market_open.return_value = False
        mock_config.trading_symbols = ["600519"]
        mock_config.decision_interval_seconds = 1
        mock_config.max_position_ratio = 0.30
        mock_config.enable_auto_trading = False
        mock_config.dry_run = True
        mock_config.market_open_hour = 9
        mock_config.market_open_minute = 30
        mock_config.market_close_hour = 15
        mock_config.market_close_minute = 0
        MockConfig.return_value = mock_config

        # 这个测试会快速退出因为市场休市
        task = asyncio.create_task(
            run_live_trader(
                account=mock_components["account"],
                policy_engine=mock_components["policy_engine"],
                survival_rules=mock_components["survival_rules"],
                matcher=mock_components["matcher"],
                tool_executor=mock_components["tool_executor"],
                config=config,
            )
        )

        # 等待一小段时间
        await asyncio.sleep(0.1)

        # 取消任务
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass
