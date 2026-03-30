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
    # 模拟 execute 方法（异步）
    async def mock_execute(tool_name, **kwargs):
        if tool_name == "get_quote":
            return Mock(
                success=True,
                data=QuoteData(
                    symbol=kwargs.get("symbol", "600519"),
                    name="Test Stock",
                    price=100.0,
                    change=1.0,
                    volume=1000000,
                    amount=100000000.0,
                ),
                error=None,
                execution_time=0.1
            )
        return Mock(success=False, error="Unknown tool")
    tool_executor.execute = mock_execute
    # 兼容旧测试
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
        # 覆盖 execute 方法返回失败结果
        async def mock_execute_fail(tool_name, **kwargs):
            return Mock(success=False, error="Network error", data=None, execution_time=0.1)
        mock_components["tool_executor"].execute = mock_execute_fail

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


# ============================================================================
# Additional Coverage Tests
# ============================================================================

class TestLiveTraderEdgeCases:
    """测试 LiveTrader 边界情况"""

    @pytest.mark.asyncio
    async def test_stop_prints_summary(self, mock_components):
        """测试停止时打印摘要"""
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

        # 设置状态
        trader.running = True

        # 停止
        await trader.stop()

        # 验证
        assert not trader.running
        assert trader.should_stop is True

    @pytest.mark.asyncio
    async def test_trading_loop_market_closed(self, mock_components):
        """测试市场休市时的交易循环"""
        config = {
            "trader": {
                "symbols": ["600519"],
                "decision_interval": 1,
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

        with patch('src.trader.TraderConfig') as MockConfig:
            mock_config = Mock()
            mock_config.is_market_open.return_value = False  # 市场休市
            mock_config.trading_symbols = ["600519"]
            mock_config.decision_interval_seconds = 0.1
            mock_config.max_position_ratio = 0.30
            mock_config.enable_auto_trading = False
            mock_config.dry_run = True
            mock_config.market_open_hour = 9
            mock_config.market_open_minute = 30
            mock_config.market_close_hour = 15
            mock_config.market_close_minute = 0
            MockConfig.return_value = mock_config
            trader.config = mock_config

            trader.running = True

            # 运行一小段时间
            task = asyncio.create_task(trader._trading_loop())
            await asyncio.sleep(0.15)
            trader.should_stop = True

            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_trading_loop_no_quotes(self, mock_components):
        """测试获取不到行情时的交易循环"""
        config = {
            "trader": {
                "symbols": ["600519"],
                "decision_interval": 1,
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

        # Mock _get_quotes 返回空列表
        trader._get_quotes = AsyncMock(return_value=[])

        with patch('src.trader.TraderConfig') as MockConfig:
            mock_config = Mock()
            mock_config.is_market_open.return_value = True
            mock_config.trading_symbols = ["600519"]
            mock_config.decision_interval_seconds = 0.1
            mock_config.max_position_ratio = 0.30
            mock_config.enable_auto_trading = False
            mock_config.dry_run = True
            mock_config.market_open_hour = 9
            mock_config.market_open_minute = 30
            mock_config.market_close_hour = 15
            mock_config.market_close_minute = 0
            MockConfig.return_value = mock_config
            trader.config = mock_config

            trader.running = True

            # 运行一小段时间
            task = asyncio.create_task(trader._trading_loop())
            await asyncio.sleep(0.15)
            trader.should_stop = True

            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_trading_loop_no_decision(self, mock_components):
        """测试没有决策时的交易循环"""
        config = {
            "trader": {
                "symbols": ["600519"],
                "decision_interval": 1,
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

        # Mock 方法
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
        trader._get_quotes = AsyncMock(return_value=quotes)
        trader._generate_decision = AsyncMock(return_value=None)  # 无决策

        with patch('src.trader.TraderConfig') as MockConfig:
            mock_config = Mock()
            mock_config.is_market_open.return_value = True
            mock_config.trading_symbols = ["600519"]
            mock_config.decision_interval_seconds = 0.1
            mock_config.max_position_ratio = 0.30
            mock_config.enable_auto_trading = False
            mock_config.dry_run = True
            mock_config.market_open_hour = 9
            mock_config.market_open_minute = 30
            mock_config.market_close_hour = 15
            mock_config.market_close_minute = 0
            MockConfig.return_value = mock_config
            trader.config = mock_config

            trader.running = True

            # 运行一小段时间
            task = asyncio.create_task(trader._trading_loop())
            await asyncio.sleep(0.15)
            trader.should_stop = True

            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_trading_loop_wait_decision(self, mock_components):
        """测试等待决策时的交易循环"""
        config = {
            "trader": {
                "symbols": ["600519"],
                "decision_interval": 1,
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

        # Mock 方法
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
        trader._get_quotes = AsyncMock(return_value=quotes)
        trader._generate_decision = AsyncMock(
            return_value=Decision(
                action="wait",  # 使用 'wait' 而不是 'watch'
                symbol="600519",
                quantity=0,
                price=0.0,
                reasoning="Wait",
                confidence=0.5,
            )
        )

        with patch('src.trader.TraderConfig') as MockConfig:
            mock_config = Mock()
            mock_config.is_market_open.return_value = True
            mock_config.trading_symbols = ["600519"]
            mock_config.decision_interval_seconds = 0.1
            mock_config.max_position_ratio = 0.30
            mock_config.enable_auto_trading = False
            mock_config.dry_run = True
            mock_config.market_open_hour = 9
            mock_config.market_open_minute = 30
            mock_config.market_close_hour = 15
            mock_config.market_close_minute = 0
            MockConfig.return_value = mock_config
            trader.config = mock_config

            trader.running = True

            # 运行一小段时间
            task = asyncio.create_task(trader._trading_loop())
            await asyncio.sleep(0.15)
            trader.should_stop = True

            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_trading_loop_policy_rejection(self, mock_components):
        """测试风控拒绝时的交易循环"""
        config = {
            "trader": {
                "symbols": ["600519"],
                "decision_interval": 1,
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

        # Mock 方法
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
        trader._get_quotes = AsyncMock(return_value=quotes)
        trader._generate_decision = AsyncMock(
            return_value=Decision(
                action="buy",
                symbol="600519",
                quantity=100,
                price=100.0,
                reasoning="Buy",
                confidence=0.8,
            )
        )

        # Mock 风控拒绝
        mock_components["policy_engine"].validate_order = Mock(
            return_value=Mock(approved=False, reason="Risk limit")
        )

        with patch('src.trader.TraderConfig') as MockConfig:
            mock_config = Mock()
            mock_config.is_market_open.return_value = True
            mock_config.trading_symbols = ["600519"]
            mock_config.decision_interval_seconds = 0.1
            mock_config.max_position_ratio = 0.30
            mock_config.enable_auto_trading = False
            mock_config.dry_run = True
            mock_config.market_open_hour = 9
            mock_config.market_open_minute = 30
            mock_config.market_close_hour = 15
            mock_config.market_close_minute = 0
            MockConfig.return_value = mock_config
            trader.config = mock_config

            trader.running = True

            # 运行一小段时间
            task = asyncio.create_task(trader._trading_loop())
            await asyncio.sleep(0.15)
            trader.should_stop = True

            try:
                await task
            except asyncio.CancelledError:
                pass

        # 验证记录了拒绝
        assert trader.metrics.rejected_trades > 0

    @pytest.mark.asyncio
    async def test_trading_loop_iteration_exception(self, mock_components):
        """测试迭代异常处理"""
        config = {
            "trader": {
                "symbols": ["600519"],
                "decision_interval": 1,
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

        # Mock 方法抛出异常
        trader._get_quotes = AsyncMock(side_effect=Exception("Get quotes failed"))

        with patch('src.trader.TraderConfig') as MockConfig:
            mock_config = Mock()
            mock_config.is_market_open.return_value = True
            mock_config.trading_symbols = ["600519"]
            mock_config.decision_interval_seconds = 0.1
            mock_config.max_position_ratio = 0.30
            mock_config.enable_auto_trading = False
            mock_config.dry_run = True
            mock_config.market_open_hour = 9
            mock_config.market_open_minute = 30
            mock_config.market_close_hour = 15
            mock_config.market_close_minute = 0
            MockConfig.return_value = mock_config
            trader.config = mock_config

            trader.running = True

            # 运行一小段时间
            task = asyncio.create_task(trader._trading_loop())
            await asyncio.sleep(0.15)
            trader.should_stop = True

            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_get_quotes_exception(self, mock_components):
        """测试获取行情异常"""
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

        # Mock tool_executor 抛出异常
        mock_components["tool_executor"].execute = AsyncMock(side_effect=Exception("Tool failed"))

        quotes = await trader._get_quotes()

        # 应该返回空列表
        assert quotes == []

    @pytest.mark.asyncio
    async def test_detect_market_regime_no_quotes(self, mock_components):
        """测试无行情时的市场状态检测"""
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

        regime = await trader._detect_market_regime([])

        # 应该返回默认状态
        assert regime == MarketRegime.SIDEWAYS

    @pytest.mark.asyncio
    async def test_detect_market_regime_no_data_file(self, mock_components, tmp_path):
        """测试没有数据文件时的市场状态检测"""
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

        # 修改 data 目录路径到临时目录
        with patch('src.trader.Path') as MockPath:
            MockPath.return_value = tmp_path / "data" / "klines_600519.csv"

            regime = await trader._detect_market_regime(quotes)

            # 应该返回默认状态
            assert regime == MarketRegime.SIDEWAYS

    @pytest.mark.asyncio
    async def test_detect_market_regime_insufficient_data(self, mock_components, tmp_path):
        """测试数据不足时的市场状态检测"""
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

        # 创建数据文件，但数据不足
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        csv_file = data_dir / "klines_600519.csv"

        import pandas as pd
        df = pd.DataFrame({
            'date': pd.date_range(start='2026-01-01', periods=10),
            'open': [100] * 10,
            'high': [105] * 10,
            'low': [95] * 10,
            'close': [100] * 10,
            'volume': [1000000] * 10,
        })
        df.to_csv(csv_file, index=False)

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

        with patch('src.trader.Path') as MockPath:
            MockPath.return_value = csv_file

            regime = await trader._detect_market_regime(quotes)

            # 应该返回默认状态
            assert regime == MarketRegime.SIDEWAYS

    @pytest.mark.asyncio
    async def test_generate_decision_no_result(self, mock_components):
        """测试生成决策无结果"""
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

        # Mock react_loop 返回空结果
        trader.agent_loop.react_loop = AsyncMock(
            return_value=Mock(success=True, final_result={})
        )

        decision = await trader._generate_decision(
            quotes,
            Mock(level=SurvivalLevel.NORMAL),
            MarketRegime.BULL
        )

        # 应该返回 None
        assert decision is None

    @pytest.mark.asyncio
    async def test_generate_decision_exception(self, mock_components):
        """测试生成决策异常"""
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

        # Mock react_loop 抛出异常
        trader.agent_loop.react_loop = AsyncMock(side_effect=Exception("React failed"))

        decision = await trader._generate_decision(
            quotes,
            Mock(level=SurvivalLevel.NORMAL),
            MarketRegime.BULL
        )

        # 应该返回 None
        assert decision is None

    def test_build_context_without_csv(self, mock_components, tmp_path):
        """测试没有CSV文件时构建上下文"""
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

        # 修改路径到临时目录（没有数据文件）
        with patch('src.trader.Path') as MockPath:
            MockPath.return_value = tmp_path / "data" / "klines_600519.csv"

            context = trader._build_context(
                quotes,
                Mock(level=SurvivalLevel.NORMAL),
                MarketRegime.BULL
            )

            # 上下文应该仍然有效
            assert context is not None
            assert "Test Stock" in context.user_input

    def test_create_order_from_sell_decision(self, mock_components):
        """测试从卖出决策创建订单"""
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
            action="sell",
            symbol="600519",
            quantity=100,
            price=100.0,
            reasoning="Test decision",
            confidence=0.8,
        )

        order = trader._create_order_from_decision(decision)

        assert order.side == OrderSide.SELL

    @pytest.mark.asyncio
    async def test_execute_decision_account_update_failure(self, mock_components):
        """测试账户更新失败"""
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

        # Mock 账户更新失败
        mock_components["account"].update_from_trade.return_value = False

        decision = Decision(
            action="buy",
            symbol="600519",
            quantity=100,
            price=100.0,
            reasoning="Test decision",
            confidence=0.8,
        )

        await trader._execute_decision(decision)

        # 应该记录失败交易
        assert trader.metrics.failed_trades == 1

    @pytest.mark.asyncio
    async def test_execute_decision_exception(self, mock_components):
        """测试执行决策异常"""
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

        # Mock match 抛出异常
        mock_components["matcher"].match = AsyncMock(side_effect=Exception("Match failed"))

        decision = Decision(
            action="buy",
            symbol="600519",
            quantity=100,
            price=100.0,
            reasoning="Test decision",
            confidence=0.8,
        )

        await trader._execute_decision(decision)

        # 应该记录失败交易
        assert trader.metrics.failed_trades == 1

    def test_print_summary(self, mock_components):
        """测试打印摘要"""
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

        # 添加一些交易数据
        trader.metrics.record_decision(SurvivalLevel.NORMAL)
        trader.metrics.record_trade(success=True, pnl=1000.0)
        trader.metrics.record_trade(success=False)

        # 测试打印（应该不会抛出异常）
        trader._print_summary()


# ============================================================================
# 2026年A股节假日休市规则测试
# ============================================================================

class TestMarketHolidaysRules:
    """测试2026年A股节假日休市规则"""

    def test_weekend_closed(self):
        """测试周末休市"""
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        # 测试周六
        with patch('src.trader.datetime') as mock_datetime:
            # 2026年1月3日是周六
            saturday = datetime(2026, 1, 3, 10, 0, 0)
            mock_datetime.now.return_value = saturday

            trader_config = TraderConfig(config)
            assert trader_config.is_market_open() is False

        # 测试周日
        with patch('src.trader.datetime') as mock_datetime:
            # 2026年1月4日是周日
            sunday = datetime(2026, 1, 4, 10, 0, 0)
            mock_datetime.now.return_value = sunday

            trader_config = TraderConfig(config)
            assert trader_config.is_market_open() is False

    def test_new_year_holiday(self):
        """测试元旦休市（1月1日-1月3日）"""
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        # 测试元旦假期内
        # 使用 property mock 来模拟 weekday 方法
        mock_now = datetime(2026, 1, 2, 10, 0, 0)  # 周四

        with patch('src.trader.datetime') as mock_datetime:
            mock_datetime.now.return_value = mock_now

            trader_config = TraderConfig(config)
            # 元旦假期应该休市
            assert trader_config.is_market_open() is False

    def test_spring_festival_holiday(self):
        """测试春节休市（2月15日-2月23日）"""
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        # 测试春节假期内
        with patch('src.trader.datetime') as mock_datetime:
            # 2026年2月18日，春节假期内
            spring_day = datetime(2026, 2, 18, 10, 0, 0)
            mock_datetime.now.return_value = spring_day

            trader_config = TraderConfig(config)
            assert trader_config.is_market_open() is False

    def test_qingming_festival_holiday(self):
        """测试清明休市（4月4日-4月6日）"""
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        with patch('src.trader.datetime') as mock_datetime:
            # 2026年4月5日，清明假期内
            qingming_day = datetime(2026, 4, 5, 10, 0, 0)
            mock_datetime.now.return_value = qingming_day

            trader_config = TraderConfig(config)
            assert trader_config.is_market_open() is False

    def test_labor_day_holiday(self):
        """测试劳动节休市（5月1日-5月5日）"""
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        with patch('src.trader.datetime') as mock_datetime:
            # 2026年5月3日，劳动节假期内
            labor_day = datetime(2026, 5, 3, 10, 0, 0)
            mock_datetime.now.return_value = labor_day

            trader_config = TraderConfig(config)
            assert trader_config.is_market_open() is False

    def test_dragon_boat_festival_holiday(self):
        """测试端午节休市（6月19日-6月21日）"""
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        with patch('src.trader.datetime') as mock_datetime:
            # 2026年6月20日，端午假期内
            dragon_day = datetime(2026, 6, 20, 10, 0, 0)
            mock_datetime.now.return_value = dragon_day

            trader_config = TraderConfig(config)
            assert trader_config.is_market_open() is False

    def test_mid_autumn_festival_holiday(self):
        """测试中秋休市（9月25日-9月27日）"""
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        with patch('src.trader.datetime') as mock_datetime:
            # 2026年9月26日，中秋假期内
            mid_autumn_day = datetime(2026, 9, 26, 10, 0, 0)
            mock_datetime.now.return_value = mid_autumn_day

            trader_config = TraderConfig(config)
            assert trader_config.is_market_open() is False

    def test_national_day_holiday(self):
        """测试国庆休市（10月1日-10月7日）"""
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        with patch('src.trader.datetime') as mock_datetime:
            # 2026年10月5日，国庆假期内
            national_day = datetime(2026, 10, 5, 10, 0, 0)
            mock_datetime.now.return_value = national_day

            trader_config = TraderConfig(config)
            assert trader_config.is_market_open() is False

    def test_trading_hours(self):
        """测试交易时段（9:30-15:00）"""
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        # 测试正常交易日的交易时段内
        with patch('src.trader.datetime') as mock_datetime:
            # 2026年1月5日（周一）10:00，交易时段内
            trading_time = datetime(2026, 1, 5, 10, 0, 0)
            mock_datetime.now.return_value = trading_time

            trader_config = TraderConfig(config)
            assert trader_config.is_market_open() is True

    def test_before_trading_hours(self):
        """测试交易时段前"""
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        with patch('src.trader.datetime') as mock_datetime:
            # 2026年1月5日（周一）9:00，交易时段前
            before_trading = datetime(2026, 1, 5, 9, 0, 0)
            mock_datetime.now.return_value = before_trading

            trader_config = TraderConfig(config)
            assert trader_config.is_market_open() is False

    def test_after_trading_hours(self):
        """测试交易时段后"""
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        with patch('src.trader.datetime') as mock_datetime:
            # 2026年1月5日（周一）15:30，交易时段后
            after_trading = datetime(2026, 1, 5, 15, 30, 0)
            mock_datetime.now.return_value = after_trading

            trader_config = TraderConfig(config)
            assert trader_config.is_market_open() is False

    def test_holiday_boundaries(self):
        """测试节假日边界日期"""
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        with patch('src.trader.datetime') as mock_datetime:
            # 春节假期结束次日（2月24日，周二），应该开盘
            after_spring = datetime(2026, 2, 24, 10, 0, 0)
            mock_datetime.now.return_value = after_spring

            trader_config = TraderConfig(config)
            assert trader_config.is_market_open() is True

        with patch('src.trader.datetime') as mock_datetime:
            # 国庆假期结束次日（10月8日，周三），应该开盘
            after_national = datetime(2026, 10, 8, 10, 0, 0)
            mock_datetime.now.return_value = after_national

            trader_config = TraderConfig(config)
            assert trader_config.is_market_open() is True

    def test_weekday_after_holiday(self):
        """测试节假日后的工作日"""
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        with patch('src.trader.datetime') as mock_datetime:
            # 2026年2月27日（周五），春节后第一个完整周
            weekday_after_holiday = datetime(2026, 2, 27, 10, 0, 0)
            mock_datetime.now.return_value = weekday_after_holiday

            trader_config = TraderConfig(config)
            assert trader_config.is_market_open() is True

class TestHolidayExactMatching:
    """测试节假日精确匹配（Line 152）"""

    @patch('src.trader.datetime')
    def test_new_year_exact_match(self, mock_datetime):
        """测试元月1日精确匹配"""
        from src.trader import TraderConfig
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        mock_now = Mock()
        mock_now.month = 1
        mock_now.day = 1
        mock_now.weekday.return_value = 2
        mock_now.hour = 10
        mock_now.minute = 0
        mock_datetime.now.return_value = mock_now

        trader_config = TraderConfig(config)
        assert trader_config.is_market_open() is False


class TestCrossMonthHolidayDetection:
    """测试跨月假期检测（Lines 163-170）"""

    @patch('src.trader.datetime')
    def test_cross_month_holiday_start_month(self, mock_datetime):
        """测试跨月假期的起始月份"""
        from src.trader import TraderConfig
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        mock_now = Mock()
        mock_now.month = 2
        mock_now.day = 15
        mock_now.weekday.return_value = 6
        mock_now.hour = 10
        mock_now.minute = 0
        mock_datetime.now.return_value = mock_now

        trader_config = TraderConfig(config)
        assert trader_config.is_market_open() is False

    @patch('src.trader.datetime')
    def test_cross_month_holiday_middle_month(self, mock_datetime):
        """测试跨月假期的中间月份（Lines 169-170）"""
        from src.trader import TraderConfig
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        # 添加一个跨月假期进行测试
        original_holidays = TraderConfig.HOLIDAYS_2026.copy()
        TraderConfig.HOLIDAYS_2026[(1, 20)] = (2, 10)  # 1月20日到2月10日

        try:
            mock_now = Mock()
            mock_now.month = 2  # 中间月份
            mock_now.day = 1
            mock_now.weekday.return_value = 2
            mock_now.hour = 10
            mock_now.minute = 0
            mock_datetime.now.return_value = mock_now

            trader_config = TraderConfig(config)
            # 应该休市
            assert trader_config.is_market_open() is False
        finally:
            # 恢复原始节假日
            TraderConfig.HOLIDAYS_2026 = original_holidays

    @patch('src.trader.datetime')
    def test_cross_month_holiday_end_month(self, mock_datetime):
        """测试跨月假期的结束月份（Lines 166-167）"""
        from src.trader import TraderConfig
        config = {
            "trader": {"symbols": ["600519"], "decision_interval": 60},
            "model": {},
        }

        # 添加一个跨月假期进行测试
        original_holidays = TraderConfig.HOLIDAYS_2026.copy()
        TraderConfig.HOLIDAYS_2026[(1, 20)] = (2, 10)  # 1月20日到2月10日

        try:
            mock_now = Mock()
            mock_now.month = 2  # 结束月份
            mock_now.day = 5  # 在结束日期之前
            mock_now.weekday.return_value = 2
            mock_now.hour = 10
            mock_now.minute = 0
            mock_datetime.now.return_value = mock_now

            trader_config = TraderConfig(config)
            # 应该休市
            assert trader_config.is_market_open() is False
        finally:
            # 恢复原始节假日
            TraderConfig.HOLIDAYS_2026 = original_holidays


class TestLiveTraderAdditionalCoverage:
    """补充测试以覆盖更多代码路径"""

    @pytest.mark.asyncio
    async def test_start_logs_live_mode(self, mock_components, caplog):
        """测试实盘模式日志（Line 236）"""
        config = {
            "trader": {
                "symbols": ["600519"],
                "decision_interval": 60,
                "dry_run": False,  # 实盘模式
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

        # Mock model router initialize
        trader.agent_loop.model_router.initialize = AsyncMock()

        # Mock is_market_open to return True briefly
        with patch('src.trader.TraderConfig') as MockConfig:
            mock_config = Mock()
            mock_config.is_market_open.return_value = False  # 快速退出
            mock_config.trading_symbols = ["600519"]
            mock_config.decision_interval_seconds = 60
            mock_config.dry_run = False
            mock_config.enable_auto_trading = False
            mock_config.market_open_hour = 9
            mock_config.market_open_minute = 30
            mock_config.market_close_hour = 15
            mock_config.market_close_minute = 0
            MockConfig.return_value = mock_config
            trader.config = mock_config

            # 运行并立即停止
            task = asyncio.create_task(trader.start())
            await asyncio.sleep(0.05)
            trader.should_stop = True

            try:
                await task
            except asyncio.CancelledError:
                pass

        # 检查日志包含实盘模式信息
        # 注意：由于日志是异步的，我们只检查没有崩溃

    @pytest.mark.asyncio
    async def test_stop_calls_summary(self, mock_components):
        """测试stop方法调用打印摘要（Lines 258-259）"""
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

        # 添加一些数据
        trader.metrics.record_decision(SurvivalLevel.NORMAL)

        # 调用stop
        await trader.stop()

        # 验证状态已更新
        assert trader.running is False
        assert trader.should_stop is True

    @pytest.mark.asyncio
    async def test_auto_trading_enabled_executes_decision(self, mock_components):
        """测试自动交易启用时执行决策（Lines 337-340）"""
        config = {
            "trader": {
                "symbols": ["600519"],
                "decision_interval": 60,
                "enable_auto_trading": True,  # 启用自动交易
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

        # Mock decision
        decision = Decision(
            action="buy",
            symbol="600519",
            quantity=100,
            price=100.0,
            reasoning="Buy",
            confidence=0.8,
        )

        # Mock matcher to succeed
        mock_components["matcher"].match = AsyncMock(
            return_value=Mock(
                success=True,
                filled_quantity=100,
                filled_price=100.0,
                commission=5.0,
                stamp_duty=10.0,
                pnl=0.0,
            )
        )

        # Mock account update
        mock_components["account"].update_from_trade = Mock(return_value=True)

        # 调用execute_decision
        await trader._execute_decision(decision)

        # 验证撮合被调用
        mock_components["matcher"].match.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_market_regime_with_sufficient_data(self, mock_components, tmp_path):
        """测试有足够数据时的市场状态检测（Lines 416-450）"""
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

        # 创建包含足够数据的CSV文件
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        csv_file = data_dir / "klines_600519.csv"

        import pandas as pd
        df = pd.DataFrame({
            'date': pd.date_range(start='2026-01-01', periods=100),
            'open': [100 + i * 0.1 for i in range(100)],
            'high': [105 + i * 0.1 for i in range(100)],
            'low': [95 + i * 0.1 for i in range(100)],
            'close': [100 + i * 0.1 for i in range(100)],
            'volume': [1000000 + i * 10000 for i in range(100)],
        })
        df.to_csv(csv_file, index=False)

        quotes = [
            QuoteData(
                symbol="600519",
                name="Test Stock",
                price=110.0,
                change=10.0,
                volume=2000000,
                amount=200000000.0,
            )
        ]

        with patch('src.trader.Path') as MockPath:
            MockPath.return_value = csv_file

            regime = await trader._detect_market_regime(quotes)

            # 应该返回一个有效的市场状态
            assert regime in MarketRegime

    @pytest.mark.asyncio
    async def test_generate_decision_with_valid_result(self, mock_components):
        """测试生成有效决策（Lines 474-478）"""
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

        # Mock react_loop 返回有效结果
        expected_decision = Decision(
            action="buy",
            symbol="600519",
            quantity=100,
            price=100.0,
            reasoning="Buy signal",
            confidence=0.8,
        )

        trader.agent_loop.react_loop = AsyncMock(
            return_value=Mock(
                success=True,
                final_result={
                    'decision': {
                        'action': 'buy',
                        'symbol': '600519',
                        'quantity': 100,
                        'price': 100.0,
                        'reasoning': 'Buy signal',
                        'confidence': 0.8,
                    }
                }
            )
        )

        decision = await trader._generate_decision(
            quotes,
            Mock(level=SurvivalLevel.NORMAL),
            MarketRegime.BULL
        )

        # 验证返回了决策
        assert decision is not None
        assert decision.action == "buy"

    @pytest.mark.asyncio
    async def test_build_context_with_technical_indicators(self, mock_components, tmp_path):
        """测试构建包含技术指标的上下文（Lines 504-603）"""
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

        # 创建包含足够数据的CSV文件
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        csv_file = data_dir / "klines_600519.csv"

        import pandas as pd
        df = pd.DataFrame({
            'date': pd.date_range(start='2026-01-01', periods=100),
            'open': [100 + i * 0.5 for i in range(100)],
            'high': [105 + i * 0.5 for i in range(100)],
            'low': [95 + i * 0.5 for i in range(100)],
            'close': [100 + i * 0.5 for i in range(100)],
            'volume': [1000000 for _ in range(100)],
        })
        df.to_csv(csv_file, index=False)

        quotes = [
            QuoteData(
                symbol="600519",
                name="贵州茅台",
                price=150.0,
                change=10.0,
                volume=2000000,
                amount=300000000.0,
            )
        ]

        with patch('src.trader.Path') as MockPath:
            MockPath.return_value = csv_file

            context = trader._build_context(
                quotes,
                Mock(level=SurvivalLevel.NORMAL),
                MarketRegime.BULL
            )

            # 验证上下文包含技术分析信息
            assert "技术分析" in context.user_input
            assert "RSI" in context.user_input
            assert "MACD" in context.user_input
            assert "布林带" in context.user_input

    @pytest.mark.asyncio
    async def test_execute_decision_with_pnl(self, mock_components):
        """测试执行有盈亏的交易（Line 678）"""
        config = {
            "trader": {
                "symbols": ["600519"],
                "decision_interval": 60,
                "enable_auto_trading": True,
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

        # Mock decision
        decision = Decision(
            action="sell",
            symbol="600519",
            quantity=100,
            price=110.0,
            reasoning="Sell",
            confidence=0.8,
        )

        # Mock matcher to succeed with PnL
        mock_components["matcher"].match = AsyncMock(
            return_value=Mock(
                success=True,
                filled_quantity=100,
                filled_price=110.0,
                commission=5.0,
                stamp_duty=11.0,
                pnl=500.0,  # 有盈亏
            )
        )

        # Mock account update
        mock_components["account"].update_from_trade = Mock(return_value=True)

        # 调用execute_decision
        await trader._execute_decision(decision)

        # 验证记录了交易和盈亏
        assert trader.metrics.successful_trades == 1
        assert trader.metrics.total_pnl == 500.0

