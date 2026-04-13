# Agent 回测引擎使用指南

## 概述

Agent 回测引擎让 LLM 在历史数据上真正自主决策，而不是使用固定的量化规则。

### 与传统回测的区别

| 特性 | 传统回测 | Agent 回测 |
|------|----------|-----------|
| **决策者** | 固定策略（如 MA 金叉） | LLM 自主推理 |
| **决策依据** | 技术指标规则 | 市场+技术+多因素分析 |
| **适应性** | 固定不变 | 根据市场状态调整 |
| **可解释性** | 规则明确 | 思维链可见 |

---

## 快速开始

### 1. 准备数据

首先下载股票数据：

```bash
python scripts/download_batch_stocks.py
```

### 2. 运行 Agent 回测

使用本地 Ollama 模型（默认）：

```bash
python scripts/run_agent_backtest.py 600519
```

使用 Claude API：

```bash
python scripts/run_agent_backtest.py 600519 --api-key YOUR_API_KEY
```

多只股票：

```bash
python scripts/run_agent_backtest.py 600519,000001 --interval 10
```

### 3. 查看结果

回测完成后，结果保存在 `data/agent_backtest/YYYYMMDD_HHMMSS/`：

- `backtest_report.json` - 完整回测报告
- `decision_records.json` - 所有决策记录
- `trade_records.json` - 交易记录
- `decision_analysis.png` - 决策可视化图表

---

## 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--api-key` | 环境变量 | Anthropic API Key |
| `--local-url` | `http://localhost:11434` | Ollama 服务地址 |
| `--interval` | 5 | 决策间隔（天），避免每个 K 线都调用 LLM |
| `--cash` | 100000 | 初始资金 |
| `--max-position` | 0.30 | 最大仓位比例 |
| `--output-dir` | 自动生成 | 输出目录 |

---

## 策略对比

对比 LLM Agent 与传统策略：

```bash
python scripts/compare_strategies.py 600519 --strategies ma_cross,agent
```

对比多种策略：

```bash
python scripts/compare_strategies.py 600519 --strategies ma_cross,triple_ma,agent
```

使用已有结果进行对比：

```bash
python scripts/compare_strategies.py 600519 --use-existing
```

---

## 决策记录分析

每个决策记录包含以下信息：

```json
{
  "date": "2024-03-22",
  "symbol": "600519",
  "price": 1680.00,
  "action": "buy",
  "confidence": 0.75,
  "reasoning": "当前RSI超卖，MACD即将金叉，建议买入",
  "thought_process": "[迭代 1] ...",
  "iterations": 2,
  "executed": true,
  "execution_result": "成交 100股 @ ¥1680.00",
  "model_used": "llm",
  "survival_level": "normal",
  "market_regime": "bull"
}
```

### 关键字段说明

- **action**: `buy`/`sell`/`hold`/`wait`
- **confidence**: 0-1 之间的置信度
- **reasoning**: LLM 的推理说明
- **thought_process**: 完整的思维链（多轮对话）
- **iterations**: 决策迭代次数
- **executed**: 是否实际执行（可能被风控拒绝）

---

## 输出文件

### 1. 回测报告 (`backtest_report.json`)

```json
{
  "backtest_type": "agent_llm",
  "initial_cash": 100000.0,
  "final_value": 115000.0,
  "total_return": 0.15,
  "total_pnl": 15000.0,
  "total_trades": 12,
  "total_llm_calls": 20,
  "performance": {
    "sharpe_ratio": 1.2,
    "max_drawdown": -0.08,
    "win_rate": 0.6
  }
}
```

### 2. 决策可视化 (`decision_analysis.png`)

包含三个子图：
- 决策分布（买入/卖出/持有/等待）
- 交易决策置信度随时间变化
- 决策执行率（已执行 vs 未执行）

### 3. 对比分析图表 (`comparison_chart.png`)

对比 LLM Agent 与传统策略的：
- 总收益率
- 夏普比率
- 最大回撤
- 综合指标雷达图

---

## 性能优化建议

### 1. 决策间隔

较小的 `interval` 会产生更多决策，但也会：
- 增加 LLM API 调用成本
- 延长回测时间

建议：
- 测试阶段：`--interval 10` 或更大
- 正式回测：`--interval 5`

### 2. 本地模型优先

使用本地 Ollama 模型可以：
- 零 API 成本
- 更快的响应速度
- 保护数据隐私

但需要确保 Ollama 服务正常运行：

```bash
# 检查 Ollama 状态
curl http://localhost:11434/api/tags

# 启动 Ollama
ollama serve
```

### 3. 数据缓存

当前版本每次回测都会重新调用 LLM。可以考虑：
- 缓存相似市场条件下的决策
- 使用决策指纹避免重复调用

---

## 常见问题

### Q1: 为什么有些决策没有执行？

A: 可能被风控规则拒绝：
- 资金不足
- 涨跌停限制
- 持仓超限
- 冷却期限制

查看决策记录中的 `execution_result` 字段。

### Q2: LLM 为什么选择 `wait` 而不是交易？

A: LLM 可能认为：
- 当前市场条件不明确
- 置信度不够高
- 等待更好的入场时机

这是正常的谨慎行为。

### Q3: 如何提高 LLM 决策质量？

A: 可以：
1. 优化 Prompt（在 `core/model_router.py` 中）
2. 提供更多上下文信息（如新闻、财报）
3. 使用更强的模型（如 Claude Opus）
4. 添加反思机制（从失败中学习）

### Q4: 回测时间太长怎么办？

A:
1. 增大 `--interval` 值
2. 使用本地模型而非 API
3. 减少回测股票数量
4. 缩短回测时间范围

---

## 下一步

1. **优化 Prompt**: 在 `core/model_router.py` 的 `_build_prompt` 方法中改进提示词
2. **添加更多工具**: 在 `tools/` 目录添加新闻、财报等数据获取工具
3. **实现反思机制**: 使用 `core/reflection.py` 从失败交易中学习
4. **策略集成**: 将 Agent 决策与传统策略信号融合

---

## 文件结构

```
src/
├── agent_backtester.py       # Agent 回测引擎核心类
│
scripts/
├── run_agent_backtest.py     # Agent 回测运行脚本
├── compare_strategies.py      # 策略对比脚本
│
core/
├── agent_loop.py              # ReAct 循环（被回测引擎调用）
├── model_router.py            # 模型路由器（LLM 调用）
├── survival_rules.py          # 生存等级系统
├── market_regime.py           # 市场状态感知
└── policy_engine.py           # 风控引擎
```

---

## 更新日志

- **2026-03-25**: 初始版本，支持 LLM 自主决策回测
