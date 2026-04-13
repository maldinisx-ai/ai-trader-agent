# -*- coding: utf-8 -*-
"""
回测脚本 - 使用真实K线数据

用法:
    python scripts/run_backtest.py 600519                    # 默认策略回测
    python scripts/run_backtest.py 600519 --strategy macd    # 使用MACD策略
    python scripts/run_backtest.py 600519 --days 180         # 回测最近180天
"""

import argparse
import sys
import os
import io
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# 设置控制台输出编码为UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from core.schemas import QuoteData, Decision
from src.backtester import BacktestEngine
from src.strategies.ma_cross import MACrossStrategy, TripleMACrossStrategy
from src.strategies.base import StrategyConfig


def load_kline_data(symbol: str, data_path: Optional[str] = None) -> List[QuoteData]:
    """
    加载K线数据并转换为QuoteData格式

    Args:
        symbol: 股票代码
        data_path: 数据文件路径（默认从 data/klines_{symbol}.csv）

    Returns:
        List[QuoteData]: 行情数据列表
    """
    if data_path is None:
        data_path = PROJECT_ROOT / f"data/klines_{symbol}.csv"

    df = pd.read_csv(data_path)
    df['date'] = pd.to_datetime(df['date'])

    # 转换为 QuoteData
    quotes = []
    stock_name = {
        '600519': '贵州茅台',
        '000001': '平安银行',
        '002594': '比亚迪'
    }.get(symbol, f'股票{symbol}')

    for _, row in df.iterrows():
        # 计算涨跌幅
        change = 0.0
        if len(quotes) > 0:
            prev_close = quotes[-1].price
            if prev_close > 0:
                change = ((row['close'] - prev_close) / prev_close) * 100

        quotes.append(QuoteData(
            symbol=symbol,
            name=stock_name,
            price=float(row['close']),
            change=change,
            volume=int(row['volume']),  # 手
            amount=float(row['amount']),  # 元
            high=float(row['high']),
            low=float(row['low']),
            open=float(row['open']),
            timestamp=row['date'],
        ))

    return quotes


def create_strategy(name: str, params: Dict[str, Any] = None):
    """
    创建策略实例

    Args:
        name: 策略名称
        params: 策略参数

    Returns:
        策略函数
    """
    params = params or {}

    if name == "ma_cross":
        # 双均线交叉策略
        config = StrategyConfig(
            name="ma_cross",
            params={
                "fast_period": params.get("fast", 5),
                "slow_period": params.get("slow", 20),
                "max_position_ratio": 0.30,
            }
        )
        strategy = MACrossStrategy(config)

        def strategy_fn(analyzer, account_info):
            signal = strategy.generate_signal(analyzer, account_info)
            if signal:
                return Decision(
                    action="buy" if signal.signal_type.value == "buy" else "sell",
                    symbol=signal.symbol,
                    quantity=signal.quantity,
                    price=signal.price,
                    reasoning=signal.reasoning,
                    confidence=signal.confidence,
                )
            return None

        return strategy_fn

    elif name == "triple_ma":
        # 三均线交叉策略
        config = StrategyConfig(
            name="triple_ma",
            params={
                "short_period": params.get("short", 5),
                "medium_period": params.get("medium", 10),
                "long_period": params.get("long", 30),
                "max_position_ratio": 0.30,
            }
        )
        strategy = TripleMACrossStrategy(config)

        def strategy_fn(analyzer, account_info):
            signal = strategy.generate_signal(analyzer, account_info)
            if signal:
                return Decision(
                    action="buy" if signal.signal_type.value == "buy" else "sell",
                    symbol=signal.symbol,
                    quantity=signal.quantity,
                    price=signal.price,
                    reasoning=signal.reasoning,
                    confidence=signal.confidence,
                )
            return None

        return strategy_fn

    else:
        # 默认策略（回测引擎内置）
        return None


class RealDataBacktestEngine(BacktestEngine):
    """使用真实数据的回测引擎"""

    def load_historical_data(self, data_path: Optional[str] = None) -> bool:
        """
        加载真实历史数据

        Args:
            data_path: 数据文件路径（可选）

        Returns:
            是否成功加载
        """
        for symbol in self.symbols:
            try:
                self.historical_data[symbol] = load_kline_data(symbol, data_path)
                print(f"[INFO] 成功加载 {symbol} 的 {len(self.historical_data[symbol])} 条K线数据")
            except FileNotFoundError:
                print(f"[ERROR] 未找到 {symbol} 的K线数据文件")
                print(f"[HINT] 请先运行: python scripts/fetch_klines.py {symbol}")
                return False
            except Exception as e:
                print(f"[ERROR] 加载 {symbol} 数据失败: {e}")
                return False

        return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="回测脚本 - 使用真实K线数据")
    parser.add_argument("symbol", type=str, help="股票代码 (如 600519)")
    parser.add_argument("--strategy", type=str, default="ma_cross",
                       choices=["ma_cross", "triple_ma", "default"],
                       help="策略类型（默认: ma_cross）")
    parser.add_argument("--initial-cash", type=float, default=100000.0,
                       help="初始资金（默认: 100000）")
    parser.add_argument("--fast", type=int, default=5,
                       help="快线周期（默认: 5）")
    parser.add_argument("--slow", type=int, default=20,
                       help="慢线周期（默认: 20）")
    parser.add_argument("--output", type=str, help="报告输出路径")

    args = parser.parse_args()

    # 显示回测配置
    print("=" * 60)
    print("回测配置")
    print("=" * 60)
    print(f"股票代码: {args.symbol}")
    print(f"策略类型: {args.strategy}")
    print(f"初始资金: ¥{args.initial_cash:,.2f}")
    if args.strategy == "ma_cross":
        print(f"快线周期: MA{args.fast}")
        print(f"慢线周期: MA{args.slow}")
    print("=" * 60)

    # 加载数据获取日期范围
    try:
        quotes = load_kline_data(args.symbol)
        start_date = quotes[0].timestamp.strftime("%Y-%m-%d")
        end_date = quotes[-1].timestamp.strftime("%Y-%m-%d")
        print(f"数据范围: {start_date} 至 {end_date}")
        print(f"数据数量: {len(quotes)} 条K线\n")
    except Exception as e:
        print(f"[ERROR] 无法加载数据: {e}")
        return 1

    # 创建策略
    strategy_params = {}
    if args.strategy == "ma_cross":
        strategy_params = {"fast": args.fast, "slow": args.slow}
    strategy = create_strategy(args.strategy, strategy_params)

    # 运行回测
    engine = RealDataBacktestEngine(
        initial_cash=args.initial_cash,
        start_date=start_date,
        end_date=end_date,
        symbols=[args.symbol],
        strategy=strategy,
    )

    results = engine.run()

    # 保存报告
    if results and args.output:
        import json
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n[INFO] 报告已保存到: {args.output}")

    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
