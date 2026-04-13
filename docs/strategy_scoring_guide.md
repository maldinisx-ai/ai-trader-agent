# 策略评分系统使用指南

## 概述

策略评分系统是 ai-trader-agent 的核心组件，负责根据策略规则对股票进行量化评分，并生成买卖信号。

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                     策略评分系统架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────────┐    ┌───────────┐ │
│  │ 策略 YAML    │───>│  数据准备器      │───>│  评分引擎  │ │
│  │ (规则定义)    │    │  (数据标准化)    │    │  (规则匹配)│ │
│  └──────────────┘    └──────────────────┘    └───────────┘ │
│                               │                       │          │
│                               ▼                       ▼          │
│                        ┌──────────────┐    ┌───────────┐  │
│                        │  市场数据    │    │ 财务数据  │  │
│                        │  (K线/资金)  │    │ (PE/ROE)  │  │
│                        └──────────────┘    └───────────┘  │
│                                                        │
└─────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. 策略 YAML (`strategies/`)

定义策略的评分规则和执行逻辑。

**关键字段**:
- `category`: 策略类别（trend/reversal/pattern）
- `core_rules`: 关联的风控规则
- `required_tools`: 需要的数据工具
- `instructions`: 策略说明

**评分建议**:
```yaml
评分调整建议：
  - 条件描述：+分数（满足时加分）
  - 反向条件：-分数（不满足时减分）
```

### 2. 评分引擎 (`src/strategy/scoring.py`)

包含三个策略引擎：

| 引擎 | 策略 | 核心逻辑 |
|------|------|----------|
| `MomentumScoringEngine` | 动量趋势 | 趋势 + 动量 + 资金流向 |
| `ValueReversalScoringEngine` | 价值反转 | 估值 + 盈利 + 反转信号 |
| `BreakoutVolumeScoringEngine` | 放量突破 | 突破 + 量价 + 形态 |

**评分规则**:
- 每个规则有独立的评分条件
- 规则按类别分组（momentum/trend/money_flow等）
- 总分 = 基础分(50) + 各规则得分

### 3. 数据准备器 (`src/strategy/data_preparer.py`)

- `MarketDataPreparer`: 处理 K线数据，计算技术指标
- `FinancialDataPreparer`: 处理财务数据

### 4. 执行器 (`src/strategy/executor.py`)

整合所有组件，执行策略分析。

## 使用方法

### 方式一：直接使用 Python API

```python
from src.strategy import get_strategy_manager, StrategyExecutor
from src.strategy.data_preparer import MarketDataPreparer
import pandas as pd

# 1. 加载策略
manager = get_strategy_manager()
manager.activate(["momentum_trend"])

# 2. 准备数据
kline_df = pd.read_csv("data/stocks/600519.csv")
market_data = MarketDataPreparer.prepare_from_df(kline_df)

# 3. 执行分析
executor = StrategyExecutor(manager)
result = executor.analyze_with_active_strategies(
    stock_code="600519",
    stock_name="贵州茅台",
    market_data=market_data,
)

# 4. 获取结果
print(f"综合评分: {result.overall_score}")
print(f"综合信号: {result.overall_signal}")

for signal in result.signals:
    print(f"{signal.display_name}: {signal.score} - {signal.signal}")
```

### 方式二：从 CSV 文件分析

```python
# 读取 K线数据
kline_df = pd.read_csv("data/stocks/600519.csv")

# 可选：读取财务数据
financial_df = pd.read_csv("data/financial/600519_indicators.csv")

# 执行分析
result = executor.analyze_from_csv(
    stock_code="600519",
    stock_name="贵州茅台",
    kline_df=kline_df,
    financial_df=financial_df,
)
```

### 方式三：运行示例脚本

```bash
python scripts/test_strategy_scoring.py
```

## 数据格式要求

### K线数据

必须包含以下列：

| 列名 | 类型 | 说明 |
|------|------|------|
| date | str | 日期 (YYYY-MM-DD) |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| volume | int | 成交量 |

### 财务数据

