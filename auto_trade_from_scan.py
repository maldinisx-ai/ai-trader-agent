#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整自动交易脚本：扫描 → AI分析 → 自动买入

流程：
1. 扫描本地所有股票数据 (data/stocks/)
2. AI分析并推荐最佳股票
3. 风控检查
4. 自动执行买入
5. 更新账户持仓
"""
import asyncio
import os
import sys
import io
import json
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd

# 设置控制台编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from anthropic import AsyncAnthropic
from simulation.account import Account
from simulation.matcher import Matcher
from core.policy_engine import PolicyEngine
from core.survival_rules import SurvivalRules
from core.schemas import Order, OrderSide, OrderType, QuoteData
from core.scoring import TrendScoringSystem
from src.indicators import QuoteDataAnalyzer
from tools.trading.place_order import PlaceOrderTool
from tools.trading.get_positions import GetPositionsTool


def print_section(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_trade_record(action: str, symbol: str, quantity: int, price: float, reason: str):
    """打印交易记录"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n{'='*60}")
    print(f"📝 交易记录 - {timestamp}")
    print(f"{'='*60}")
    print(f"操作:   {action}")
    print(f"股票:   {symbol}")
    print(f"数量:   {quantity} 股")
    print(f"价格:   ¥{price:.2f}")
    print(f"金额:   ¥{quantity * price:,.2f}")
    print(f"理由:   {reason}")
    print(f"{'='*60}\n")


def calculate_stock_scores(stocks: List[Dict]) -> Dict[str, Any]:
    """
    使用内置策略系统计算所有股票的评分

    Returns:
        评分字典 {symbol: {score, signal, details}}
    """
    print_section("步骤 1.5: 策略评分分析")

    scoring_system = TrendScoringSystem()
    scores = {}

    for stock in stocks:
        symbol = stock['symbol']
        # 尝试多个可能的路径和文件名格式
        possible_names = [
            f'{symbol}.csv',
            f'{symbol}_SZ.csv',
            f'{symbol}_SH.csv',
            f'klines_{symbol}.csv',
        ]

        csv_path = None
        for name in possible_names:
            path = f'data/stocks/{name}'
            if os.path.exists(path):
                csv_path = path
                break

        if not csv_path:
            scores[symbol] = {
                'total_score': 0,
                'buy_signal': 'WAIT',
                'error': '无历史数据'
            }
            continue

        try:
            # 读取历史K线数据
            if not os.path.exists(csv_path):
                scores[symbol] = {
                    'total_score': 0,
                    'buy_signal': 'WAIT',
                    'error': '无历史数据'
                }
                continue

            df = pd.read_csv(csv_path)
            # 处理不同的日期列名
            date_col = None
            for col in ['trade_date', 'date', 'timestamp']:
                if col in df.columns:
                    date_col = col
                    break

            if not date_col:
                scores[symbol] = {
                    'total_score': 0,
                    'buy_signal': 'WAIT',
                    'error': '无日期列'
                }
                continue

            df[date_col] = pd.to_datetime(df[date_col])
            df = df.sort_values(date_col).tail(60)  # 使用最近60天

            # 构建 QuoteData 列表
            quotes = []
            for _, row in df.iterrows():
                # 处理不同的列名格式
                close_col = 'close_price' if 'close_price' in row else 'close'
                open_col = 'open_price' if 'open_price' in row else 'open'
                high_col = 'high_price' if 'high_price' in row else 'high'
                low_col = 'low_price' if 'low_price' in row else 'low'

                quotes.append(QuoteData(
                    symbol=symbol,
                    name=stock['name'],
                    price=float(row[close_col]),
                    change=0,  # 后续计算
                    volume=int(row['volume']),
                    amount=float(row.get('amount', 0)),
                    high=float(row[high_col]),
                    low=float(row[low_col]),
                    open=float(row[open_col]),
                    timestamp=row[date_col],
                ))

            # 使用评分系统
            analyzer = QuoteDataAnalyzer(quotes)
            result = scoring_system.score(analyzer)

            scores[symbol] = {
                'total_score': result.total_score,
                'buy_signal': result.buy_signal.value,
                'trend_score': result.trend_score,
                'bias_score': result.bias_score,
                'volume_score': result.volume_score,
                'support_score': result.support_score,
                'macd_score': result.macd_score,
                'rsi_score': result.rsi_score,
                'reasons': result.reasons,
                'risk_factors': result.risk_factors,
            }

        except Exception as e:
            scores[symbol] = {
                'total_score': 0,
                'buy_signal': 'WAIT',
                'error': str(e)
            }

    # 按评分排序
    sorted_scores = sorted(scores.items(), key=lambda x: x[1].get('total_score', 0), reverse=True)

    # 显示评分结果
    print(f"\n{'排名':<6}{'代码':<10}{'名称':<12}{'总分':<8}{'信号':<12}{'趋势':<8}{'乖离':<8}{'量能':<8}")
    print("-" * 100)
    for i, (symbol, score_data) in enumerate(sorted_scores[:10], 1):
        error = score_data.get('error', '')
        if error:
            print(f"{i:<6}{symbol:<10}{stock['name']:<12}{'N/A':<8}{'无数据':<12}{error}")
        else:
            print(f"{i:<6}{symbol:<10}{stock['name']:<12}{score_data['total_score']:<8}"
                  f"{score_data['buy_signal']:<12}{score_data['trend_score']:<8}"
                  f"{score_data['bias_score']:<8}{score_data['volume_score']:<8}")

    return scores


