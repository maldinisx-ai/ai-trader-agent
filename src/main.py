# -*- coding: utf-8 -*-
"""
主程序入口

AI Trader Agent 的统一 CLI 入口。
支持交易模式、回测模式、演示模式。
"""

import asyncio
import signal
import sys
import os
import pandas as pd
from pathlib import Path
from datetime import datetime

# 设置控制台输出编码为UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import click
import yaml

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.survival_rules import SurvivalRules
from core.policy_engine import PolicyEngine
from simulation.account import Account
from simulation.matcher import Matcher
from tools.data.get_quote import GetQuoteTool
from tools.trading.place_order import PlaceOrderTool
from tools.trading.cancel_order import CancelOrderTool
from tools.trading.get_positions import GetPositionsTool
from core.tool_executor import Tool, ToolExecutor
from core.schemas import SurvivalLevel, QuoteData
from core.reflection_storage import ReflectionStorage
from core.reflection import ReflectionEngine


# ============================================
# 本地数据工具
# ============================================

class LocalQuoteTool(Tool):
    """使用本地 CSV 数据的行情工具"""

    def __init__(self, data_dir: str = "data"):
        super().__init__()
        self.data_dir = Path(data_dir)
        self._cache = {}

    @property
    def name(self) -> str:
        return "get_quote"

    @property
    def description(self) -> str:
        return "获取股票行情（从本地 CSV 文件）"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "股票代码"},
            },
            "required": ["symbol"],
        }

    async def _execute(self, **kwargs) -> QuoteData:
        symbol = kwargs.get("symbol", "")
        if not symbol:
            raise ValueError("股票代码不能为空")

        # 从缓存获取
        if symbol in self._cache:
            return self._cache[symbol]

        # 读取本地 CSV 文件
        csv_path = self.data_dir / f"klines_{symbol}.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"找不到数据文件: {csv_path}")

        df = pd.read_csv(csv_path)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # 获取最新数据
        latest = df.iloc[-1]
        prev_close = df.iloc[-2]['close'] if len(df) > 1 else latest['open']
        change_pct = ((latest['close'] - prev_close) / prev_close) * 100

        quote = QuoteData(
            symbol=symbol,
            name="股票" + symbol,
            price=float(latest['close']),
            change=round(change_pct, 2),
            volume=int(latest['volume']),
            amount=float(latest['amount']),
            high=float(latest['high']),
            low=float(latest['low']),
            upper_limit=float(latest['close']) * 1.1,
            lower_limit=float(latest['close']) * 0.9,
        )

        # 缓存结果
        self._cache[symbol] = quote
        return quote


# ============================================
# 配置加载
# ============================================

def load_config(config_path: str = "config/config.yaml") -> dict:
    """
    加载配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        dict: 配置字典
    """
    config_file = PROJECT_ROOT / config_path
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


# ============================================
# 信号处理
# ============================================

class ShutdownHandler:
    """优雅退出处理器"""

    def __init__(self):
        self.should_exit = False
        self.setup_signal_handlers()

    def setup_signal_handlers(self):
        """设置信号处理器"""
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def handle_signal(self, signum, frame):
        """处理信号"""
        print("\n\n接收到退出信号，正在优雅关闭...")
        self.should_exit = True


# ============================================
# 组件初始化
# ============================================

def initialize_components(config: dict, mode: str):
    """
    初始化所有组件

    Args:
        config: 配置字典
        mode: 运行模式

    Returns:
        tuple: (account, policy_engine, survival_rules, matcher, tool_executor)
    """
    # 账户配置
    account_config = config.get("account", {})
    initial_cash = account_config.get("initial_cash", 1_000_000.0)
    db_path = account_config.get("db_path", "data/trading.db")

    # 创建账户
    account = Account(
        initial_cash=initial_cash,
        db_path=db_path,
    )

    # 风控引擎
    policy_engine = PolicyEngine(
        cash=account.cash,
        max_position_ratio=0.30,
    )

    # 生存规则
    survival_rules = SurvivalRules(initial_cash=initial_cash)

    # 撮合引擎
    matcher = Matcher()

    # 工具执行器
    data_provider = config.get("data", {}).get("provider", "mock")
    tool_executor = ToolExecutor()

    if data_provider == "mock":
        # 使用本地数据
        tool_executor.register(LocalQuoteTool(data_dir="data"))
    else:
        # 使用网络数据
        tool_executor.register(GetQuoteTool(use_real_data=True))

    tool_executor.register(PlaceOrderTool(policy_engine=policy_engine))
    tool_executor.register(CancelOrderTool(matcher=matcher))
    tool_executor.register(GetPositionsTool(account=account))

    return account, policy_engine, survival_rules, matcher, tool_executor


