# 策略评分系统实现总结

## ✅ 已完成

### 1. 核心模块

| 文件 | 功能 |
|------|------|
| `src/strategy/scoring.py` | 评分引擎 - 实现3个策略的评分规则 |
| `src/strategy/data_preparer.py` | 数据准备器 - 转换数据格式 |
| `src/strategy/executor.py` | 执行器 - 整合评分流程 |
| `src/strategy/manager.py` | 策略管理器 - 加载 YAML 策略 |

### 2. 策略 YAML

| 文件 | 策略类型 | 评分规则数 |
|------|----------|-----------|
| `momentum_trend.yaml` | 动量趋势 | 15条规则 |
| `value_reversal.yaml` | 价值反转 | 12条规则 |
| `breakout_vol.yaml` | 放量突破 | 9条规则 |

### 3. 评分规则示例

#### 动量趋势策略

```
加分:
- 20日涨幅 > 25%     → +20分
- 多头排列 (MA5>MA10>MA20) → +15分
- 主力净流入占比 > 20% → +12分
- 缩量回踩MA10       → +10分

减分:
- 空头排列           → -20分
- 主力大幅净流出     → -15分
- 乖离率 > 5%        → -10分
```

#### 价值反转策略

```
加分:
- PE < 10      → +15分
- PB < 1       → +12分
- ROE > 15%    → +12分
- 股息率 > 5%  → +10分

减分:
- PE > 50      → -10分
- ROE < 8%     → -10分
- 负债率 > 70% → -12分
```

#### 放量突破策略

```
加分:
- 量比 > 2.5        → +18分
- 突破阻力位 > 3%    → +10分
- 横盘 > 30天        → +10分

减分:
- 量比 < 1.2        → -10分
- 假突破风险        → -20分
```

## 📊 测试结果

```
股票: 贵州茅台 (600519)
综合评分: 39/100
综合信号: HOLD

各策略评分:
[动量趋势策略] 28/100 - SELL
  ├─ weak_momentum: +3 (20日涨幅0%-5%偏弱)
  ├─ price_above_ma5: +5 (价格站上MA5)
  ├─ bearish_alignment: -20 (MA5 < MA10 < MA20空头排列)
  └─ price_below_ma20: -10 (价格跌破MA20)

[价值反转策略] 50/100 - HOLD
  (无财务数据，使用基础分)
```

## 🔧 使用方式

### 方式一：直接调用

```python
from src.strategy import get_strategy_manager, StrategyExecutor
from src.strategy.data_preparer import MarketDataPreparer
import pandas as pd

# 准备数据
kline_df = pd.read_csv("data/stocks/600519.csv")
market_data = MarketDataPreparer.prepare_from_df(kline_df)

# 执行分析
manager = get_strategy_manager()
manager.activate(["momentum_trend"])
executor = StrategyExecutor(manager)

result = executor.analyze_with_active_strategies(
    stock_code="600519",
    stock_name="贵州茅台",
    market_data=market_data,
)

print(f"评分: {result.overall_score}")
print(f"信号: {result.overall_signal}")
```

### 方式二：使用 finshare 数据

```python
import finshare as fs

# 获取K线数据
df = fs.get_historical_data("600519.SZ")

# 分析
result = executor.analyze_from_csv(
    stock_code="600519",
    stock_name="贵州茅台",
    kline_df=df,
)
```

## 📝 数据格式要求

### K线数据

```python
# 必需列
columns = ["date", "open", "high", "low", "close", "volume"]

# 数据样例
kline_df = pd.DataFrame([
    {"date": "2026-03-25", "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 1000000},
    # ...
])
```

### 财务数据

```python
# 可选字段
financial_data = {
    "pe": 12.5,      # 市盈率
    "pb": 1.8,       # 市净率
    "roe": 18.5,     # ROE(%)
    "dividend_yield": 3.2,  # 股息率(%)
    "debt_ratio": 45.0,     # 负债率(%)
}
```

## 🎯 扩展策略

### 步骤1：创建 YAML

```yaml
# strategies/my_strategy.yaml
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

### 步骤2：实现评分引擎

```python
# 在 src/strategy/scoring.py 中添加

class MyStrategyScoringEngine:
    @staticmethod
    def get_rules():
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
    def calculate(cls, market_data, financial_data=None):
        factors = []
        score = 50

        for rule in cls.get_rules():
            factor = rule.evaluate(market_data)
            if factor:
                factors.append(factor)
                score += factor["score"]

        return ScoringResult(
            score=max(0, min(100, score)),
            signal=SignalType.BUY if score >= 70 else (SignalType.SELL if score <= 30 else SignalType.HOLD),
            confidence=min(1.0, abs(score - 50) / 50),
            factors=factors,
            reasoning="推理说明"
        )
```

### 步骤3：注册引擎

```python
# 在 src/strategy/scoring.py 末尾

STRATEGY_ENGINES = {
    "my_strategy": MyStrategyScoringEngine,
    # ...
}
```

## 📚 相关文档

- `docs/strategy_scoring_guide.md` - 完整使用指南
- `strategies/*.yaml` - 策略定义文件
- `scripts/test_scoring.py` - 测试示例

## 🚀 下一步

1. **集成真实数据** - 连接 finshare 下载的数据
2. **完善规则** - 根据回测结果调整评分权重
3. **Web界面** - 在前端展示评分详情和因子
