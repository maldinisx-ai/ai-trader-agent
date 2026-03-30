#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Agent 自动扫描所有股票并给出交易建议
"""
import asyncio
import os
import sys
import io
import json
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Dict, Any

# 设置控制台编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from anthropic import AsyncAnthropic


def print_section(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


async def scan_all_stocks(max_stocks: int = 10):
    """
    自动扫描所有股票并给出交易建议

    Args:
        max_stocks: 最大扫描股票数量
    """
    print("=" * 80)
    print(" AI Agent 自动股票扫描系统")
    print("=" * 80)
    print(f"扫描参数: 最大股票数={max_stocks}")

    # 模拟股票列表
    stocks = [
        {"symbol": "600519", "name": "贵州茅台", "price": 1680.00, "change": 1.2, "volume": 100000},
        {"symbol": "000001", "name": "平安银行", "price": 12.50, "change": -0.5, "volume": 500000},
        {"symbol": "000002", "name": "万科A", "price": 8.80, "change": 0.3, "volume": 800000},
        {"symbol": "600036", "name": "招商银行", "price": 32.50, "change": 0.8, "volume": 600000},
        {"symbol": "000858", "name": "五粮液", "price": 145.00, "change": -0.2, "volume": 300000},
        {"symbol": "601318", "name": "中国平安", "price": 42.30, "change": 1.5, "volume": 400000},
        {"symbol": "600276", "name": "恒瑞医药", "price": 45.60, "change": -1.2, "volume": 200000},
        {"symbol": "002594", "name": "比亚迪", "price": 220.00, "change": 2.3, "volume": 350000},
        {"symbol": "601012", "name": "隆基绿能", "price": 25.80, "change": -0.8, "volume": 700000},
        {"symbol": "300750", "name": "宁德时代", "price": 185.00, "change": 1.8, "volume": 450000},
    ][:max_stocks]

    print_section("步骤 1: 获取股票列表")

    print(f"✓ 获取到 {len(stocks)} 只股票")

    # 显示股票列表
    print(f"\n{'代码':<10}{'名称':<12}{'价格':<10}{'涨跌幅':<10}")
    print("-" * 50)
    for stock in stocks:
        print(f"{stock['symbol']:<10}{stock['name']:<12}{stock['price']:<10.2f}{stock['change']:<10.2f}")

    print_section("步骤 2: AI 分析所有股票")

    # 构建股票信息
    stock_info = "\n".join([
        f"- {s['symbol']} {s['name']}: 价格 ¥{s['price']:.2f}, 涨跌幅 {s['change']:.2f}%, 成交量 {s['volume']:,} 手"
        for s in stocks
    ])

    # 账户状态
    account_info = f"""
## 当前账户状态
- 现金: ¥1,000,000.00
- 总资产: ¥1,000,000.00
- 回撤率: 0.00%
- 生存等级: normal
- 市场状态: sideways (震荡市)
- 最大仓位: 30%
- 当前持仓: 空仓

## 待分析股票列表
{stock_info}
"""

    # 构建提示词
    prompt = f"""你是一个专业的股票交易智能体。

{account_info}

## 分析要求
请对以上所有股票进行全面分析，并按照以下要求给出建议：

1. **排序推荐**: 根据投资价值对所有股票进行排序（综合考虑估值、技术面、基本面、风险）
2. **推荐等级**: 为每只股票标注推荐等级（强烈买入/买入/观望/卖出/强烈卖出）
3. **最佳选择**: 从中选择1只最具投资价值的股票作为主要推荐
4. **操作建议**: 给出具体的买入/卖出建议（数量、价格）

## 决策格式
请严格按照以下 JSON 格式回复：

