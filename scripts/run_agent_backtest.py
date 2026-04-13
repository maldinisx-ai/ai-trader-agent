# -*- coding: utf-8 -*-
"""
Agent 回测运行脚本

使用 ReAct Agent 在历史数据上进行回测，让 LLM 真正自主决策。

用法:
    # 使用默认配置（本地 Ollama 模型）
    python scripts/run_agent_backtest.py 600519

    # 使用 Claude API
    python scripts/run_agent_backtest.py 600519 --api-key YOUR_KEY

    # 指定决策间隔（每隔 N 天决策一次）
    python scripts/run_agent_backtest.py 600519 --interval 10

    # 多只股票
    python scripts/run_agent_backtest.py 600519,000001 --interval 5

    # 保存详细报告
    python scripts/run_agent_backtest.py 600519 --output-dir results/agent_backtest
"""

import asyncio
import argparse
import sys
import os
import io
from pathlib import Path
from datetime import datetime
from typing import List

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 加载 .env 环境变量
try:
    from dotenv import load_dotenv
    # 从项目根目录加载 .env
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass  # 没有安装 dotenv 忽略

# 设置控制台输出编码为UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Agent 回测 - 使用 LLM 自主决策",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s 600519                              # 单只股票，使用本地模型
  %(prog)s 600519 --api-key YOUR_KEY             # 使用 Claude API
  %(prog)s 600519,000001 --interval 10           # 多只股票，间隔10天
  %(prog)s 600519 --interval 5 --cash 500000      # 自定义初始资金和间隔
        """
    )

    parser.add_argument(
        "symbols",
        type=str,
        help="股票代码（逗号分隔，如 600519,000001）"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("ANTHROPIC_API_KEY"),
        help="Anthropic API Key（默认从环境变量读取）"
    )
    parser.add_argument(
        "--glm-key",
        type=str,
        default=os.getenv("ZHIPU_API_KEY") or os.getenv("THIRD_PARTY_API_KEY"),
        help="智谱 GLM API Key（默认从环境变量读取 ZHIPU_API_KEY 或 THIRD_PARTY_API_KEY）"
    )
    parser.add_argument(
        "--glm-url",
        type=str,
        default=os.getenv("THIRD_PARTY_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
        help="智谱 GLM API Base URL"
    )
    parser.add_argument(
        "--glm-model",
        type=str,
        default=os.getenv("THIRD_PARTY_MODEL", "glm-4-flash"),
        help="智谱 GLM 模型名称（默认: glm-4-flash）"
    )
    parser.add_argument(
        "--local-url",
        type=str,
        default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        help="本地模型 URL（默认: http://localhost:11434）"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="决策间隔天数（默认: 5，避免每个 K 线都调用 LLM）"
    )
    parser.add_argument(
        "--cash",
        type=float,
        default=100000.0,
        help="初始资金（默认: 100000）"
    )
    parser.add_argument(
        "--max-position",
        type=float,
        default=0.30,
        help="最大仓位比例（默认: 0.30）"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="报告输出目录（默认: data/agent_backtest/YYYYMMDD_HHMMSS/）"
    )

    args = parser.parse_args()

    # 解析股票代码
    symbols = [s.strip() for s in args.symbols.split(',')]

    # 设置输出目录
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = PROJECT_ROOT / "data" / "agent_backtest" / timestamp

    output_dir.mkdir(parents=True, exist_ok=True)

    # 打印配置
    print("=" * 70)
    print("Agent 回测配置")
    print("=" * 70)
    print(f"股票代码: {', '.join(symbols)}")
    print(f"初始资金: ¥{args.cash:,.2f}")
    print(f"决策间隔: {args.interval} 天")
    print(f"Claude API: {'已配置' if args.api_key else '未配置'}")
    print(f"智谱 GLM API: {'已配置' if args.glm_key else '未配置'}")
    if args.glm_key:
        print(f"  - URL: {args.glm_url}")
        print(f"  - 模型: {args.glm_model}")
    print(f"本地 Ollama: {args.local_url}")
    print(f"输出目录: {output_dir}")
    print("=" * 70)
    print()

    # 导入模块
    from src.agent_backtester import create_agent_backtest_engine

    # 创建回测引擎
    print("正在初始化 Agent 回测引擎...")
    engine = await create_agent_backtest_engine(
        initial_cash=args.cash,
        symbols=symbols,
        api_key=args.api_key,
        third_party_api_key=args.glm_key,
        third_party_base_url=args.glm_url,
        third_party_model=args.glm_model,
        local_url=args.local_url,
        decision_interval=args.interval,
        max_position_ratio=args.max_position or 0.30,
    )

    # 加载数据
    print("正在加载历史数据...")
    if not engine.load_historical_data():
        print("❌ 加载历史数据失败")
        print("\n提示: 请先运行以下命令下载股票数据：")
        print("  python scripts/download_batch_stocks.py")
        return 1

    # 运行回测
    print()
    print("开始 Agent 回测...")
    print("这可能需要较长时间（取决于决策次数和 LLM 响应速度）")
    print()

    results = await engine.run()

    # 保存结果
    print()
    print("正在保存结果...")

    # 保存完整报告
    report_file = output_dir / "backtest_report.json"
    import json
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"✅ 回测报告: {report_file}")

    # 保存决策记录
    decisions_file = output_dir / "decision_records.json"
    engine.save_decision_records(decisions_file)

    # 保存交易记录
    trades_file = output_dir / "trade_records.json"
    engine.save_trade_records(trades_file)

    # 生成决策可视化
    _generate_decision_visualization(engine, output_dir)

    print()
    print("=" * 70)
    print("Agent 回测完成！")
    print(f"所有结果已保存到: {output_dir}")
    print("=" * 70)

    return 0


def _generate_decision_visualization(engine, output_dir: Path):
    """生成决策可视化"""
    try:
        import pandas as pd
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
        plt.rcParams['axes.unicode_minus'] = False

        # 转换决策记录为 DataFrame
        records = [r.to_dict() for r in engine.decision_records]
        if not records:
            return

        df = pd.DataFrame(records)
        df['date'] = pd.to_datetime(df['date'])

        # 创建图表
        fig, axes = plt.subplots(3, 1, figsize=(14, 12))

        # 1. 决策分布
        action_counts = df['action'].value_counts()
        colors = {'buy': '#2ECC71', 'sell': '#E74C3C', 'hold': '#F39C12', 'wait': '#95A5A6'}
        bar_colors = [colors.get(a, '#3498DB') for a in action_counts.index]

        axes[0].bar(action_counts.index, action_counts.values, color=bar_colors, alpha=0.7)
        axes[0].set_title('决策分布', fontsize=14, fontweight='bold')
        axes[0].set_ylabel('次数')
        axes[0].grid(True, alpha=0.3, axis='y')

        # 添加数值标签
        for i, (action, count) in enumerate(action_counts.items()):
            axes[0].text(i, count, f' {count}', ha='left', va='center', fontsize=10)

        # 2. 置信度分布
        df_conf = df[df['action'].isin(['buy', 'sell'])]
        if not df_conf.empty:
            df_conf_sorted = df_conf.sort_values('date')

            colors = ['#2ECC71' if a == 'buy' else '#E74C3C' for a in df_conf_sorted['action']]
            axes[1].bar(df_conf_sorted['date'], df_conf_sorted['confidence'], color=colors, alpha=0.6)
            axes[1].axhline(y=0.7, color='red', linestyle='--', alpha=0.5, label='高置信度阈值')
            axes[1].set_title('交易决策置信度', fontsize=14, fontweight='bold')
            axes[1].set_ylabel('置信度')
            axes[1].set_xlabel('日期')
            axes[1].legend()
            axes[1].grid(True, alpha=0.3, axis='y')

            # 格式化日期
            axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            axes[1].xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(df_conf_sorted) // 10)))
            plt.setp(axes[1].xaxis.get_majorticklabels(), rotation=45)

        # 3. 执行率统计
        executed = df['executed'].sum()
        total = len(df)
        execution_rate = executed / total if total > 0 else 0

        exec_data = [executed, total - executed]
        exec_labels = [f'已执行: {executed}', f'未执行: {total - executed}']
        exec_colors = ['#2ECC71', '#95A5A6']
        explode = (0.05, 0) if executed > 0 else (0, 0.05)

        axes[2].pie(exec_data, labels=exec_labels, colors=exec_colors, autopct='%1.1f%%',
                   startangle=90, explode=explode)
        axes[2].set_title(f'决策执行率: {execution_rate*100:.1f}%', fontsize=14, fontweight='bold')

        plt.tight_layout()

        # 保存图表
        chart_file = output_dir / "decision_analysis.png"
        plt.savefig(chart_file, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"✅ 决策可视化: {chart_file}")

    except Exception as e:
        print(f"⚠️  生成可视化失败: {e}")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
