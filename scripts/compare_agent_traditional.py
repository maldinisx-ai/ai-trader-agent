# -*- coding: utf-8 -*-
"""
策略对比分析

对比传统量化策略与 Agent 自主决策策略的回测结果。
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime


# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False


class StrategyComparison:
    """策略对比分析器"""

    def __init__(
        self,
        traditional_report: Dict[str, Any],
        agent_report: Dict[str, Any],
        benchmark_report: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化对比分析器

        Args:
            traditional_report: 传统策略回测报告
            agent_report: Agent 策略回测报告
            benchmark_report: 基准策略报告（可选，买入持有）
        """
        self.traditional = traditional_report
        self.agent = agent_report
        self.benchmark = benchmark_report

    def compare_key_metrics(self) -> Dict[str, Any]:
        """对比关键指标"""
        metrics = {}

        # 收益率对比
        traditional_return = self._extract_return(self.traditional)
        agent_return = self._extract_return(self.agent)
        metrics["收益率"] = {
            "传统策略": f"{traditional_return * 100:.2f}%",
            "Agent策略": f"{agent_return * 100:.2f}%",
            "差异": f"{(agent_return - traditional_return) * 100:+.2f}%",
            "胜者": "Agent" if agent_return > traditional_return else "传统",
        }

        # 最大回撤对比
        traditional_dd = self._extract_max_drawdown(self.traditional)
        agent_dd = self._extract_max_drawdown(self.agent)
        metrics["最大回撤"] = {
            "传统策略": f"{traditional_dd * 100:.2f}%",
            "Agent策略": f"{agent_dd * 100:.2f}%",
            "差异": f"{(agent_dd - traditional_dd) * 100:+.2f}%",
            "胜者": "传统" if traditional_dd < agent_dd else "Agent",
        }

        # 夏普比率对比
        traditional_sharpe = self._extract_sharpe(self.traditional)
        agent_sharpe = self._extract_sharpe(self.agent)
        metrics["夏普比率"] = {
            "传统策略": f"{traditional_sharpe:.2f}",
            "Agent策略": f"{agent_sharpe:.2f}",
            "差异": f"{agent_sharpe - traditional_sharpe:+.2f}",
            "胜者": "Agent" if agent_sharpe > traditional_sharpe else "传统",
        }

        # 胜率对比
        traditional_win_rate = self._extract_win_rate(self.traditional)
        agent_win_rate = self._extract_win_rate(self.agent)
        metrics["胜率"] = {
            "传统策略": f"{traditional_win_rate * 100:.1f}%",
            "Agent策略": f"{agent_win_rate * 100:.1f}%",
            "差异": f"{(agent_win_rate - traditional_win_rate) * 100:+.1f}%",
            "胜者": "Agent" if agent_win_rate > traditional_win_rate else "传统",
        }

        # 交易频率对比
        traditional_trades = self._extract_trade_count(self.traditional)
        agent_trades = self._extract_trade_count(self.agent)
        metrics["交易次数"] = {
            "传统策略": traditional_trades,
            "Agent策略": agent_trades,
            "差异": f"{agent_trades - traditional_trades:+d}",
            "胜者": "传统" if traditional_trades < agent_trades else "Agent",
        }

        # 决策置信度（Agent 特有）
        if "decision_stats" in self.agent:
            avg_confidence = self.agent["decision_stats"].get("avg_confidence", 0)
            metrics["平均置信度"] = f"{avg_confidence:.2f}"

        # LLM 调用次数（Agent 特有）
        if "total_llm_calls" in self.agent:
            metrics["LLM调用次数"] = self.agent["total_llm_calls"]

        # 基准对比（如果有）
        if self.benchmark:
            benchmark_return = self._extract_return(self.benchmark)
            metrics["基准收益率"] = f"{benchmark_return * 100:.2f}%"

        return metrics

    def generate_comparison_report(self) -> str:
        """生成对比报告"""
        metrics = self.compare_key_metrics()

        lines = []
        lines.append("=" * 70)
        lines.append("策略对比报告")
        lines.append("=" * 70)
        lines.append("")
        lines.append("对比策略:")
        lines.append(f"  传统策略: {self.traditional.get('strategy_name', 'MA Crossover')}")
        lines.append(f"  Agent策略: ReAct LLM 自主决策")
        if self.benchmark:
            lines.append(f"  基准策略: 买入持有")
        lines.append("")
        lines.append("-" * 70)
        lines.append("关键指标对比")
        lines.append("-" * 70)
        lines.append("")

        for metric_name, values in metrics.items():
            lines.append(f"【{metric_name}】")

            if isinstance(values, str):
                # 单值（Agent 特有指标）
                lines.append(f"  {values}")
            elif isinstance(values, dict):
                # 对比值
                for key, value in values.items():
                    lines.append(f"  {key}: {value}")
            lines.append("")

        lines.append("-" * 70)
        lines.append("决策差异分析")
        lines.append("-" * 70)
        lines.append("")

        # 分析 Agent 的决策特点
        if "decision_records" in self.agent:
            decisions = pd.DataFrame(self.agent["decision_records"])
            if not decisions.empty:
                lines.append("Agent 决策分布:")
                action_dist = decisions['action'].value_counts()
                for action, count in action_dist.items():
                    pct = count / len(decisions) * 100
                    lines.append(f"  {action:6}: {count} 次 ({pct:.1f}%)")
                lines.append("")

                # 分析执行率
                executed = decisions['executed'].sum()
                exec_rate = executed / len(decisions) * 100
                lines.append(f"决策执行率: {exec_rate:.1f}%")
                lines.append("")

        lines.append("-" * 70)
        lines.append("核心发现")
        lines.append("-" * 70)
        lines.append("")

        # 生成核心发现
        findings = self._generate_findings()
        for finding in findings:
            lines.append(f"  • {finding}")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)

    def generate_comparison_chart(self, output_path: Path) -> None:
        """生成对比图表"""
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('策略对比分析', fontsize=16, fontweight='bold')

        metrics = self.compare_key_metrics()

        # 1. 收益率对比
        if "收益率" in metrics:
            returns = {
                "传统策略": float(metrics["收益率"]["传统策略"].replace("%", "")),
                "Agent策略": float(metrics["收益率"]["Agent策略"].replace("%", "")),
            }
            if self.benchmark and "基准收益率" in metrics:
                returns["基准"] = float(metrics["基准收益率"].replace("%", ""))

            colors = ['#3498DB', '#E74C3C', '#95A5A6'][:len(returns)]
            bars = axes[0, 0].bar(returns.keys(), returns.values(), color=colors, alpha=0.7)
            axes[0, 0].set_title('收益率对比', fontweight='bold')
            axes[0, 0].set_ylabel('收益率 (%)')
            axes[0, 0].grid(True, alpha=0.3, axis='y')
            axes[0, 0].axhline(y=0, color='black', linestyle='-', linewidth=0.5)

            # 添加数值标签
            for bar in bars:
                height = bar.get_height()
                axes[0, 0].text(bar.get_x() + bar.get_width()/2., height,
                              f'{height:.2f}%', ha='center', va='bottom' if height >= 0 else 'top')

        # 2. 风险指标对比（最大回撤）
        if "最大回撤" in metrics:
            dd = {
                "传统策略": float(metrics["最大回撤"]["传统策略"].replace("%", "")),
                "Agent策略": float(metrics["最大回撤"]["Agent策略"].replace("%", "")),
            }

            bars = axes[0, 1].bar(dd.keys(), dd.values(), color=['#F39C12', '#E74C3C'], alpha=0.7)
            axes[0, 1].set_title('最大回撤对比（越低越好）', fontweight='bold')
            axes[0, 1].set_ylabel('回撤 (%)')
            axes[0, 1].grid(True, alpha=0.3, axis='y')

            for bar in bars:
                height = bar.get_height()
                axes[0, 1].text(bar.get_x() + bar.get_width()/2., height,
                              f'{height:.2f}%', ha='center', va='bottom')

        # 3. 效率指标对比（夏普比率）
        if "夏普比率" in metrics:
            sharpe = {
                "传统策略": float(metrics["夏普比率"]["传统策略"]),
                "Agent策略": float(metrics["夏普比率"]["Agent策略"]),
            }

            bars = axes[1, 0].bar(sharpe.keys(), sharpe.values(), color=['#2ECC71', '#3498DB'], alpha=0.7)
            axes[1, 0].set_title('夏普比率对比（越高越好）', fontweight='bold')
            axes[1, 0].set_ylabel('夏普比率')
            axes[1, 0].grid(True, alpha=0.3, axis='y')

            for bar in bars:
                height = bar.get_height()
                axes[1, 0].text(bar.get_x() + bar.get_width()/2., height,
                              f'{height:.2f}', ha='center', va='bottom')

        # 4. 交易次数对比
        if "交易次数" in metrics:
            trades = {
                "传统策略": metrics["交易次数"]["传统策略"],
                "Agent策略": metrics["交易次数"]["Agent策略"],
            }

            bars = axes[1, 1].bar(trades.keys(), trades.values(), color=['#9B59B6', '#E67E22'], alpha=0.7)
            axes[1, 1].set_title('交易次数对比', fontweight='bold')
            axes[1, 1].set_ylabel('交易次数')
            axes[1, 1].grid(True, alpha=0.3, axis='y')

            for bar in bars:
                height = bar.get_height()
                axes[1, 1].text(bar.get_x() + bar.get_width()/2., height,
                              f'{height}', ha='center', va='bottom')

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

    def _generate_findings(self) -> List[str]:
        """生成核心发现"""
        findings = []

        traditional_return = self._extract_return(self.traditional)
        agent_return = self._extract_return(self.agent)
        return_diff = agent_return - traditional_return

        if return_diff > 0.05:  # 5% 以上
            findings.append(f"Agent 策略收益显著高于传统策略（高出 {return_diff*100:.2f}%）")
        elif return_diff < -0.05:
            findings.append(f"Agent 策略收益低于传统策略（低 {abs(return_diff)*100:.2f}%）")
        else:
            findings.append("两种策略收益相当")

        # 风险分析
        traditional_dd = self._extract_max_drawdown(self.traditional)
        agent_dd = self._extract_max_drawdown(self.agent)

        if agent_dd < traditional_dd * 0.8:
            findings.append("Agent 策略风险控制更好，最大回撤更小")
        elif agent_dd > traditional_dd * 1.2:
            findings.append("Agent 策略风险较高，最大回撤更大")

        # 交易频率分析
        traditional_trades = self._extract_trade_count(self.traditional)
        agent_trades = self._extract_trade_count(self.agent)

        if agent_trades < traditional_trades * 0.5:
            findings.append("Agent 策略交易频率更低，更注重长期持有")
        elif agent_trades > traditional_trades * 1.5:
            findings.append("Agent 策略交易频率更高，更积极操作")

        # Agent 特有发现
        if "decision_records" in self.agent:
            decisions = pd.DataFrame(self.agent["decision_records"])
            if not decisions.empty:
                executed = decisions['executed'].sum()
                exec_rate = executed / len(decisions)

                if exec_rate < 0.5:
                    findings.append("Agent 决策执行率较低，可能受风控限制")

                avg_conf = decisions['confidence'].mean()
                if avg_conf < 0.6:
                    findings.append("Agent 平均置信度较低，决策不够果断")
                elif avg_conf > 0.8:
                    findings.append("Agent 平均置信度较高，决策较为果断")

        return findings

    def _extract_return(self, report: Dict[str, Any]) -> float:
        """提取收益率"""
        # 尝试多个可能的字段
        for field in ['total_return', 'return', 'annualized_return', 'final_return']:
            if field in report:
                return float(report[field])
        if 'performance' in report:
            perf = report['performance']
            for field in ['total_return', 'return', 'annualized_return']:
                if field in perf:
                    return float(perf[field])
        return 0.0

    def _extract_max_drawdown(self, report: Dict[str, Any]) -> float:
        """提取最大回撤"""
        for field in ['max_drawdown', 'max_draw_down', 'drawdown']:
            if field in report:
                return abs(float(report[field]))
        if 'performance' in report:
            perf = report['performance']
            for field in ['max_drawdown', 'max_draw_down', 'drawdown']:
                if field in perf:
                    return abs(float(perf[field]))
        return 0.0

    def _extract_sharpe(self, report: Dict[str, Any]) -> float:
        """提取夏普比率"""
        for field in ['sharpe_ratio', 'sharpe']:
            if field in report:
                return float(report[field])
        if 'performance' in report:
            perf = report['performance']
            for field in ['sharpe_ratio', 'sharpe']:
                if field in perf:
                    return float(perf[field])
        return 0.0

    def _extract_win_rate(self, report: Dict[str, Any]) -> float:
        """提取胜率"""
        for field in ['win_rate', 'winning_rate', 'winrate']:
            if field in report:
                return float(report[field])
        if 'performance' in report:
            perf = report['performance']
            for field in ['win_rate', 'winning_rate', 'winrate']:
                if field in perf:
                    return float(perf[field])
        return 0.0

    def _extract_trade_count(self, report: Dict[str, Any]) -> int:
        """提取交易次数"""
        for field in ['total_trades', 'trades', 'trade_count']:
            if field in report:
                return int(report[field])
        if 'performance' in report:
            perf = report['performance']
            for field in ['total_trades', 'trades', 'trade_count']:
                if field in perf:
                    return int(perf[field])
        return 0


