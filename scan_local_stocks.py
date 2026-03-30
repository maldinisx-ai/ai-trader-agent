#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描本地CSV股票数据并让AI分析
"""
import asyncio
import os
import sys
import io
import json
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
import pandas as pd

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


def load_local_stocks_from_csv(max_stocks: int = 50):
    """从本地CSV文件加载股票数据"""
    stocks_dir = 'data/stocks'
    money_flow_dir = 'data/money_flow'

    if not os.path.exists(stocks_dir):
        print(f"未找到股票数据目录: {stocks_dir}")
        return []

    # 获取所有CSV文件
    csv_files = [f for f in os.listdir(stocks_dir) if f.endswith('.csv')]
    print(f"从 {stocks_dir} 读取到 {len(csv_files)} 只股票文件")

    # 读取股票列表映射（用于获取名称和行业）
    name_mapping = {}
    mapping_file = 'data/stock_industry_mapping.csv'
    if os.path.exists(mapping_file):
        df_mapping = pd.read_csv(mapping_file)
        for _, row in df_mapping.iterrows():
            code = str(row['股票代码'])  # 转换为字符串
            name_mapping[code] = {
                'name': row['股票名称'],
                'industry': row['申万行业'],
                'sub_industry': row['细分行业']
            }

    # 读取K线数据 + 资金流向
    stocks_data = []
    for csv_file in csv_files[:max_stocks]:
        file_path = os.path.join(stocks_dir, csv_file)

        try:
            df = pd.read_csv(file_path)

            if len(df) == 0:
                continue

            # 获取最新数据
            latest = df.iloc[-1]

            # 提取股票代码
            raw_code = latest['code']
            code = str(raw_code).replace('.SZ', '').replace('.SH', '').replace('.', '')

            # 计算涨跌幅
            price = float(latest['close_price'])
            change = 0
            if len(df) > 1:
                prev_close = float(df.iloc[-2]['close_price'])
                change = (price - prev_close) / prev_close * 100

            # 获取名称和行业
            mapping = name_mapping.get(code, {})
            name = mapping.get('name', f'股票{code}')
            industry = mapping.get('industry', '未知')
            sub_industry = mapping.get('sub_industry', '未知')

            # 读取资金流向数据
            money_flow_data = {}
            money_flow_file = os.path.join(money_flow_dir, csv_file)
            if os.path.exists(money_flow_file):
                try:
                    df_flow = pd.read_csv(money_flow_file)
                    if len(df_flow) > 0:
                        flow_latest = df_flow.iloc[-1]
                        money_flow_data = {
                            'main_net_inflow': float(flow_latest.get('主力净流入-净额', 0)),  # 主力净流入
                            'main_net_ratio': float(flow_latest.get('主力净流入-净占比', 0)),  # 主力净占比
                            'super_net_inflow': float(flow_latest.get('超大单净流入-净额', 0)),  # 超大单
                            'super_net_ratio': float(flow_latest.get('超大单净流入-净占比', 0)),
                            'big_net_inflow': float(flow_latest.get('大单净流入-净额', 0)),  # 大单
                            'big_net_ratio': float(flow_latest.get('大单净流入-净占比', 0)),
                            'medium_net_inflow': float(flow_latest.get('中单净流入-净额', 0)),  # 中单
                            'medium_net_ratio': float(flow_latest.get('中单净流入-净占比', 0)),
                            'small_net_inflow': float(flow_latest.get('小单净流入-净额', 0)),  # 小单
                            'small_net_ratio': float(flow_latest.get('小单净流入-净占比', 0)),
                        }
                except Exception:
                    pass

            stocks_data.append({
                'symbol': code,
                'name': name,
                'industry': industry,
                'sub_industry': sub_industry,
                'price': price,
                'change': change,
                'volume': int(latest['volume']),
                'high': float(latest['high_price']),
                'low': float(latest['low_price']),
                'amount': float(latest['amount']),
                'turnover_rate': float(latest.get('turnover_rate', 0)),  # 换手率
                'money_flow': money_flow_data  # 资金流向数据
            })

        except Exception as e:
            continue

    print(f"成功解析 {len(stocks_data)} 只股票数据")
    return stocks_data


async def scan_local_stocks(max_stocks: int = 50):
    """扫描本地股票数据"""
    print("=" * 80)
    print(" AI Agent 本地股票数据扫描")
    print("=" * 80)
    print(f"数据来源: data/stocks/ (真实历史数据)")

    print_section("步骤 1: 加载本地股票数据")

    stocks = load_local_stocks_from_csv(max_stocks)

    if not stocks:
        print("没有可用的股票数据")
        return

    # 显示股票列表（包含资金流向）
    print(f"\n{'代码':<10}{'名称':<10}{'行业':<10}{'价格':<8}{'涨跌':<8}{'主力净流入':<12}{'占比':<8}{'换手率':<8}")
    print("-" * 100)
    for s in stocks:
        change_str = f"{s['change']:+.2f}%"
        money_flow = s.get('money_flow', {})
        main_net = money_flow.get('main_net_inflow', 0)
        main_ratio = money_flow.get('main_net_ratio', 0)
        main_net_str = f"{main_net/10000:+.1f}万" if main_net else "N/A"
        main_ratio_str = f"{main_ratio:+.1f}%" if main_ratio else "N/A"
        turnover_str = f"{s.get('turnover_rate', 0):.2f}%"
        print(f"{s['symbol']:<10}{s['name']:<10}{s['industry']:<10}{s['price']:<8.2f}{change_str:<8}{main_net_str:<12}{main_ratio_str:<8}{turnover_str:<8}")

    print_section("步骤 2: AI 分析所有股票")

    # 构建股票信息（包含资金流向和换手率）
    stock_info_lines = []
    for s in stocks:
        money_flow = s.get('money_flow', {})
        main_net = money_flow.get('main_net_inflow', 0)
        main_ratio = money_flow.get('main_net_ratio', 0)
        turnover = s.get('turnover_rate', 0)
        sub_industry = s.get('sub_industry', '')

        line_parts = [
            f"{s['symbol']} {s['name']}",
        ]
        if sub_industry and sub_industry != '未知':
            line_parts.append(f"({s['industry']}/{sub_industry})")
        else:
            line_parts.append(f"({s['industry']})")

        line_parts.extend([
            f"价格{s['price']:.2f}",
            f"涨跌{s['change']:+.2f}%",
            f"换手{turnover:.2f}%"
        ])

        if main_net != 0:
            line_parts.append(f"主力净{main_net/10000:+.1f}万")
            if main_ratio != 0:
                line_parts.append(f"占比{main_ratio:+.1f}%")

        stock_info_lines.append(f"- {' '.join(str(p) for p in line_parts)}")

    stock_info = "\n".join(stock_info_lines)

    # 账户状态
    account_info = f"""
