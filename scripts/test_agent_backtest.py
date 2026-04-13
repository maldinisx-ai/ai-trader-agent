# -*- coding: utf-8 -*-
"""
Agent 回测引擎测试脚本

不调用 LLM，直接测试框架功能。
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import List

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class MockModelRouter:
    """模拟模型路由器（用于测试）"""

    def __init__(self):
        self._daily_tokens = 0
        self._daily_limit = 1_000_000

    async def initialize(self):
        """初始化"""
        print("[OK] Mock 模型路由器初始化完成")

    async def generate_decision(self, context, memories=None, market_data=None):
        """生成模拟决策"""
        from core.schemas import Decision

        self._daily_tokens += 1000

        # 简单的模拟决策逻辑
        cash_ratio = context.current_cash / context.total_value

        if cash_ratio > 0.8:  # 现金太多，买入
            return Decision(
                action="buy",
                symbol="600519",
                quantity=100,
                price=1680.0,
                confidence=0.7,
                reasoning="【模拟】现金比例过高，建议买入",
                is_final=True,
            )
        elif cash_ratio < 0.3:  # 现金太少，卖出
            return Decision(
                action="sell",
                symbol="600519",
                quantity=100,
                price=1680.0,
                confidence=0.6,
                reasoning="【模拟】需要降低仓位",
                is_final=True,
            )
        else:  # 持有
            return Decision(
                action="hold",
                confidence=0.5,
                reasoning="【模拟】保持现有仓位",
                is_final=True,
            )


async def main():
    """测试主函数"""
    print("=" * 60)
    print("Agent 回测引擎测试")
    print("=" * 60)
    print()

    # 导入模块
    from src.agent_backtester import AgentBacktestEngine

    # 创建模拟模型路由器
    mock_router = MockModelRouter()
    await mock_router.initialize()

    # 创建回测引擎
    print("正在创建 Agent 回测引擎...")
    engine = AgentBacktestEngine(
        initial_cash=100000.0,
        symbols=["600519"],
        model_router=mock_router,
        decision_interval=10,  # 每 10 天决策一次
        max_position_ratio=0.30,
    )

    # 加载数据
    print("正在加载历史数据...")
    if not engine.load_historical_data():
        print("加载历史数据失败")
        return 1

    print(f"[OK] 数据加载成功")
    print(f"   决策日期数: {len(engine.decision_dates)}")
    print()

    # 运行回测
    print("开始运行 Agent 回测（模拟模式）...")
    print()

    results = await engine.run()

    # 保存结果
    print()
    print("正在保存测试结果...")

    output_dir = PROJECT_ROOT / "data" / "agent_backtest_test"
    output_dir.mkdir(parents=True, exist_ok=True)

    import json
    report_file = output_dir / "test_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    decisions_file = output_dir / "test_decisions.json"
    engine.save_decision_records(decisions_file)

    trades_file = output_dir / "test_trades.json"
    engine.save_trade_records(trades_file)

    print(f"[OK] 测试报告: {report_file}")
    print(f"[OK] 决策记录: {decisions_file}")
    print(f"[OK] 交易记录: {trades_file}")

    # 显示决策摘要
    print()
    print("=" * 60)
    print("决策摘要")
    print("=" * 60)

    for record in engine.decision_records[:10]:  # 显示前 10 条
        print(f"{record.date} | {record.action:6} | 置信度: {record.confidence:.2f} | {record.reasoning[:30]}...")

    if len(engine.decision_records) > 10:
        print(f"... (还有 {len(engine.decision_records) - 10} 条)")

    print()
    print("=" * 60)
    print("测试完成！")
    print()

    # 显示关键统计
    decision_stats = results.get('decision_stats', {})
    print("关键统计:")
    print(f"  总决策数: {len(engine.decision_records)}")
    print(f"  总交易数: {results.get('total_trades', 0)}")
    print(f"  总收益率: {results.get('total_return', 0)*100:+.2f}%")
    print(f"  平均置信度: {decision_stats.get('avg_confidence', 0):.2f}")
    print(f"  执行率: {decision_stats.get('execution_rate', 0)*100:.1f}%")
    print()

    print("=" * 60)
    print(f"[OK] 测试成功！框架运行正常。")
    print()
    print("下一步：")
    print("  1. 启动 Ollama: ollama serve")
    print("  2. 运行真实回测: python scripts/run_agent_backtest.py 600519")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
