#!/usr/bin/env python3
"""
策略评分系统使用示例

演示如何使用策略评分引擎分析股票。
"""
import sys
import pandas as pd
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategy import get_strategy_manager, StrategyExecutor
from src.strategy.data_preparer import MarketDataPreparer


def create_sample_kline_data():
    """创建示例 K线数据"""
    import numpy as np
    from datetime import datetime, timedelta

    # 生成120天的模拟数据
    dates = [datetime.now() - timedelta(days=i) for i in range(120, 0, -1)]

    # 模拟上升趋势股票
    base_price = 100
    trend = 0.002  # 每日0.2%的上升趋势
    volatility = 0.02  # 2%的波动率

    np.random.seed(42)

    data = []
    price = base_price

    for date in dates:
        # 生成价格
        change = trend + np.random.normal(0, volatility)
        price = price * (1 + change)

        # 生成开高低收
        high = price * (1 + abs(np.random.normal(0, 0.01)))
        low = price * (1 - abs(np.random.normal(0, 0.01)))
        open_price = low + (high - low) * np.random.random()

        # 生成成交量（基础量 + 随机波动）
        base_volume = 1000000
        volume = int(base_volume * (1 + np.random.normal(0, 0.3)))

        data.append({
            "date": date.strftime("%Y-%m-%d"),
            "open": round(open_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(price, 2),
            "volume": volume,
        })

    return pd.DataFrame(data)


def create_sample_financial_data():
    """创建示例财务数据"""
    return {
        "pe": 12.5,
        "pb": 1.8,
        "ps": 8.0,
        "roe": 18.5,
        "roa": 6.2,
        "dividend_yield": 3.2,
        "debt_ratio": 45.0,
        "current_ratio": 1.8,
        "revenue_growth": 15.2,
        "profit_growth": 22.8,
    }


def main():
    """主函数"""
    print("=" * 60)
    print("策略评分系统使用示例")
    print("=" * 60)

    # 1. 创建示例数据
    print("\n[生成示例 K线数据...]")
    kline_df = create_sample_kline_data()
    print(f"   数据周期: {kline_df['date'].min()} 至 {kline_df['date'].max()}")
    print(f"   最新价格: {kline_df['close'].iloc[-1]:.2f}")
    print(f"   期间涨跌: {(kline_df['close'].iloc[-1] / kline_df['close'].iloc[0] - 1) * 100:+.2f}%")

    # 2. 准备财务数据
    print("\n[准备财务数据...]")
    financial_data = create_sample_financial_data()
    print(f"   PE: {financial_data['pe']}")
    print(f"   PB: {financial_data['pb']}")
    print(f"   ROE: {financial_data['roe']}%")

    # 3. 初始化策略管理器
    print("\n[初始化策略管理器...]")
    manager = get_strategy_manager()
    print(f"   已加载策略: {len(manager.strategies)} 个")

    # 4. 激活策略
    print("\n[激活策略...]")
    manager.activate(["momentum_trend", "value_reversal"])
    active = manager.get_active_strategies()
    print(f"   已激活: {[s.display_name for s in active]}")

    # 5. 执行分析
    print("\n[执行策略分析...]")
    executor = StrategyExecutor(manager)

    result = executor.analyze_from_csv(
        stock_code="600519",
        stock_name="贵州茅台",
        kline_df=kline_df,
        financial_df=None,  # 可以传入财务数据
    )

    # 6. 输出结果
    print("\n" + "=" * 60)
    print("分析结果")
    print("=" * 60)

    print(f"\n股票: {result.stock_name} ({result.stock_code})")
    print(f"综合评分: {result.overall_score}/100")
    print(f"综合信号: {result.overall_signal.upper()}")
    print(f"置信度: {result.overall_confidence:.2f}")

    print(f"\n使用策略: {', '.join([s.display_name for s in manager.get_active_strategies()])}")

    print("\n" + "-" * 60)
    print("各策略评分详情:")
    print("-" * 60)

    for signal in result.signals:
        print(f"\n[{signal.display_name}]")
        print(f"评分: {signal.score}/100")
        print(f"信号: {signal.signal.upper()}")
        print(f"置信度: {signal.confidence:.2f}")

        if signal.entry_price:
            print(f"买入价: {signal.entry_price:.2f}")
        if signal.stop_loss:
            print(f"止损价: {signal.stop_loss:.2f}")
        if signal.take_profit:
            print(f"目标价: {signal.take_profit:.2f}")

        print(f"\n推理分析:")
        print(signal.reasoning)

    # 7. 市场数据摘要
    if result.market_data:
        print("\n" + "-" * 60)
        print("关键市场指标:")
        print("-" * 60)
        m = result.market_data
        print(f"MA5:  {m.get('ma5', 'N/A'):.2f}")
        print(f"MA10: {m.get('ma10', 'N/A'):.2f}")
        print(f"MA20: {m.get('ma20', 'N/A'):.2f}")
        print(f"乖离率(MA5): {m.get('bias_ma5', 0):+.2f}%")
        print(f"量比: {m.get('volume_ratio', 1):.2f}")
        print(f"20日涨幅: {m.get('n20_gain_pct', 0):+.2f}%")

    print("\n" + "=" * 60)
    print("分析完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