可选，包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| pe | float | 市盈率 |
| pb | float | 市净率 |
| roe | float | ROE (%) |
| dividend_yield | float | 股息率 (%) |
| debt_ratio | float | 负债率 (%) |

## 评分规则

### 动量趋势策略

**加分项**:
- 20日涨幅 > 25%: +20
- 多头排列 (MA5>MA10>MA20): +15
- 主力净流入占比 > 20%: +12
- 缩量回踩MA10: +10

**减分项**:
- 空头排列: -20
- 主力大幅净流出: -15
- 放量滞涨: -12
- 乖离率 > 5%: -10

### 价值反转策略

**加分项**:
- PE < 10: +15
- PB < 1: +12
- ROE > 15%: +12
- 股息率 > 5%: +10
- 距高点跌幅 > 40%: +15

**减分项**:
- PE > 50: -10
- ROE < 8%: -10
- 负债率 > 70%: -12

### 放量突破策略

**加分项**:
- 量比 > 2.5: +18
- 突破阻力位 > 3%: +10
- 横盘 > 30天: +10

**减分项**:
- 量比 < 1.2: -10
- 假突破风险: -20

## 扩展策略

### 1. 创建新策略 YAML

```bash
# 在 strategies/ 目录创建新文件
vim strategies/my_strategy.yaml
```

```yaml
name: my_strategy
display_name: 我的策略
description: 策略描述
category: trend
required_tools:
  - get_daily_history
  - analyze_trend

instructions: |
  **我的策略**

  评分调整：
  - 条件满足：+10
  - 条件不满足：-5
```

### 2. 实现评分引擎

在 `src/strategy/scoring.py` 中创建新的引擎类：

```python
class MyStrategyScoringEngine:
    @staticmethod
    def get_rules() -> List[ScoringRule]:
        return [
            ScoringRule(
                name="my_rule",
                condition=lambda d: d.get("some_field", 0) > 10,
                score=10,
                reason="规则说明",
                category="my_category"
            ),
        ]

    @classmethod
    def calculate(cls, market_data, financial_data=None) -> ScoringResult:
        # 实现评分逻辑
        pass
```

### 3. 注册引擎

在 `src/strategy/scoring.py` 的 `STRATEGY_ENGINES` 中添加：

```python
STRATEGY_ENGINES = {
    "my_strategy": MyStrategyScoringEngine,
    # ...
}
```

## API 集成

策略评分系统已集成到 FastAPI 中：

```bash
# 启动 API 服务
python run.py --api-only

# 分析股票
curl -X POST http://localhost:8000/api/v1/analysis/analyze \
  -H "Content-Type: application/json" \
  -d '{"stock_code": "600519"}'
```

## 调试技巧

### 1. 查看评分因子

```python
for signal in result.signals:
    print(f"\n【{signal.display_name}】评分因子:")
    for factor in signal.factors:
        print(f"  {factor['name']}: {factor['score']} ({factor['reason']})")
```

### 2. 查看原始数据

```python
print("\n市场数据:")
for key, value in result.market_data.items():
    print(f"  {key}: {value}")
```

### 3. 验证规则匹配

```python
from src.strategy.scoring import MomentumScoringEngine

rules = MomentumScoringEngine.get_rules()
for rule in rules:
    print(f"{rule.name}: {rule.reason}")
```

## 常见问题

### Q: 如何调整评分权重？

A: 修改 `scoring.py` 中各规则的 `score` 值。

### Q: 如何添加新的评分条件？

A: 在对应策略引擎的 `get_rules()` 方法中添加新的 `ScoringRule`。

### Q: 评分为什么是 50 分？

A: 50 分是基础分，需要规则匹配才能增减分数。检查数据格式是否正确。

### Q: 如何集成实时数据？

A: 实现自定义的数据准备器，将实时数据转换为标准格式。

## 相关文件

- `strategies/` - 策略 YAML 文件
- `src/strategy/manager.py` - 策略管理器
- `src/strategy/scoring.py` - 评分引擎
- `src/strategy/executor.py` - 执行器
- `src/strategy/data_preparer.py` - 数据准备器
- `scripts/test_strategy_scoring.py` - 使用示例