```json
{{
    "action": "buy|sell|hold|wait",
    "symbol": "最终推荐的股票代码",
    "quantity": 建议数量（股），
    "price": 建议价格，
    "confidence": 置信度（0-1），
    "reasoning": "详细的推理过程",
    "analysis": {{
        "market_summary": "整体市场分析",
        "recommendations": [
            {{"symbol": "代码", "name": "名称", "rating": "推荐等级", "price": "当前价格", "target_price": "目标价格", "reason": "推荐理由（50字内）"}}
        ],
        "risk_warning": "风险提示"
    }},
    "is_final": true
}}
```"""

    print_section("步骤 3: 调用大模型分析")

    print(f"提示词长度: {len(prompt)} 字符")
    print(f"正在调用智谱 GLM 模型...")

    # 创建 Anthropic 客户端（连接到智谱）
    client = AsyncAnthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY", "sk-ant-xxx"),
        base_url=os.getenv("ANTHROPIC_BASE_URL")
    )

    start_time = datetime.now()

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}],
        )

        elapsed = (datetime.now() - start_time).total_seconds()

        # 解析响应
        content = response.content[0].text

        print_section("步骤 4: AI 分析结果")

        # 提取 JSON
        import re
        json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = content

        try:
            decision = json.loads(json_str)

            print(f"\n【推荐决策】")
            print(f"  动作: {decision.get('action', 'N/A').upper()}")
            print(f"  股票: {decision.get('symbol', 'N/A')}")
            print(f"  数量: {decision.get('quantity', 0)} 股")
            print(f"  价格: {f'¥{decision.get('price', 0):.2f}' if decision.get('price') else 'N/A'}")
            print(f"  置信度: {decision.get('confidence', 0):.2%}")

            print(f"\n【推理过程】")
            reasoning = decision.get('reasoning', '')
            if reasoning:
                # 分段显示
                lines = reasoning.split('。')
                for line in lines[:5]:  # 显示前5句
                    if line.strip():
                        print(f"  • {line.strip()}")
                if len(lines) > 5:
                    print(f"  • ...")

            # 显示所有股票分析
            analysis = decision.get('analysis', {})
            recommendations = analysis.get('recommendations', [])

            if recommendations:
                print(f"\n【所有股票推荐排序】")
                print(f"\n{'排名':<6}{'代码':<10}{'名称':<12}{'推荐等级':<16}{'当前价':<10}{'目标价':<10}{'推荐理由'}")
                print("-" * 100)
                for i, rec in enumerate(recommendations, 1):
                    print(f"{i:<6}{rec['symbol']:<10}{rec['name']:<12}{rec['rating']:<16}"
                          f"¥{rec.get('price', 0):<9.2f}¥{rec.get('target_price', 0):<9.2f}{rec['reason'][:30]}...")

            # 市场总结
            market_summary = analysis.get('market_summary', '')
            if market_summary:
                print(f"\n【市场分析】")
                print(f"  {market_summary}")

            # 风险提示
            risk_warning = analysis.get('risk_warning', '')
            if risk_warning:
                print(f"\n【风险提示】")
                print(f"  ⚠️  {risk_warning}")

            print_section("扫描完成")

            # 数据统计
            confidence_str = f"{decision.get('confidence', 0):.2%}" if decision.get('confidence') else 'N/A'
            symbol_str = decision.get('symbol') or 'N/A'
            action_str = decision.get('action', 'N/A').upper()

            print(f"""
┌─────────────────────┬─────────────────┐
│     项目            │     数值        │
├─────────────────────┼─────────────────┤
│ 扫描股票数量        │ {len(stocks):>10} 只    │
│ 模型响应时间        │ {elapsed:>10.2f} 秒   │
│ 输入 Tokens         │ {response.usage.input_tokens if hasattr(response, 'usage') else 0:>10}      │
│ 输出 Tokens         │ {response.usage.output_tokens if hasattr(response, 'usage') else 0:>10}      │
│ 推荐动作            │ {action_str:>10}      │
│ 推荐股票            │ {symbol_str:>10}      │
│ 置信度              │ {confidence_str:>10}     │
└─────────────────────┴─────────────────┘
            """)

        except json.JSONDecodeError as e:
            print(f"\n❌ 解析 JSON 失败: {e}")
            print(f"\n原始响应:")
            print(content[:500])

    except Exception as e:
        print(f"\n❌ 调用模型失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="AI Agent 自动股票扫描")
    parser.add_argument("--max-stocks", type=int, default=10, help="最大扫描股票数量")

    args = parser.parse_args()

    await scan_all_stocks(max_stocks=args.max_stocks)


if __name__ == "__main__":
    asyncio.run(main())
