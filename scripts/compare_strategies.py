# -*- coding: utf-8 -*-
"""
策略对比分析脚本

对比 LLM Agent 策略与传统量化策略的回测结果。

用法:
    # 对比单只股票
    python scripts/compare_strategies.py 600519

    # 指定策略类型
    python scripts/compare_strategies.py 600519 --strategies ma_cross,agent

    # 使用已有的回测结果
    python scripts/compare_strategies.py 600519 --use-existing
"""

import asyncio
import argparse
import sys
import os
import io
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import json

# 设置控制台输出编码为UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_backtest_results(result_dir: Path) -> Dict[str, Any]:
    """加载回测结果"""
    report_file = result_dir / "backtest_report.json"

    if not report_file.exists():
        return None

    with open(report_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_comparison_chart(
    results: Dict[str, Dict[str, Any]],
    output_path: Path,
):
    """生成对比图表"""
    try:
        import pandas as pd
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        import numpy as np

        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
        plt.rcParams['axes.unicode_minus'] = False

        # 创建对比数据
        comparison_data = []

        for strategy_name, result in results.items():
            if result is None:
                continue

            performance = result.get('performance', {})

            comparison_data.append({
                'strategy': strategy_name,
                'total_return': result.get('total_return', 0) * 100,
                'total_pnl': result.get('total_pnl', 0),
                'total_trades': result.get('total_trades', 0),
                'sharpe_ratio': performance.get('sharpe_ratio', 0),
                'max_drawdown': performance.get('max_drawdown', 0) * 100,
                'win_rate': performance.get('win_rate', 0) * 100,
            })

        df = pd.DataFrame(comparison_data)

        # 创建图表
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))

        # 1. 总收益率对比
        bars = axes[0, 0].bar(df['strategy'], df['total_return'],
                                color='#3498DB', alpha=0.7)
        axes[0, 0].axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        axes[0, 0].set_title('总收益率对比', fontsize=14, fontweight='bold')
        axes[0, 0].set_ylabel('收益率 (%)')
        axes[0, 0].grid(True, alpha=0.3, axis='y')

        # 添加数值标签
        for bar in bars:
            height = bar.get_height()
            axes[0, 0].text(bar.get_x() + bar.get_width() / 2., height,
                           f'{height:.1f}%', ha='center', va='bottom' if height >= 0 else 'top',
                           fontsize=10)

        # 2. 夏普比率对比
        colors = ['#2ECC71' if x > 1 else '#E74C3C' for x in df['sharpe_ratio']]
        axes[0, 1].bar(df['strategy'], df['sharpe_ratio'], color=colors, alpha=0.7)
        axes[0, 1].axhline(y=1.0, color='red', linestyle='--', alpha=0.5, label='基准线')
        axes[0, 1].set_title('夏普比率对比', fontsize=14, fontweight='bold')
        axes[0, 1].set_ylabel('夏普比率')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3, axis='y')

        for bar in bars:
            height = bar.get_height()
            axes[0, 1].text(bar.get_x() + bar.get_width() / 2., height,
                           f'{height:.2f}', ha='center', va='bottom' if height >= 0 else 'top',
                           fontsize=10)

        # 3. 最大回撤对比
        axes[1, 0].bar(df['strategy'], df['max_drawdown'],
                     color='#E74C3C', alpha=0.7)
        axes[1, 0].set_title('最大回撤对比', fontsize=14, fontweight='bold')
        axes[1, 0].set_ylabel('回撤 (%)')
        axes[1, 0].grid(True, alpha=0.3, axis='y')

        for bar in bars:
            height = bar.get_height()
            axes[1, 0].text(bar.get_x() + bar.get_width() / 2., height,
                           f'{height:.1f}%', ha='center', va='top',
                           fontsize=10)

        # 4. 综合指标雷达图
        categories = ['收益率', '夏普比率', '胜率', '交易频率']

        # 归一化数据（0-1）
        normalized = {}
        for _, row in df.iterrows():
            normalized[row['strategy']] = [
                max(0, min(1, row['total_return'] / 50 + 0.5)),  # 假设±50%为范围
                max(0, min(1, row['sharpe_ratio'] / 2)),  # 假设0-2为范围
                row['win_rate'] / 100,
                max(0, min(1, row['total_trades'] / 100))  # 假设100笔为上限
            ]

        # 绘制雷达图
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        angles += angles[:1]

        fig_radar = plt.figure(figsize=(8, 8))
        ax_radar = fig_radar.add_subplot(111, polar=True)

        for strategy, values in normalized.items():
            values += values[:1]
            color = '#2ECC71' if strategy == 'agent_llm' else '#3498DB'
            ax_radar.plot(angles, values, 'o-', linewidth=2, label=strategy, color=color)
            ax_radar.fill(angles, values, alpha=0.15, color=color)

        ax_radar.set_xticks(angles[:-1])
        ax_radar.set_xticklabels(categories)
        ax_radar.set_ylim(0, 1)
        ax_radar.set_title('策略综合对比', fontsize=14, fontweight='bold', pad=20)
        ax_radar.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
        ax_radar.grid(True)

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close(fig_radar)

        print(f"✅ 对比图表已保存: {output_path}")

    except Exception as e:
        print(f"⚠️  生成对比图表失败: {e}")