def load_local_stocks_from_csv(max_stocks: int = 50):
    """从本地CSV文件加载股票数据"""
    stocks_dir = 'data/stocks'

    if not os.path.exists(stocks_dir):
        print(f"❌ 未找到股票数据目录: {stocks_dir}")
        return []

    # 获取所有CSV文件
    csv_files = [f for f in os.listdir(stocks_dir) if f.endswith('.csv')]
    print(f"📁 从 {stocks_dir} 读取到 {len(csv_files)} 只股票文件")

    # 读取股票列表映射
    name_mapping = {}
    mapping_file = 'data/stock_industry_mapping.csv'
    if os.path.exists(mapping_file):
        df_mapping = pd.read_csv(mapping_file)
        for _, row in df_mapping.iterrows():
            code = str(row['股票代码'])
            name_mapping[code] = {
                'name': row['股票名称'],
                'industry': row['申万行业']
            }

    # 读取K线数据
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
            name = name_mapping.get(code, {}).get('name', f'股票{code}')
            industry = name_mapping.get(code, {}).get('industry', '未知')

            stocks_data.append({
                'symbol': code,
                'name': name,
                'industry': industry,
                'price': price,
                'change': change,
                'volume': int(latest['volume']),
                'high': float(latest['high_price']),
                'low': float(latest['low_price']),
                'amount': float(latest['amount'])
            })

        except Exception as e:
            continue

    print(f"✅ 成功解析 {len(stocks_data)} 只股票数据")
    return stocks_data