# ============================================
# 演示模式
# ============================================

async def demo_mode(account, matcher, tool_executor):
    """
    演示模式：模拟交易流程

    Args:
        account: 模拟账户
        matcher: 撮合引擎
        tool_executor: 工具执行器
    """
    from core.schemas import Order, QuoteData, OrderSide, OrderType

    print("=" * 50)
    print("AI Trader Agent - 演示模式")
    print("=" * 50)

    # 更新行情数据
    quote = QuoteData(
        symbol="600519",
        name="贵州茅台",
        price=1680.00,
        change=1.2,
        volume=1234567,
        amount=2100000000.0,
        high=1695.00,
        low=1675.00,
        upper_limit=1688.00,
        lower_limit=1672.00,
    )
    matcher.update_quote(quote)

    print(f"\n1. 当前行情: {quote.name} ({quote.symbol})")
    print(f"   价格: ¥{quote.price:.2f}  涨跌: {quote.change:+.2f}%")

    # 创建买入订单
    order = Order(
        order_id=f"DEMO_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        symbol="600519",
        side=OrderSide.BUY,
        quantity=100,
        price=1680.00,
        order_type=OrderType.MARKET,
    )

    print(f"\n2. 创建订单: {order.side.value.upper()} {order.quantity}股 @ ¥{order.price:.2f}")

    # 撮合
    match_result = await matcher.match(order)
    print(f"\n3. 撮合结果: {match_result.reason}")
    print(f"   成交数量: {match_result.filled_quantity} 股")
    print(f"   成交价格: ¥{match_result.filled_price:.2f}")

    # 更新账户
    success = account.update_from_trade(match_result)
    if success:
        print(f"\n4. 账户更新成功")
        account_info = account.get_account_info()
        print(f"   现金: ¥{account_info['cash']:,.2f}")
        print(f"   总资产: ¥{account_info['total_value']:,.2f}")

        positions = account.get_positions()
        if positions:
            pos = positions[0]
            print(f"   持仓: {pos.symbol} {pos.shares}股")
            print(f"   成本: ¥{pos.avg_cost:.2f}")
            print(f"   市值: ¥{pos.market_value:,.2f}")
            print(f"   盈亏: ¥{pos.pnl:+,.2f} ({pos.pnl_ratio*100:+.2f}%)")

    print("\n" + "=" * 50)
    print("演示完成！")
    print("=" * 50)


# ============================================
# 交易模式
# ============================================

async def trade_mode(account, policy_engine, survival_rules, matcher, tool_executor, config: dict):
    """
    交易模式：实时交易循环

    Args:
        account: 模拟账户
        policy_engine: 风控引擎
        survival_rules: 生存规则
        matcher: 撮合引擎
        tool_executor: 工具执行器
        config: 配置字典
    """
    from src.trader import run_live_trader

    print("=" * 50)
    print("AI Trader Agent - 交易模式")
    print("=" * 50)

    # 运行实盘交易器
    await run_live_trader(
        account=account,
        policy_engine=policy_engine,
        survival_rules=survival_rules,
        matcher=matcher,
        tool_executor=tool_executor,
        config=config,
    )


# ============================================
# 回测模式
# ============================================

async def backtest_mode(start_date: str, end_date: str, symbols: str):
    """
    回测模式：历史数据回测

    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        symbols: 股票代码列表（逗号分隔）
    """
    from src.backtester import run_backtest

    print("=" * 50)
    print("AI Trader Agent - 回测模式")
    print("=" * 50)
    print(f"\n回测区间: {start_date} ~ {end_date}")

    # 解析股票代码
    symbol_list = [s.strip() for s in symbols.split(",")]
    print(f"股票代码: {', '.join(symbol_list)}")

    # 运行回测
    result = run_backtest(
        start_date=start_date,
        end_date=end_date,
        symbols=symbol_list,
    )

    # 返回结果
    return result


# ============================================
# CLI 命令
# ============================================

@click.group()
@click.version_option(version="0.1.0")
def cli():
    """AI Trader Agent - 智能股票交易系统"""
    pass


@cli.command()
@click.option('--config', '-c', default='config/config.yaml', help='配置文件路径')
@click.option('--mode', '-m', type=click.Choice(['demo', 'trade', 'backtest']),
              default='demo', help='运行模式')