def generate_comparison_report(
    results: Dict[str, Dict[str, Any]],
    output_path: Path,
):
    """生成对比报告"""
    report_lines = [
        "=" * 80,
        "策略对比分析报告",
        "=" * 80,
        "",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    # 策略列表
    report_lines.extend([
        "对比策略:",
        *[f"  - {name}" for name in results.keys() if results[name] is not None],
        "",
        "-" * 80,
        "",
    ])

    # 指标对比表
    report_lines.append("核心指标对比:")
    report_lines.append("")

    # 表头
    headers = ['策略', '总收益率', '夏普比率', '最大回撤', '胜率', '交易次数']
    report_lines.append(f"{'策略':<15} {'收益率':<12} {'夏普比率':<12} {'最大回撤':<12} {'胜率':<12} {'交易次数':<10}")
    report_lines.append("-" * 80)

    # 数据行
    for strategy_name, result in results.items():
        if result is None:
            continue

        performance = result.get('performance', {})

        report_lines.append(
            f"{strategy_name:<15} "
            f"{result.get('total_return', 0)*100:>10.2f}%   "
            f"{performance.get('sharpe_ratio', 0):>10.2f}   "
            f"{performance.get('max_drawdown', 0)*100:>10.2f}%   "
            f"{performance.get('win_rate', 0)*100:>9.1f}%   "
            f"{result.get('total_trades', 0):>10}"
        )

    report_lines.extend(["", "-" * 80, ""])

    # 详细分析
    report_lines.extend([
        "",
        "详细分析:",
        "",
    ])

    for strategy_name, result in results.items():
        if result is None:
            continue

        report_lines.extend([
            f"【{strategy_name}】",
            "",
            f"  收益表现:",
            f"    总收益: {result.get('total_return', 0)*100:+.2f}%",
            f"    总盈亏: ¥{result.get('total_pnl', 0):+,.2f}",
            "",
            f"  风险指标:",
            f"    夏普比率: {result.get('performance', {}).get('sharpe_ratio', 0):.2f}",
            f"    最大回撤: {result.get('performance', {}).get('max_drawdown', 0)*100:.2f}%",
            "",
            f"  交易统计:",
            f"    交易次数: {result.get('total_trades', 0)}",
            f"    胜率: {result.get('performance', {}).get('win_rate', 0)*100:.1f}%",
            "",
        ])

        # Agent 特有统计
        if strategy_name == "agent_llm":
            decision_stats = result.get('decision_stats', {})
            report_lines.extend([
                f"  Agent 特有:",
                f"    LLM 调用次数: {result.get('total_llm_calls', 0)}",
                f"    平均置信度: {decision_stats.get('avg_confidence', 0):.2f}",
                f"    决策执行率: {decision_stats.get('execution_rate', 0)*100:.1f}%",
                "",
            ])

    report_lines.extend(["=" * 80])

    # 保存报告
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    print(f"✅ 对比报告已保存: {output_path}")

    # 同时打印到控制台
    print()
    print('\n'.join(report_lines))


async def run_strategy_backtest(
    strategy_name: str,
    symbols: List[str],
    output_dir: Path,
) -> Dict[str, Any]:
    """运行单个策略的回测"""
    if strategy_name == "agent_llm":
        # Agent 回测
        from src.agent_backtester import create_agent_backtest_engine

        print(f"正在运行 {strategy_name} 回测...")
        engine = await create_agent_backtest_engine(
            initial_cash=100000.0,
            symbols=symbols,
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            decision_interval=5,
        )

        if not engine.load_historical_data():
            print(f"❌ {strategy_name}: 加载数据失败")
            return None

        result = await engine.run()

        # 保存结果
        strategy_dir = output_dir / strategy_name
        strategy_dir.mkdir(parents=True, exist_ok=True)

        report_file = strategy_dir / "backtest_report.json"
        import json
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        engine.save_decision_records(strategy_dir / "decision_records.json")
        engine.save_trade_records(strategy_dir / "trade_records.json")

        return result

    else:
        # 传统策略回测
        from scripts.run_backtest import create_strategy, RealDataBacktestEngine

        print(f"正在运行 {strategy_name} 回测...")

        # 获取数据范围
        data_file = PROJECT_ROOT / "data" / "stocks" / f"stock_{symbols[0]}.csv"
        if not data_file.exists():
            print(f"❌ {strategy_name}: 数据文件不存在")
            return None

        import pandas as pd
        df = pd.read_csv(data_file)
        df['date'] = pd.to_datetime(df['date'])
        start_date = df['date'].min().strftime("%Y-%m-%d")
        end_date = df['date'].max().strftime("%Y-%m-%d")

        # 创建策略
        strategy = create_strategy(strategy_name)

        # 运行回测
        engine = RealDataBacktestEngine(
            initial_cash=100000.0,
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
            strategy=strategy,
        )

        result = engine.run()

        # 保存结果
        strategy_dir = output_dir / strategy_name
        strategy_dir.mkdir(parents=True, exist_ok=True)

        report_file = strategy_dir / "backtest_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        return result


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="策略对比分析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("symbols", type=str, help="股票代码（逗号分隔）")
    parser.add_argument("--strategies", type=str, default="ma_cross,agent",
                       help="对比的策略（逗号分隔，默认: ma_cross,agent）")
    parser.add_argument("--use-existing", action="store_true",
                       help="使用已有的回测结果")
    parser.add_argument("--output-dir", type=str, default=None,
                       help="输出目录（默认: data/strategy_comparison/YYYYMMDD_HHMMSS/）")

    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(',')]
    strategies = [s.strip() for s in args.strategies.split(',')]

    # 设置输出目录
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = PROJECT_ROOT / "data" / "strategy_comparison" / timestamp

    output_dir.mkdir(parents=True, exist_ok=True)

    # 打印配置
    print("=" * 70)
    print("策略对比分析")
    print("=" * 70)
    print(f"股票代码: {', '.join(symbols)}")
    print(f"对比策略: {', '.join(strategies)}")
    print(f"输出目录: {output_dir}")
    print("=" * 70)
    print()

    results = {}

    if args.use_existing:
        # 使用已有结果
        print("正在加载已有回测结果...")
        base_dir = PROJECT_ROOT / "data"

        for strategy in strategies:
            if strategy == "agent":
                result_dir = base_dir / "agent_backtest"
            else:
                result_dir = base_dir / "backtest_results"

            # 查找最新的结果目录
            if result_dir.exists():
                subdirs = [d for d in result_dir.iterdir() if d.is_dir()]
                if subdirs:
                    latest_dir = max(subdirs, key=lambda p: p.stat().st_mtime)
                    results[strategy] = load_backtest_results(latest_dir)
    else:
        # 运行新回测
        for strategy in strategies:
            result = await run_strategy_backtest(strategy, symbols, output_dir)
            results[strategy] = result

    # 生成对比报告和图表
    print()
    print("正在生成对比分析...")

    comparison_report = output_dir / "comparison_report.txt"
    generate_comparison_report(results, comparison_report)

    comparison_chart = output_dir / "comparison_chart.png"
    generate_comparison_chart(results, comparison_chart)

    print()
    print("=" * 70)
    print("对比分析完成！")
    print(f"所有结果已保存到: {output_dir}")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