async def ai_analyze_stocks(stocks: List[Dict], account: Account, scores: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    使用AI分析所有股票并给出推荐

    Returns:
        决策字典: {action, symbol, quantity, price, confidence, reasoning}
    """
    print_section("步骤 2: AI 智能分析")

    # 构建股票信息（包含评分）
    if scores:
        # 使用评分系统排序
        sorted_stocks = sorted(stocks, key=lambda s: scores.get(s['symbol'], {}).get('total_score', 0), reverse=True)
        stock_info = "\n".join([
            f"- {s['symbol']} {s['name']} ({s['industry']}): "
            f"价格 {s['price']:.2f}, 涨跌幅 {s['change']:+.2f}%, "
            f"评分 {scores.get(s['symbol'], {}).get('total_score', 0):.0f}/100, "
            f"信号 {scores.get(s['symbol'], {}).get('buy_signal', 'WAIT')}"
            for s in sorted_stocks
        ])

        # 添加评分详情
        score_details = "\n\n## 策略评分详情 (Top 5)\n\n"
        for i, s in enumerate(sorted_stocks[:5], 1):
            symbol = s['symbol']
            score_data = scores.get(symbol, {})
            if score_data.get('error'):
                continue

            score_details += f"### {i}. {symbol} {s['name']} - {score_data['total_score']}分\n"
            score_details += f"- 趋势: {score_data['trend_score']}/30 "
            score_details += f"- 乖离: {score_data['bias_score']}/20 "
            score_details += f"- 量能: {score_data['volume_score']}/15\n"
            score_details += f"- 支撑: {score_data['support_score']}/10 "
            score_details += f"- MACD: {score_data['macd_score']}/15 "
            score_details += f"- RSI: {score_data['rsi_score']}/10\n"

            if score_data.get('reasons'):
                score_details += f"- 买入理由: {', '.join(score_data['reasons'][:3])}\n"
            if score_data.get('risk_factors'):
                score_details += f"- 风险因素: {', '.join(score_data['risk_factors'][:2])}\n"
            score_details += "\n"
    else:
        # 原始格式（无评分）
        stock_info = "\n".join([
            f"- {s['symbol']} {s['name']} ({s['industry']}): 价格 {s['price']:.2f}, 涨跌幅 {s['change']:+.2f}%, 成交量 {s['volume']:,}手"
            for s in stocks
        ])
        score_details = ""

    # 获取账户状态
    account_info = account.get_account_info()
    positions = account.get_positions()

    # 构建持仓信息
    position_info = "空仓" if not positions else "\n".join([
        f"- {p.symbol}: {p.shares}股, 成本 ¥{p.avg_cost:.2f}, 市值 ¥{p.market_value:,.2f}"
        for p in positions
    ])

    # 账户状态
    account_state = f"""
## 当前账户状态
- 现金: ¥{account_info['cash']:,.2f}
- 总资产: ¥{account_info['total_value']:,.2f}
- 持仓市值: ¥{account_info['position_value']:,.2f}
- 盈亏: ¥{account_info['profit_loss']:+,.2f} ({account_info['profit_loss_ratio']*100:+.2f}%)
- 回撤率: {(1 - account_info['total_value'] / account_info['initial_cash']) * 100:.2f}%
- 当前持仓: {position_info}

## 待分析股票列表 ({len(stocks)}只)
{stock_info}
{score_details}
"""

    # 构建提示词
    prompt = f"""你是一个专业的股票交易智能体。

{account_state}

## 分析要求
请对以上所有股票进行全面分析，并按照以下要求给出建议：

1. **市场环境判断**: 分析当前市场整体情况
2. **排序推荐**: 根据投资价值对所有股票进行排序
3. **推荐等级**: 为每只股票标注推荐等级（强烈买入/买入/观望/卖出/强烈卖出）
4. **最佳选择**: 从中选择1只最具投资价值的股票
5. **操作建议**: 给出具体的买入/卖出建议

## 风控要求
- 单只股票最大仓位: 30%
- 现金限制: 不能超过可用现金
- 止损: 亏损 > 8% 止损
- 止盈: 盈利 > 20% 减半仓

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

    print(f"📊 提示词长度: {len(prompt)} 字符")
    print("🤖 正在调用智谱 GLM 模型...")

    # 创建 Anthropic 客户端
    client = AsyncAnthropic(
        api_key=os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("ANTHROPIC_API_KEY", "sk-ant-xxx"),
        base_url=os.getenv("ANTHROPIC_BASE_URL")
    )

    # 使用配置的模型名称
    model_name = os.getenv("ANTHROPIC_MODEL", "glm-4.7")
    start_time = datetime.now()

    try:
        response = await client.messages.create(
            model=model_name,
            max_tokens=2048,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}],
        )

        elapsed = (datetime.now() - start_time).total_seconds()

        # 解析响应 - 处理不同类型的内容块
        content = ""
        for block in response.content:
            if hasattr(block, 'text'):
                content += block.text
            elif hasattr(block, 'thinking'):
                # ThinkingBlock 跳过思考过程，只获取最终输出
                pass
            else:
                # 其他类型尝试转为字符串
                content += str(block) if hasattr(block, '__str__') else ""

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

        decision = json.loads(json_str)

        print(f"\n⏱️  AI响应时间: {elapsed:.2f}秒")
        print(f"📥 Tokens: {response.usage.input_tokens} → {response.usage.output_tokens}")

        return decision

    except Exception as e:
        print(f"❌ AI分析失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def execute_trade(
    decision: Dict[str, Any],
    account: Account,
    policy_engine: PolicyEngine,
    matcher: Matcher
) -> bool:
    """
    执行交易决策

    Returns:
        bool: 交易是否成功
    """
    print_section("步骤 4: 执行交易")

    action = decision.get('action', '').upper()
    symbol_raw = decision.get('symbol', '')
    # 清理股票代码（移除 .SZ, .SH 等后缀）
    symbol = str(symbol_raw).replace('.SZ', '').replace('.SH', '').replace('.', '')
    quantity = decision.get('quantity', 0)
    price = decision.get('price', 0)
    reasoning = decision.get('reasoning', '')

    # 如果不是买入或卖出，直接返回
    if action not in ['BUY', 'SELL']:
        print(f"🔒 决策: {action} - 无需交易")
        return False

    # 创建订单
    order = Order(
        order_id=f"AUTO_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        symbol=symbol,
        side=OrderSide.BUY if action == 'BUY' else OrderSide.SELL,
        quantity=int(quantity),
        price=float(price) if price else 0.0,
        order_type=OrderType.MARKET,
    )

    print(f"\n📋 订单信息:")
    print(f"   订单ID: {order.order_id}")
    print(f"   股票: {order.symbol}")
    print(f"   方向: {order.side.value}")
    print(f"   数量: {order.quantity} 股")
    print(f"   价格: {'市价' if order.price == 0 else f'¥{order.price:.2f}'}")

    # 风控检查
    print(f"\n🛡️  风控检查...")
    policy_check = policy_engine.validate_order(
        order=order,
        current_time=datetime.now().time()
    )

    if not policy_check.allowed:
        print(f"❌ 风控拒绝: {policy_check.reason}")
        return False

    print(f"✅ 风控通过")

    # 执行撮合
    print(f"\n💹 执行撮合...")
    match_result = await matcher.match(order)

    if not match_result.success:
        print(f"❌ 撮合失败: {match_result.reason}")
        return False

    # 更新账户
    success = account.update_from_trade(match_result)

    if not success:
        print(f"❌ 账户更新失败")
        return False

    # 打印交易记录
    print_trade_record(
        action=f"{'买入' if order.side == OrderSide.BUY else '卖出'}",
        symbol=order.symbol,
        quantity=match_result.filled_quantity,
        price=match_result.filled_price,
        reason=reasoning[:100]
    )

    print(f"✅ 交易成功!")
    print(f"   成交数量: {match_result.filled_quantity} 股")
    print(f"   成交价格: ¥{match_result.filled_price:.2f}")
    print(f"   成交金额: ¥{match_result.filled_quantity * match_result.filled_price:,.2f}")
    print(f"   手续费: ¥{match_result.commission:.2f}")
    if match_result.stamp_duty > 0:
        print(f"   印花税: ¥{match_result.stamp_duty:.2f}")
    if match_result.pnl and match_result.pnl != 0:
        print(f"   盈亏: ¥{match_result.pnl:+,.2f}")

    return True


