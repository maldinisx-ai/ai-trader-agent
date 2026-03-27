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
from tools.trading.get_positions import GetPositionsTool
from core.tool_executor import ToolExecutor
from core.schemas import SurvivalLevel


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
    use_real_data = config.get("data", {}).get("provider") == "akshare"
    tool_executor = ToolExecutor()
    tool_executor.register(GetQuoteTool(use_real_data=use_real_data))
    tool_executor.register(PlaceOrderTool(policy_engine=policy_engine))
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


# ============================================
# 主入口
# ============================================

if __name__ == "__main__":
    cli()