def load_report(report_path: Path) -> Optional[Dict[str, Any]]:
    """加载回测报告"""
    if not report_path.exists():
        return None

    with open(report_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def compare_reports(
    traditional_path: Path,
    agent_path: Path,
    benchmark_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> None:
    """
    对比两个回测报告

    Args:
        traditional_path: 传统策略报告路径
        agent_path: Agent 策略报告路径
        benchmark_path: 基准策略报告路径（可选）
        output_dir: 输出目录
    """
    # 加载报告
    traditional_report = load_report(traditional_path)
    agent_report = load_report(agent_path)
    benchmark_report = load_report(benchmark_path) if benchmark_path else None

    if not traditional_report:
        print(f"错误: 找不到传统策略报告 {traditional_path}")
        return

    if not agent_report:
        print(f"错误: 找不到 Agent 策略报告 {agent_path}")
        return

    # 创建对比分析器
    comparison = StrategyComparison(
        traditional_report=traditional_report,
        agent_report=agent_report,
        benchmark_report=benchmark_report,
    )

    # 确定输出目录
    if output_dir is None:
        output_dir = agent_path.parent

    # 生成文本报告
    report_text = comparison.generate_comparison_report()
    report_file = output_dir / "comparison_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_text)

    print(f"对比报告: {report_file}")

    # 生成图表
    chart_file = output_dir / "comparison_chart.png"
    comparison.generate_comparison_chart(chart_file)

    print(f"对比图表: {chart_file}")

    # 打印报告
    print()
    print(report_text)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="策略对比分析")
    parser.add_argument("--traditional", type=str, required=True, help="传统策略报告路径")
    parser.add_argument("--agent", type=str, required=True, help="Agent 策略报告路径")
    parser.add_argument("--benchmark", type=str, help="基准策略报告路径")
    parser.add_argument("--output", type=str, help="输出目录")

    args = parser.parse_args()

    compare_reports(
        traditional_path=Path(args.traditional),
        agent_path=Path(args.agent),
        benchmark_path=Path(args.benchmark) if args.benchmark else None,
        output_dir=Path(args.output) if args.output else None,
    )