async def auto_trade_from_scan(max_stocks: int = 50, enable_trading: bool = True):
    """
    完整自动交易流程

    Args:
        max_stocks: 最大扫描股票数量
        enable_trading: 是否启用真实交易（False为模拟模式）
    """
    print("=" * 80)
    print(" AI Trader Agent - 完整自动交易系统")
    print("=" * 80)
    print(f"扫描模式: 本地数据 (data/stocks/)")
    print(f"最大股票: {max_stocks} 只")
    print(f"交易模式: {'🟢 真实交易' if enable_trading else '🟡 模拟交易'}")
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 初始化组件
    print_section("步骤 0: 初始化系统")

    print("🔧 初始化账户...")
    account = Account(initial_cash=1_000_000.0)
    print(f"✅ 初始资金: ¥{account.initial_cash:,.2f}")

    print("🔧 初始化撮合引擎...")
    matcher = Matcher()

    print("🔧 初始化风控引擎...")
    policy_engine = PolicyEngine(cash=account.initial_cash)

    print("🔧 初始化生存规则...")
    survival_rules = SurvivalRules(initial_cash=account.initial_cash)

    # 步骤1: 扫描股票
    print_section("步骤 1: 扫描本地股票")

    stocks = load_local_stocks_from_csv(max_stocks=max_stocks)

    if not stocks:
        print("❌ 没有可用的股票数据")
        return

    # 显示股票列表（前10只）
    print(f"\n{'代码':<10}{'名称':<12}{'价格':<10}{'涨跌幅':<10}")
    print("-" * 50)
    for s in stocks[:10]:
        change_str = f"{s['change']:+.2f}%"
        print(f"{s['symbol']:<10}{s['name']:<12}{s['price']:<10.2f}{change_str:<10}")
    if len(stocks) > 10:
        print(f"... 还有 {len(stocks) - 10} 只股票")

    # 步骤1.5: 策略评分
    scores = calculate_stock_scores(stocks)

    # 步骤2: AI分析（带评分）
    decision = await ai_analyze_stocks(stocks, account, scores)

    if not decision:
        print("❌ AI分析失败，终止流程")
        return

    # 显示AI推荐结果
    print_section("步骤 3: AI 推荐结果")

    action = decision.get('action', 'N/A').upper()
    symbol = decision.get('symbol', 'N/A')
    quantity = decision.get('quantity', 0)
    price = decision.get('price', 0)
    confidence = decision.get('confidence', 0)
    reasoning = decision.get('reasoning', '')

    print(f"\n🎯 推荐决策:")
    print(f"   动作: {action}")
    print(f"   股票: {symbol}")
    print(f"   数量: {quantity} 股")
    print(f"   价格: {f'¥{price:.2f}' if price else '市价'}")
    print(f"   置信度: {confidence:.2%}")

    print(f"\n💭 推理过程:")
    print(f"   {reasoning}")

    # 显示分析详情
    analysis = decision.get('analysis', {})

    top_picks = analysis.get('top_picks', '')
    if top_picks:
        print(f"\n⭐ 重点关注:")
        print(f"   {top_picks}")

    recommendations = analysis.get('recommendations', [])
    if recommendations:
        print(f"\n📊 推荐排序 (前5名):")
        for i, rec in enumerate(recommendations[:5], 1):
            print(f"   {i}. {rec['symbol']} {rec['name']} - {rec['rating']}")
            print(f"      {rec['reason']}")

    market_summary = analysis.get('market_summary', '')
    if market_summary:
        print(f"\n📈 市场分析:")
        print(f"   {market_summary}")

    # 步骤3: 确认交易
    if not enable_trading:
        print_section("模拟模式 - 不执行交易")
        print("⚠️  当前为模拟模式，未执行实际交易")
        print("💡 如需启用真实交易，设置 enable_trading=True")
        return

    # 步骤4: 执行交易
    success = await execute_trade(
        decision=decision,
        account=account,
        policy_engine=policy_engine,
        matcher=matcher
    )

    # 步骤5: 显示最终状态
    print_section("步骤 5: 账户状态")

    account_info = account.get_account_info()
    positions = account.get_positions()

    print(f"\n💰 资金情况:")
    print(f"   初始资金: ¥{account_info['initial_cash']:,.2f}")
    print(f"   当前现金: ¥{account_info['cash']:,.2f}")
    print(f"   持仓市值: ¥{account_info['position_value']:,.2f}")
    print(f"   总资产:   ¥{account_info['total_value']:,.2f}")
    print(f"   总盈亏:   ¥{account_info['profit_loss']:+,.2f} ({account_info['profit_loss_ratio']*100:+.2f}%)")

    if positions:
        print(f"\n📋 当前持仓:")
        for pos in positions:
            profit = pos.market_value - (pos.shares * pos.avg_cost)
            profit_ratio = (profit / (pos.shares * pos.avg_cost)) * 100 if pos.shares > 0 else 0
            print(f"   {pos.symbol}: {pos.shares}股")
            print(f"      成本: ¥{pos.avg_cost:.2f}")
            print(f"      现价: ¥{pos.current_price:.2f}")
            print(f"      市值: ¥{pos.market_value:,.2f}")
            if profit != 0:
                print(f"      盈亏: ¥{profit:+,.2f} ({profit_ratio:+.2f}%)")
    else:
        print(f"\n📋 当前持仓: 空仓")

    print_section("执行完成")

    print(f"""
┌─────────────────────┬─────────────────┐
│     项目            │     数值        │
├─────────────────────┼─────────────────┤
│ 扫描股票数量        │ {len(stocks):>10} 只    │
│ 推荐动作            │ {action:>10}      │
│ 推荐股票            │ {symbol:>10}      │
│ 交易状态            │ {'成功' if success else '未执行':>10}      │
│ 执行时间            │ {datetime.now().strftime('%H:%M:%S'):>10}      │
└─────────────────────┴─────────────────┘
    """)


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="完整自动交易系统")
    parser.add_argument("--max-stocks", type=int, default=50, help="最大扫描股票数量")
    parser.add_argument("--enable-trading", action="store_true", help="启用真实交易（默认为模拟模式）")

    args = parser.parse_args()

    await auto_trade_from_scan(
        max_stocks=args.max_stocks,
        enable_trading=args.enable_trading
    )


if __name__ == "__main__":
    asyncio.run(main())
