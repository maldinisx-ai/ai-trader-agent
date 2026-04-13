#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试脚本：显示AI分析时的完整数据流
"""
import asyncio
import os
import sys
import io
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
import pandas as pd

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from anthropic import AsyncAnthropic
from simulation.account import Account
from simulation.matcher import Matcher
from core.policy_engine import PolicyEngine
from core.schemas import QuoteData
from core.scoring import TrendScoringSystem
from src.indicators import QuoteDataAnalyzer


def print_section(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def calculate_stock_scores(stocks):
    """计算股票评分"""
    scoring_system = TrendScoringSystem()
    scores = {}

    for stock in stocks:
        symbol = stock['symbol']
        possible_names = [
            f'{symbol}.csv',
            f'{symbol}_SZ.csv',
            f'{symbol}_SH.csv',
        ]

        csv_path = None
        for name in possible_names:
            path = f'data/stocks/{name}'
            if os.path.exists(path):
                csv_path = path
                break

        if not csv_path:
            continue

        try:
            df = pd.read_csv(csv_path)
            date_col = 'trade_date' if 'trade_date' in df.columns else 'date'
            df[date_col] = pd.to_datetime(df[date_col])
            df = df.sort_values(date_col).tail(60)

            quotes = []
            for _, row in df.iterrows():
                close_col = 'close_price' if 'close_price' in row else 'close'
                open_col = 'open_price' if 'open_price' in row else 'open'
                high_col = 'high_price' if 'high_price' in row else 'high'
                low_col = 'low_price' if 'low_price' in row else 'low'

                quotes.append(QuoteData(
                    symbol=symbol,
                    name=stock['name'],
                    price=float(row[close_col]),
                    change=0,
                    volume=int(row['volume']),
                    amount=float(row.get('amount', 0)),
                    high=float(row[high_col]),
                    low=float(row[low_col]),
                    open=float(row[open_col]),
                    timestamp=row[date_col],
                ))

            analyzer = QuoteDataAnalyzer(quotes)
            result = scoring_system.score(analyzer)

            scores[symbol] = {
                'total_score': result.total_score,
                'buy_signal': result.buy_signal.value,
                'trend_score': result.trend_score,
                'bias_score': result.bias_score,
                'volume_score': result.volume_score,
                'reasons': result.reasons[:3],
                'risk_factors': result.risk_factors[:2],
            }

        except Exception as e:
            scores[symbol] = {'error': str(e)}

    return scores


async def debug_ai_data_flow(max_stocks: int = 3):
    """调试完整数据流"""

    print("=" * 80)
    print(" AI Agent 数据流调试")
    print("=" * 80)

    # 加载股票
    print_section("步骤 1: 加载股票数据")

    stocks_dir = 'data/stocks'
    csv_files = [f for f in os.listdir(stocks_dir) if f.endswith('.csv')][:max_stocks]

    stocks = []
    for csv_file in csv_files:
        file_path = os.path.join(stocks_dir, csv_file)
        try:
            df = pd.read_csv(file_path)
            if len(df) == 0:
                continue

            latest = df.iloc[-1]
            raw_code = latest['code']
            code = str(raw_code).replace('.SZ', '').replace('.SH', '').replace('.', '')

            price = float(latest['close_price'])
            change = 0
            if len(df) > 1:
                prev_close = float(df.iloc[-2]['close_price'])
                change = (price - prev_close) / prev_close * 100

            stocks.append({
                'symbol': code,
                'name': f'股票{code}',
                'industry': '未知',
                'price': price,
                'change': change,
                'volume': int(latest['volume']),
            })
        except:
            continue

    print(f"✅ 加载了 {len(stocks)} 只股票")

    # 计算评分
    scores = calculate_stock_scores(stocks)

    # 初始化账户
    account = Account(initial_cash=1_000_000.0)
    account_info = account.get_account_info()
    positions = account.get_positions()

    # 构建发送给AI的数据
    print_section("步骤 2: 发送给AI的数据 (完整提示词)")

    sorted_stocks = sorted(stocks, key=lambda s: scores.get(s['symbol'], {}).get('total_score', 0), reverse=True)

    stock_info = "\n".join([
        f"- {s['symbol']} {s['name']}: 价格 {s['price']:.2f}, 涨跌幅 {s['change']:+.2f}%, "
        f"评分 {scores.get(s['symbol'], {}).get('total_score', 0):.0f}/100, "
        f"信号 {scores.get(s['symbol'], {}).get('buy_signal', 'WAIT')}"
        for s in sorted_stocks
    ])

    # 评分详情
    score_details = "\n\n## 策略评分详情\n\n"
    for i, s in enumerate(sorted_stocks, 1):
        symbol = s['symbol']
        score_data = scores.get(symbol, {})
        if not score_data or score_data.get('error'):
            continue

        score_details += f"### {i}. {symbol} - {score_data['total_score']}分\n"
        score_details += f"- 趋势: {score_data['trend_score']}/30 "
        score_details += f"- 乖离: {score_data['bias_score']}/20 "
        score_details += f"- 量能: {score_data['volume_score']}/15\n"

        if score_data.get('reasons'):
            score_details += f"- 买入理由: {', '.join(score_data['reasons'])}\n"
        if score_data.get('risk_factors'):
            score_details += f"- 风险: {', '.join(score_data['risk_factors'])}\n"
        score_details += "\n"

    # 完整提示词
    prompt = f"""你是一个专业的股票交易智能体。