## 当前账户状态
- 现金: 1,000,000.00 元
- 总资产: 1,000,000.00 元
- 回撤率: 0.00%
- 生存等级: normal
- 市场状态: sideways (震荡市)
- 最大仓位: 30%
- 当前持仓: 空仓

## 待分析股票列表 ({len(stocks)}只 - 真实历史数据)
{stock_info}
"""

    # 构建提示词
    prompt = f"""你是一个专业的股票交易智能体。

{account_info}

## 分析要求
请对以上所有股票进行全面分析，并按照以下要求给出建议：

1. **排序推荐**: 根据投资价值对所有股票进行排序（综合考虑估值、技术面、基本面、行业前景）
2. **推荐等级**: 为每只股票标注推荐等级（强烈买入/买入/观望/卖出/强烈卖出）
3. **最佳选择**: 从中选择1-2只最具投资价值的股票作为主要推荐
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
    "reasoning": "详细的推理过程（300字以内）",
    "analysis": {{
        "market_summary": "整体市场分析（100字以内）",
        "top_picks": "最值得关注的3只股票（代码及简述理由）",
        "recommendations": [
            {{"symbol": "代码", "name": "名称", "industry": "行业", "rating": "推荐等级", "reason": "推荐理由（40字内）"}}
        ]
    }},
    "is_final": true
}}
```"""

    print_section("步骤 3: 调用大模型分析")

    print(f"提示词长度: {len(prompt)} 字符")
    print(f"正在调用阿里云 DashScope 模型...")

    # 创建 Anthropic 客户端 - 使用阿里云百炼 Coding Plan 兼容接口
    client = AsyncAnthropic(
        api_key=os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("ANTHROPIC_API_KEY", "sk-ant-xxx"),
        base_url="https://coding.dashscope.aliyuncs.com/apps/anthropic"
    )

    start_time = datetime.now()

    try:
        response = await client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20240529"),  # Coding Plan 支持的模型
            max_tokens=2048,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}],
        )

        elapsed = (datetime.now() - start_time).total_seconds()

        # 解析响应 - 兼容 ThinkingBlock 和 TextBlock
        content = ""
        for block in response.content:
            if hasattr(block, 'text'):
                content += block.text
            elif hasattr(block, 'thinking'):
                content += block.thinking or ""
            elif hasattr(block, 'content'):
                content += str(block.content or "")

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
                print(f"  {reasoning}")

            # 显示分析结果
            analysis = decision.get('analysis', {})

            top_picks = analysis.get('top_picks', '')
            if top_picks:
                print(f"\n【重点关注】")
                print(f"  {top_picks}")

            recommendations = analysis.get('recommendations', [])

            if recommendations:
                print(f"\n【所有股票推荐排序】")
                print(f"\n{'排名':<6}{'代码':<8}{'名称':<10}{'行业':<10}{'推荐等级':<10}{'换手率':<8}{'主力净':<10}{'推荐理由'}")
                print("-" * 130)
                for i, rec in enumerate(recommendations, 1):
                    # 从原始股票数据中查找换手率和资金流向
                    stock_data = next((s for s in stocks if s['symbol'] == rec['symbol']), {})
                    money_flow = stock_data.get('money_flow', {})
                    main_net = money_flow.get('main_net_inflow', 0)
                    main_net_str = f"{main_net/10000:+.1f}万" if main_net != 0 else "-"
                    turnover_str = f"{stock_data.get('turnover_rate', 0):.2f}%"
                    print(f"{i:<6}{rec['symbol']:<8}{rec['name']:<10}{rec['industry']:<10}{rec['rating']:<10}{turnover_str:<8}{main_net_str:<10}{rec['reason'][:40]}...")

            # 市场总结
            market_summary = analysis.get('market_summary', '')
            if market_summary:
                print(f"\n【市场分析】")
                print(f"  {market_summary}")

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
│ 数据来源            │   真实历史      │
│ 模型响应时间        │ {elapsed:>10.2f} 秒   │
│ 输入 Tokens         │ {response.usage.input_tokens if hasattr(response, 'usage') else 0:>10}      │
│ 输出 Tokens         │ {response.usage.output_tokens if hasattr(response, 'usage') else 0:>10}      │
│ 推荐动作            │ {action_str:>10}      │
│ 推荐股票            │ {symbol_str:>10}      │
│ 置信度              │ {confidence_str:>10}     │
└─────────────────────┴─────────────────┘
            """)

        except json.JSONDecodeError as e:
            print(f"\n解析 JSON 失败: {e}")
            print(f"\n原始响应:")
            print(content[:500])

    except Exception as e:
        print(f"\n调用模型失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="扫描本地股票数据")
    parser.add_argument("--max-stocks", type=int, default=50, help="最大扫描股票数量")

    args = parser.parse_args()

    await scan_local_stocks(max_stocks=args.max_stocks)


if __name__ == "__main__":
    asyncio.run(main())