@click.option('--symbol', '-s', help='股票代码 (交易模式)')
@click.option('--symbols', help='股票代码列表，逗号分隔 (回测模式)')
@click.option('--start', help='开始日期 (回测模式 YYYY-MM-DD)')
@click.option('--end', help='结束日期 (回测模式 YYYY-MM-DD)')
def run(config, mode, symbol, symbols, start, end):
    """
    运行 AI Trader Agent
    """
    # 加载配置
    cfg = load_config(config)

    # 初始化组件
    account, policy_engine, survival_rules, matcher, tool_executor = initialize_components(cfg, mode)

    # 设置退出处理器
    shutdown_handler = ShutdownHandler()

    # 运行对应模式
    if mode == 'demo':
        asyncio.run(demo_mode(account, matcher, tool_executor))

    elif mode == 'trade':
        if not symbol:
            click.echo("错误: 交易模式需要指定 --symbol 参数")
            sys.exit(1)
        asyncio.run(trade_mode(account, policy_engine, survival_rules, matcher, tool_executor, cfg))

    elif mode == 'backtest':
        if not start or not end:
            click.echo("错误: 回测模式需要指定 --start 和 --end 参数")
            sys.exit(1)
        if not symbols:
            click.echo("错误: 回测模式需要指定 --symbols 参数")
            sys.exit(1)
        asyncio.run(backtest_mode(start, end, symbols))


@cli.command()
def status():
    """显示账户状态"""
    config = load_config()
    account, _, _, _, _ = initialize_components(config, 'demo')

    info = account.get_account_info()

    print("=" * 50)
    print("账户状态")
    print("=" * 50)
    print(f"初始资金: ¥{info['initial_cash']:,.2f}")
    print(f"当前现金: ¥{info['cash']:,.2f}")
    print(f"持仓市值: ¥{info['position_value']:,.2f}")
    print(f"总资产:   ¥{info['total_value']:,.2f}")
    print(f"盈亏:     ¥{info['profit_loss']:+,.2f} ({info['profit_loss_ratio']*100:+.2f}%)")
    print(f"持仓数量: {info['position_count']}")
    print("=" * 50)

    positions = account.get_positions()
    if positions:
        print("\n持仓明细:")
        for pos in positions:
            print(f"  {pos.symbol}: {pos.shares}股 @ ¥{pos.avg_cost:.2f}")
            print(f"    市值: ¥{pos.market_value:,.2f}  盈亏: ¥{pos.pnl:+,.2f}")


@cli.command()
@click.option('--reset', is_flag=True, help='重置账户')
def account(reset):
    """账户管理"""
    import os
    config = load_config()

    if reset:
        db_path = config.get("account", {}).get("db_path", "data/trading.db")
        db_file = PROJECT_ROOT / db_path

        if db_file.exists():
            os.remove(db_file)
            click.echo("账户已重置")
        else:
            click.echo("账户不存在")
    else:
        config = load_config()
        acc, _, _, _, _ = initialize_components(config, 'demo')

        info = acc.get_account_info()

        print("=" * 50)
        print("账户状态")
        print("=" * 50)
        print(f"初始资金: ¥{info['initial_cash']:,.2f}")
        print(f"当前现金: ¥{info['cash']:,.2f}")
        print(f"持仓市值: ¥{info['position_value']:,.2f}")
        print(f"总资产:   ¥{info['total_value']:,.2f}")
        print(f"盈亏:     ¥{info['profit_loss']:+,.2f} ({info['profit_loss_ratio']*100:+.2f}%)")
        print(f"持仓数量: {info['position_count']}")
        print("=" * 50)

        positions = acc.get_positions()
        if positions:
            print("\n持仓明细:")
            for pos in positions:
                print(f"  {pos.symbol}: {pos.shares}股 @ ¥{pos.avg_cost:.2f}")
                print(f"    市值: ¥{pos.market_value:,.2f}  盈亏: ¥{pos.pnl:+,.2f}")


@cli.command()
@click.option('--host', '-h', default='0.0.0.0', help='监听地址')
@click.option('--port', '-p', default=8000, help='监听端口')
def monitor(host, port):
    """启动监控面板"""
    try:
        from monitoring.app import start_monitoring
        click.echo(f"启动监控面板: http://{host}:{port}")
        start_monitoring(host, port)
    except ImportError:
        click.echo("错误: 监控面板未安装或 fastapi 未安装")
        click.echo("请运行: pip install fastapi uvicorn")
        sys.exit(1)