## 当前账户状态
- 现金: ¥{account_info['cash']:,.2f}
- 总资产: ¥{account_info['total_value']:,.2f}
- 持仓市值: ¥{account_info['position_value']:,.2f}
- 盈亏: ¥{account_info['profit_loss']:+,.2f} ({account_info['profit_loss_ratio']*100:+.2f}%)
- 回撤率: {(1 - account_info['total_value'] / account_info['initial_cash']) * 100:.2f}%
- 当前持仓: 空仓

## 待分析股票列表 ({len(stocks)}只)
{stock_info}
{score_details}
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
    "reasoning": "详细的推理过程（200字以内）",
    "analysis": {{
        "market_summary": "整体市场分析（100字以内）",
        "top_picks": "最值得关注的3只股票（代码及简述理由）",
        "recommendations": [
            {{"symbol": "代码", "name": "名称", "rating": "推荐等级", "reason": "推荐理由（30字内）"}}
        ]
    }},
    "is_final": true
}}
```"""

    print(f"\n{'='*80}")
    print(f"提示词总长度: {len(prompt)} 字符")
    print(f"{'='*80}")
    print("\n【完整提示词内容】")
    print("-" * 80)
    print(prompt)
    print("-" * 80)

    # 调用AI
    print_section("步骤 3: 调用大模型 (GLM-4)")

    client = AsyncAnthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        base_url=os.getenv("ANTHROPIC_BASE_URL")
    )

    start_time = datetime.now()

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}],
    )

    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"\n⏱️  响应时间: {elapsed:.2f}秒")
    print(f"📥 Token使用: 输入 {response.usage.input_tokens} → 输出 {response.usage.output_tokens}")

    # 显示AI返回的原始数据
    print_section("步骤 4: AI返回的原始数据")

    raw_content = response.content[0].text
    print("\n【原始响应】")
    print("-" * 80)
    print(raw_content)
    print("-" * 80)

    # 解析JSON
    print_section("步骤 5: 解析后的决策数据")

    import re
    json_match = re.search(r"```json\s*(.*?)\s*```", raw_content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_match = re.search(r"\{.*\}", raw_content, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = raw_content

    import json
    decision = json.loads(json_str)

    print("\n【最终决策数据】")
    print(f"  动作 (action):     {decision.get('action', 'N/A').upper()}")
    print(f"  股票 (symbol):     {decision.get('symbol', 'N/A')}")
    print(f"  数量 (quantity):   {decision.get('quantity', 0)} 股")
    print(f"  价格 (price):      {decision.get('price', 0)}")
    print(f"  置信度 (confidence): {decision.get('confidence', 0):.2%}")

    print(f"\n  推理过程 (reasoning):")
    print(f"    {decision.get('reasoning', '')}")

    analysis = decision.get('analysis', {})

    print(f"\n  市场分析 (market_summary):")
    print(f"    {analysis.get('market_summary', '')}")

    print(f"\n  重点关注 (top_picks):")
    print(f"    {analysis.get('top_picks', '')}")

    recommendations = analysis.get('recommendations', [])
    if recommendations:
        print(f"\n  推荐排序:")
        for i, rec in enumerate(recommendations, 1):
            print(f"    {i}. {rec['symbol']} {rec['name']} - {rec['rating']}")
            print(f"       {rec['reason']}")

    # 数据流总结
    print_section("步骤 6: 数据流总结")

    print(f"""
┌─────────────────────────────────────────────────────────────────┐
│                        数据流总结                                 │
├─────────────────────────────────────────────────────────────────┤
│ 1️⃣  输入数据 (发送给AI)                                          │
│    • 股票数量:     {len(stocks)} 只                                         │
│    • 策略评分:     已计算 (趋势/乖离/量能/MACD/RSI)                    │
│    • 账户状态:     现金 ¥{account_info['cash']:,.0f} / 总资产 ¥{account_info['total_value']:,.0f}                   │
│    • 提示词长度:   {len(prompt)} 字符                                       │
│    • 输入Token:    {response.usage.input_tokens}                                    │
├─────────────────────────────────────────────────────────────────┤
│ 2️⃣  AI处理 (GLM-4模型)                                           │
│    • 模型:         claude-sonnet-4-6                              │
│    • 处理时间:     {elapsed:.2f} 秒                                          │
│    • 输出Token:    {response.usage.output_tokens}                                    │
├─────────────────────────────────────────────────────────────────┤
│ 3️⃣  输出数据 (AI返回)                                            │
│    • 动作:         {decision.get('action', 'N/A').upper()}                                         │
│    • 目标股票:     {decision.get('symbol', 'N/A')}                                        │
│    • 建议数量:     {decision.get('quantity', 0)} 股                                        │
│    • 置信度:       {decision.get('confidence', 0)*100:.0f}%                                         │
│    • 推理过程:     {len(decision.get('reasoning', ''))} 字符                                   │
│    • 市场分析:     {len(analysis.get('market_summary', ''))} 字符                                   │
│    • 推荐列表:     {len(recommendations)} 只                                      │
└─────────────────────────────────────────────────────────────────┘
    """)

    print("\n✅ 数据流调试完成！")


if __name__ == "__main__":
    asyncio.run(debug_ai_data_flow(max_stocks=3))