@cli.command()
@click.option('--symbol', '-s', default='600519', help='股票代码（单个分析）')
@click.option('--all', 'scan_all', is_flag=True, help='扫描所有本地股票')
@click.option('--limit', '-l', default=20, help='扫描股票数量限制（默认20，避免token过多）')
@click.option('--config', '-c', default='config/config.yaml', help='配置文件路径')
def ai(symbol, scan_all, limit, config):
    """测试 AI 决策"""
    from core.agent_loop import AgentLoop
    from core.model_router import ModelRouter
    from core.market_regime import MarketRegimeDetector
    from core.reflection import ReflectionEngine
    from core.reflection_storage import ReflectionStorage
    from tools.data.local_data_loader import LocalDataLoader

    # 加载配置和初始化组件
    cfg = load_config(config)
    account, policy_engine, survival_rules, _, tool_executor = initialize_components(cfg, 'demo')

    # 初始化反思引擎
    reflection_storage = ReflectionStorage(db_path="data/reflections.db")
    reflection_engine = ReflectionEngine(storage=reflection_storage)

    print("=" * 60)
    if scan_all:
        print("AI Trader Agent - 市场扫描")
    else:
        print("AI Trader Agent - 决策测试")
    print("=" * 60)

    # 初始化模型
    print("\n[初始化] AI 模型...")
    model_router = ModelRouter()

    async def run_ai():
        try:
            await model_router.initialize()
        except Exception as e:
            print(f"[错误] 模型初始化失败: {e}")
            return

        # 初始化 Agent Loop
        agent_loop = AgentLoop(
            model_router=model_router,
            survival_rules=survival_rules,
            market_detector=MarketRegimeDetector(),
            tool_executor=tool_executor,
            policy_engine=policy_engine,
            reflection_engine=reflection_engine,  # 传入反思引擎
            max_iterations=3,
        )

        # 加载市场数据
        data_loader = LocalDataLoader(data_dir="data")

        if scan_all:
            # 扫描所有股票（使用限制）
            market_data = data_loader.load_all_stocks(limit=limit)
            stock_count = market_data.get("total_count", 0)
            total_available = len(data_loader.get_available_symbols())
            print(f"\n[数据] 扫描市场: {stock_count} 只股票 (总共 {total_available} 只，限制 {limit} 只)")

            # 显示概览
            if "stocks" in market_data:
                for stock in market_data["stocks"]:
                    latest = stock["latest"]
                    print(f"   {stock['symbol']}: ¥{latest['close']:.2f} ({latest['change']:+.2f}%)")

            user_input = f"分析扫描的 {stock_count} 只股票的K线数据、技术指标、行业资金流向等，找出最具交易机会的股票并给出具体建议（买入/卖出/等待，包括股票代码、数量、价格）"
        else:
            # 分析单个股票
            print(f"\n[数据] 加载 {symbol} 的完整市场数据...")
            market_data = data_loader.load_all_data(symbol)

            # 显示基本行情
            if "klines" in market_data and "latest" in market_data["klines"]:
                latest = market_data["klines"]["latest"]
                print(f"   日期: {latest['date']}")
                print(f"   价格: ¥{latest['close']:.2f}")
                print(f"   涨跌: {latest['change']:+.2f}%")
                print(f"   成交量: {latest['volume']:,} 手")

            user_input = f"分析股票 {symbol} 的K线数据、技术指标、行业资金流向等信息，给出交易建议"

        # 运行决策
        account_info = account.get_account_info()
        print(f"\n[账户] 现金: ¥{account_info['cash']:,.2f}")

        print(f"\n[AI] 分析中...")
        response = await agent_loop.react_loop(
            user_input=user_input,
            current_cash=account_info['cash'],
            total_value=account_info['total_value'],
            initial_cash=account_info['initial_cash'],
            positions=account.get_positions(),
            market_data=market_data,
        )

        # 输出结果
        print("\n" + "=" * 60)
        print("决策结果")
        print("=" * 60)

        if response.success:
            print(f"\n状态: 成功")
            decision = response.final_result['decision']
            print(f"\n动作: {decision['action'].upper()}")
            if decision.get('symbol'):
                print(f"股票: {decision['symbol']}")
            if decision.get('quantity'):
                print(f"数量: {decision['quantity']} 股")
            if decision.get('price'):
                print(f"价格: ¥{decision['price']:.2f}")
            print(f"置信度: {decision['confidence']:.2f}")
            print(f"\n推理:")
            print(f"  {decision['reasoning']}")
            print(f"\n执行时间: {response.execution_time:.2f}秒")
        else:
            print(f"\n失败: {response.message}")

        print("=" * 60)

    asyncio.run(run_ai())


# ============================================
# 主入口
# ============================================

if __name__ == "__main__":
    cli()