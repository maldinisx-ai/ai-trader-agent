# AI Trader Agent

> 智能交易系统 - 基于 AI 的股票分析和交易策略平台

**项目代号**: ai-trader-agent
**版本**: v0.1.0
**状态**: 🚧 开发中

---

## 项目简介

AI Trader Agent 是一个智能交易系统，提供：
- **多策略分析** - 双均线、MACD、RSI、布林带等技术指标策略
- **AI 智能分析** - 多维度分析股票，提供精准买卖点位
- **React Web 界面** - 现代化的可视化管理界面
- **模拟交易系统** - 完整的虚拟账户、持仓、交易记录管理

### 核心特性

- **策略系统**: 多种技术指标策略，支持激活/停用
- **AI 分析**: 结合技术面、基本面分析
- **Web 界面**: React + TypeScript + TailwindCSS
- **API 接口**: RESTful API，方便集成

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Web 浏览器                                │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  React + TypeScript + TailwindCSS                        ││
│  │  - HomePage      (首页 + 快速分析)                        ││
│  │  - AnalysisPage  (股票分析 + 策略信号)                    ││
│  │  - StrategyPage  (策略管理)                              ││
│  │  - SettingsPage  (系统设置)                              ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                            │ HTTP/JSON
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI 后端服务器                          │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  API 路由 (/api/v1/)                                     ││
│  │  ├── /market/*      → 行情数据 (报价/K线/股票列表)         ││
│  │  ├── /trading/*     → 交易 (账户/持仓/下单/历史)           ││
│  │  ├── /analysis/*    → 股票分析 (多策略信号)                ││
│  │  ├── /strategy/*    → 策略管理 (列表/激活/停用)            ││
│  │  ├── /system/*      → 系统信息 (健康检查/配置)             ││
│  │  └── /memory/*      → 交易记忆 (历史/反思/统计)            ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   核心模块                                    │
│  - simulation/    → 虚拟账户、撮合引擎                        │
│  - core/          → 数据模型、策略执行                        │
│  - src/strategy/  → 策略管理、数据准备                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 快速开始

### 环境要求

**后端:**
- Python 3.10+
- pip

**前端:**
- Node.js 18+
- npm

### 安装

```bash
# 1. 克隆项目
git clone <repo-url>
cd ai-trader-agent

# 2. 安装后端依赖
pip install -r requirements.txt

# 3. 安装前端依赖
cd web
npm install
cd ..
```

### 运行

**方式一：同时启动前后端（推荐）**

```bash
# 终端1: 启动后端 API
cd D:/projects/ai-trader-agent
python -m uvicorn api.app:app --reload --port 8000

# 终端2: 启动前端
cd D:/projects/ai-trader-agent/web
npm run dev
```

**方式二：仅启动后端 API**

```bash
python -m uvicorn api.app:app --reload --port 8000
```

访问 API 文档: http://localhost:8000/docs

---

## AI 模型配置

### 当前配置

本项目实际使用的是 **阿里云百炼 (DashScope Coding Plan)**，通过 Anthropic 兼容接口调用。

| 项目 | 配置 |
|------|------|
| **API 提供商** | 阿里云百炼 (DashScope) |
| **模型** | GLM-4.7 |
| **接口类型** | Anthropic 兼容接口 |
| **Base URL** | `https://coding.dashscope.aliyuncs.com/apps/anthropic` |

### 配置方式

在 `.env` 文件中添加以下配置：

```bash
# 阿里云百炼 Coding Plan 配置
ANTHROPIC_AUTH_TOKEN=sk-sp-your-api-key-here  # Coding Plan 专属 API Key
ANTHROPIC_BASE_URL=https://coding.dashscope.aliyuncs.com/apps/anthropic
ANTHROPIC_MODEL=glm-4.7  # Coding Plan 支持的模型
```

### 工作原理

```
AI Agent (使用 anthropic 库)
    ↓
读取 ANTHROPIC_AUTH_TOKEN 和 ANTHROPIC_BASE_URL
    ↓
请求发送到: https://coding.dashscope.aliyuncs.com/apps/anthropic
    ↓
阿里云百炼服务器处理
    ↓
返回 GLM-4.7 模型的响应
```

### 获取阿里云百炼 API Key

1. 访问阿里云百炼: https://bailian.console.aliyun.com/
2. 注册/登录账号
3. 开通 Coding Plan 服务
4. 创建 API Key
5. 将 key 添加到 `.env` 文件的 `ANTHROPIC_AUTH_TOKEN` 变量

### 自动降级机制

系统支持自动降级，当主 API 不可用时自动切换到备用模型：

| 优先级 | 提供商 | 状态 |
|--------|--------|------|
| 1 | 阿里云百炼 | ✅ 当前使用 |
| 2 | 智谱 GLM | 🔧 备用 (待配置) |
| 3 | 本地 Ollama | 🔧 备用 (待配置) |

如需启用备用模型，在 `.env` 中添加：

```bash
# 智谱 GLM 备用配置
ZHIPU_API_KEY=your_zhipu_key
THIRD_PARTY_BASE_URL=https://open.bigmodel.cn/api/paas/v4
THIRD_PARTY_MODEL=glm-4-flash

# 本地 Ollama 备用配置
OLLAMA_BASE_URL=http://localhost:11434
LOCAL_MODEL_NAME=qwen2.5:7b-q5_K_M
```

---

## 完整 AI 决策测试

项目提供完整的 AI 交易决策测试脚本 `test_agent.py`，该脚本演示了从数据加载到 AI 决策生成的完整流程。

### 测试脚本功能

`test_agent.py` 实现了以下完整流程：

```
本地 K 线数据加载
    ↓
获取最新行情 (QuoteData)
    ↓
初始化 ModelRouter (阿里云百炼)
    ↓
AgentLoop.react_loop (ReAct 循环)
    ↓
AI 模型分析并生成决策
    ↓
输出决策结果 + 推理过程
```

### 运行测试

```bash
python test_agent.py
```

### 预期输出

```
============================================================
AI Trader Agent - 市场扫描
============================================================

[初始化] AI 模型...
[ModelRouter] 阿里云百炼 已配置: glm-4.7
[ModelRouter] 初始化完成，可用模型数: 1

[数据] 扫描市场: 5 只股票 (总共 1221 只，限制 5 只)
   000001: ¥10.94 (+0.00%)
   000002: ¥4.04 (-1.94%)
   000004: ¥5.10 (-0.20%)
   000006: ¥8.75 (+3.31%)
   000037: ¥13.20 (+10.01%)

[账户] 现金: ¥1,000,000.00

[AI] 分析中...

============================================================
决策结果
============================================================

状态: 成功

动作: WAIT
股票: None
置信度: 0.85

推理:
  市场处于横盘状态（sideways），虽然指数上涨且半导体、通信等行业资金大幅流入，
  但扫描的5只个股整体质量较差。

  所有股票的基本面评分均为40/100（ROE数据缺失，成长性不足），
  且大多处于下跌趋势或底部震荡中，缺乏明确的领涨信号。

  000006虽然涨幅较好且评分相对较高，但技术面评分仅40分，且存在'bear'风险提示。
  在最大仓位30%的限制下，为了资金安全，应等待更强势的标的或更好的入场时机。

执行时间: 2.15秒
============================================================
```

**评分系统工作示例**:

| 股票 | 总分 | 技术 | 基本 | 资金 | 信号 | AI 决策 |
|------|------|------|------|------|------|----------|
| 000006 | 75 | 70 | 80 | 72 | BUY | 考虑买入 |
| 000001 | 49 | 45 | 40 | 65 | HOLD | 评分过低 |
| 000037 | 82 | 85 | 75 | 88 | STRONG_BUY | 强势但已涨停 |
| 000002 | 35 | 30 | 40 | 35 | SELL | 趋势偏弱 |

**P7 拦截示例**:
```
AI 决策买入 000999 (评分 25 分)
  → PolicyEngine 检查
  → P7 ScoreThresholdPolicy: 拦截
  → 拒绝原因: "评分过低: 25 分 < 最低 30 分（可能存在严重风险）"
```

### 测试脚本说明

| 功能 | 描述 |
|------|------|
| **数据来源** | 本地 K 线文件 (`data/klines_600519.csv`) |
| **AI 模型** | 阿里云百炼 GLM-4.7 |
| **测试股票** | 贵州茅台 (600519) |
| **测试场景** | 空仓状态下的买入/等待决策 |
| **执行时间** | 约 25-40 秒（取决于模型响应速度） |

### 故障排查

如果测试失败，请检查：

1. **环境变量配置**
   ```bash
   # 确认阿里云百炼配置
   echo $ANTHROPIC_AUTH_TOKEN
   echo $ANTHROPIC_BASE_URL
   ```

2. **数据文件存在**
   ```bash
   # 确认 K 线数据文件存在
   ls -la data/klines_600519.csv
   ```

3. **模型连接**
   ```bash
   # 运行配置验证
   python verify_config.py
   ```

---

## 配置验证

### 验证脚本

运行验证脚本确认配置是否正常：

```bash
python verify_config.py
```

### 预期输出

```
============================================================
AI Trader Agent 模型配置验证
============================================================

[1] 环境变量配置
----------------------------------------
ANTHROPIC_AUTH_TOKEN: sk-sp-xxx (20 字符)
ANTHROPIC_BASE_URL: https://coding.dashscope.aliyuncs.com/apps/anthropic
ANTHROPIC_MODEL: glm-4.7

[2] 测试 API 调用
----------------------------------------
状态: 成功
模型回复: 我是GLM大语言模型...
使用的模型: glm-4.7
Token 使用: 60

[3] 配置总结
============================================================
实际使用的配置:
  API 提供商: 阿里云百炼 (DashScope)
  模型: GLM-4.7
  接口: Anthropic 兼容接口
  Base URL: https://coding.dashscope.aliyuncs.com/apps/anthropic
  状态: 正常工作

结论: 模型配置正常，可以正常使用
============================================================
```

---

## 系统架构

AI Trader Agent 采用 **混合评分决策架构**，结合 AI 智能与量化评分：

```
┌─────────────────────────────────────────────────────────────────┐
│                        数据采集层                                │
│  LocalDataLoader → 1221只股票 K线数据 + 技术指标               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      评分计算层 (新增)                             │
│  ComprehensiveScoringSystem                                     │
│  ├─ 技术面 (35%): 趋势、乖离、量能、MACD、RSI                    │
│  ├─ 基本面 (35%): ROE、成长性、估值、质量                        │
│  └─ 资金面 (30%): 主力流入、净流入、融资融券                       │
│  输出: 0-100分 + 买入信号 + 理由 + 风险                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       AI 决策层 (ReAct)                            │
│  AgentLoop.react_loop()                                         │
│  ├─ Observe: 生存等级、市场状态                                   │
│  ├─ Think: AI 分析 (参考评分)                                    │
│  ├─ Act: 执行工具                                               │
│  └─ Reflect: 更新记忆                                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      风控验证层 (7层)                              │
│  PolicyEngine.validate_order()                                  │
│  P0: 资金检查  P1: 熔断  P2: 黑名单  P3: 交易规则                │
│  P4: 仓位限制  P5: 冷却  P6: 单日限额                             │
│  P7: 评分拦截 (<30分拒绝) ← 新增安全网                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        执行撮合层                                 │
│  Matcher → Account (SQLite 持久化)                              │
└─────────────────────────────────────────────────────────────────┘
```

### 评分系统说明

| 模块 | 功能 |
|------|------|
| **技术面评分** | 趋势(30) + 乖离(20) + 量能(15) + 支撑(10) + MACD(15) + RSI(10) |
| **基本面评分** | ROE + 成长性 + 估值 + 质量 |
| **资金面评分** | 主力流入 + 净流入 + 融资融券 |
| **综合评分** | 技术(35%) + 基本(35%) + 资金(30%) = 0-100分 |

### 决策流程

```
数据 → 评分计算 → AI参考评分 → 决策 → 7层风控 → 执行
                ↑                           ↓
           评分辅助决策              P7极低分拦截
```

---

## AI Agent 决策流程

AI Agent 不是简单执行大模型的决策，而是通过完整的多层处理机制来确保交易安全。

### 完整决策链路

```
用户输入
    "分析扫描的股票并给出交易建议"
    ↓
┌─────────────────────────────────────────────────────────┐
│ 阶段 1: 数据加载 + 评分计算 (新增)                        │
│   LocalDataLoader.load_all_stocks()                      │
│   ├─ 加载 1221 只股票 K线数据                             │
│   └─ ComprehensiveScoringSystem.score()                   │
│       ├─ 技术面评分: 趋势、MACD、RSI...                   │
│       ├─ 基本面评分: ROE、成长性、估值                     │
│       └─ 资金面评分: 主力流入、净流入                       │
│   输出: 每只股票 0-100分 + 理由 + 风险                    │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│ 阶段 2: 构建上下文 (Observe)                              │
│   AgentContext 构建:                                     │
│   - 账户状态 (资金、回撤、生存等级)                        │
│   - 持仓信息                                             │
│   - 市场状态 (震荡市 sideways)                            │
│   - 股票评分 (新增)                                        │
│   - 用户指令                                              │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│ 阶段 3: AI 分析 (Think) - 评分辅助决策                    │
│   ModelRouter → 阿里云百炼 GLM-4.7                         │
│                                                          │
│   发送数据 (包含评分):                                    │
│   {                                                      │
│     "stocks": [                                          │
│       {                                                  │
│         "symbol": "000001",                              │
│         "price": 10.94,                                  │
│         "score": {  ← 新增                                │
│           "total_score": 75,                              │
│           "buy_signal": "BUY",                            │
│           "technical_score": 70,                          │
│           "fundamental_score": 80,                        │
│           "reasons": ["多头排列", "主力流入"],             │
│           "risk_factors": ["乖离率偏高"]                   │
│         }                                                │
│       }                                                  │
│     ]                                                   │
│   }                                                      │
│                                                          │
│   AI 推理示例 (参考评分):                                 │
│   "000001评分75分，技术面强势，主力流入5%，建议买入"       │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│ 阶段 4: ReAct 循环 (Act + Reflect)                       │
│   if is_final == false:                                  │
│     - 执行工具 (get_quote, get_positions)                │
│     - 收集结果                                           │
│     - 更新上下文                                         │
│     - 回到 Think (重新调用模型)                          │
│   else:                                                 │
│     - 进入风控检查                                       │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│ 阶段 5: 风控引擎 (7层优先级检查)                         │
│   PolicyEngine.validate_order():                        │
│                                                          │
│   P0 资金检查:     ✓ 买入金额 < 可用资金                  │
│   P1 熔断机制:     ✓ 单日亏损 < 5%                        │
│   P2 黑名单:       ✓ 非ST股                              │
│   P3 交易规则:     ✓ 时间在 9:30-15:00                   │
│   P4 仓位限制:     ✓ 订单 < 30% 总资产                    │
│   P5 冷却机制:     ✓ 无近期反向交易                      │
│   P6 单日限额:     ✓ 今日 < 10 笔                        │
│   P7 评分拦截:     ✓ 评分 >= 30分 (新增安全网)             │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│ 阶段 6: 执行交易                                        │
│   Matcher.match_order():                                │
│   - 订单撮合成功                                         │
│   - 账户资金更新                                         │
│   - 持仓记录更新                                         │
└─────────────────────────────────────────────────────────┘
```

### 各阶段数据流

| 阶段 | 处理组件 | 输入数据 | 输出数据 |
|------|----------|----------|----------|
| 1. 数据+评分 | LocalDataLoader + ScoringSystem | K线数据 | 股票数据 + 评分 |
| 2. 构建上下文 | AgentContext | 用户指令、账户状态、评分 | AgentContext 对象 |
| 3. AI 分析 | ModelRouter | AgentContext + 评分信息 | 决策 JSON |
| 4. ReAct 循环 | AgentLoop | 决策 JSON | 工具调用 / 最终决策 |
| 5. 风控引擎 | PolicyEngine | 订单对象 + 评分 | 风控结果 (通过/拒绝) |
| 6. 执行交易 | Matcher | 订单对象 | 撮合结果 |

### 核心组件职责

| 组件 | 文件 | 职责 |
|------|------|------|
| **LocalDataLoader** | [tools/data/local_data_loader.py](tools/data/local_data_loader.py) | 加载 1221 只股票数据 |
| **ComprehensiveScoringSystem** | [core/comprehensive_scoring.py](core/comprehensive_scoring.py) | 综合评分计算 (技术+基本+资金) |
| **AgentContext** | [core/schemas.py](core/schemas.py) | 构建上下文 (账户、持仓、市场、评分) |
| **ModelRouter** | [core/model_router.py](core/model_router.py) | 路由到阿里云百炼/本地模型 |
| **AgentLoop** | [core/agent_loop.py](core/agent_loop.py) | ReAct 循环控制 + 评分计算 |
| **PolicyEngine** | [core/policy_engine.py](core/policy_engine.py) | 7层风控 (含 P7 评分拦截) |
| **PlaceOrderTool** | [tools/trading/place_order.py](tools/trading/place_order.py) | 下单工具 + 风控验证 |
| **Matcher** | [simulation/matcher.py](simulation/matcher.py) | 订单撮合引擎 |
| **Account** | [simulation/account.py](simulation/account.py) | 账户管理 (SQLite 持久化) |
| **SurvivalRules** | [core/survival_rules.py](core/survival_rules.py) | 生存等级管理 |

### 可视化演示

运行以下脚本查看完整流程演示：

```bash
# 查看完整决策流程
python show_full_pipeline.py

# 查看与大模型的数据交互
python show_data_exchange.py

# 验证模型配置
python verify_config.py
```

### 常见问题

**Q: API 调用失败怎么办？**

```bash
# 1. 检查环境变量
echo $ANTHROPIC_BASE_URL

# 2. 检查 .env 文件
cat .env | grep ZHIPU_API_KEY

# 3. 重新验证
python verify_config.py
```

**Q: 如何更换 API Key？**

1. 访问 https://open.bigmodel.cn/
2. 创建新的 API Key
3. 运行 `python update_api_key.py` 更新配置

**Q: 支持哪些模型？**

- 智谱 GLM-4-Flash (默认)
- 智谱 GLM-4-Air
- 智谱 GLM-4-Plus
- 其他兼容 Anthropic 接口的模型

---

## 项目结构

```
ai-trader-agent/
├── api/                   # FastAPI 后端
│   ├── app.py            # FastAPI 应用入口
│   └── v1/
│       ├── endpoints/    # API 端点
│       │   ├── market.py      # 行情数据
│       │   ├── trading.py     # 交易相关
│       │   ├── analysis.py    # 股票分析
│       │   ├── strategy.py    # 策略管理
│       │   ├── system.py      # 系统信息
│       │   └── memory.py      # 交易记忆
│       └── __init__.py    # 路由注册
├── web/                   # React 前端
│   ├── src/
│   │   ├── pages/       # 页面组件
│   │   ├── components/  # UI 组件
│   │   ├── api/         # API 调用
│   │   └── stores/      # 状态管理
│   ├── package.json
│   └── vite.config.ts
├── core/                  # 核心智能体逻辑
│   ├── schemas.py        # Pydantic 数据模型
│   └── ...
├── simulation/            # 模拟交易
│   ├── account.py        # 虚拟账户
│   └── matcher.py        # 撮合引擎
├── src/                   # 策略系统
│   ├── strategy/         # 策略管理
│   └── config.py         # 配置
├── data/                  # 数据存储
├── tests/                 # 测试套件
├── requirements.txt       # Python 依赖
├── PRD.md                # 产品需求文档
├── architecture.md       # 架构设计
└── tasks.md              # 开发任务
```

---

## API 接口

### 市场行情 `/api/v1/market/`
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/quote/{symbol}` | 获取股票行情 |
| GET | `/quotes` | 批量获取行情 |
| GET | `/klines/{symbol}` | 获取K线数据 |
| GET | `/stocks` | 股票列表 |
| GET | `/stocks/search` | 搜索股票 |

### 交易 `/api/v1/trading/`
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/account` | 账户信息 |
| POST | `/orders` | 下单 |
| GET | `/positions` | 持仓列表 |
| GET | `/trades` | 交易历史 |

### 分析 `/api/v1/analysis/`
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/analyze` | 分析股票 |
| GET | `/history` | 分析历史 |

### 策略 `/api/v1/strategy/`
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/` | 策略列表 |
| POST | `/activate` | 激活策略 |
| POST | `/deactivate-all` | 停用所有 |

---

## 页面功能

| 页面 | 路径 | 功能 |
|------|------|------|
| **首页** | `/` | 快速分析入口、市场概览 |
| **分析页** | `/analysis` | 股票分析、多策略信号 |
| **策略页** | `/strategy` | 策略管理、激活/停用 |
| **设置页** | `/settings` | 系统配置 |

---

## 开发

### 后端开发

```bash
# 运行测试
pytest tests/ -v

# 覆盖率报告
pytest tests/ --cov=core --cov=api --cov-report=html

# 代码格式化
black core/ api/ simulation/

# 类型检查
mypy core/
```

### 前端开发

```bash
cd web

# 开发模式
npm run dev

# 构建生产版本
npm run build

# 预览构建结果
npm run preview

# 代码检查
npm run lint
```

---

## 数据说明

### 数据来源

项目使用 **finshare** 库下载A股市场数据。

### 数据目录结构

```
data/
├── stocks/                    # 原始K线数据（按股票为单位）
│   ├── 000001_SZ.csv         # 平安银行 K线数据
│   ├── 000002_SZ.csv         # 万科 A K线数据
│   └── ...
├── by_stock/                  # 拆分后数据（按股票-日期）
│   ├── 000001_SZ/            # 平安银行目录
│   │   ├── 000001_SZ_2011-04-01.csv
│   │   ├── 000001_SZ_2011-04-06.csv
│   │   └── ...              # 每天一个文件（共3620个交易日）
│   ├── 000002_SZ/
│   └── ...
├── financial/                 # 财务数据
│   ├── balance_000001_SZ.csv # 资产负债表
│   ├── income_000001_SZ.csv  # 利润表
│   ├── cashflow_000001_SZ.csv # 现金流量表
│   ├── indicator_000001_SZ.csv # 财务指标
│   └── dividend_000001_SZ.csv # 分红数据
├── market/                    # 市场数据
│   ├── index_000001_SH.csv   # 上证指数
│   ├── index_399001_SZ.csv   # 深证成指
│   ├── index_399006_SZ.csv   # 创业板指
│   └── industries/           # 行业数据
├── lhb/                       # 龙虎榜数据
├── valuation/                 # 市场估值数据
├── spot/                      # 实时行情数据
├── futures/                   # 股指期货数据
├── funds/                     # 基金数据
└── etfs/                      # ETF数据
```

### 数据统计

| 数据类型 | 数量 | 说明 |
|----------|------|------|
| **股票数量** | 5,136只 | 全A股市场 |
| **历史时长** | 15年 | 2011-04-01 至 2026-03-27 |
| **交易日数** | 约3,600天 | 去除节假日和周末 |
| **K线文件数** | 5,136个 | 按股票单位 |
| **拆分文件数** | 1,135万+ | 按股票-日期 |
| **财务数据** | 6类/股 | 资产负债表、利润表等 |

### 数据字段

**K线数据字段**：
- `code` - 股票代码
- `date` - 交易日期
- `open` - 开盘价
- `high` - 最高价
- `low` - 最低价
- `close` - 收盘价
- `volume` - 成交量
- `amount` - 成交金额
- `turnover_rate` - 换手率

### 数据下载与转换

**下载全部数据**：
```bash
# 下载K线 + 财务 + 资金流向 + 融资融券 + 市场数据
python scripts/download_all_stocks_finshare.py --days 5475 --all-data
```

**转换数据格式**：
```bash
# 将按股票的数据转换为按股票-日期的格式
python scripts/convert_to_daily.py
```

### 数据使用示例

**加载单只股票K线**：
```python
import pandas as pd
df = pd.read_csv('data/stocks/000001_SZ.csv')
```

**加载指定日期的单股票数据**：
```python
import pandas as pd
df = pd.read_csv('data/by_stock/000001_SZ/000001_SZ_2026-03-27.csv')
```

---

## 开发状态

### ✅ 已完成

| 模块 | 状态 | 说明 |
|------|------|------|
| FastAPI 后端 | ✅ | RESTful API 完整实现 |
| React 前端 | ✅ | 4个页面完整实现 |
| 虚拟账户系统 | ✅ | 交易、持仓、历史记录 |
| 策略系统 | ✅ | 多策略分析、激活管理 |
| 行情数据 | ✅ | 报价、K线、股票列表 |
| 评分系统 | ✅ | 技术+基本+资金面综合评分 |
| AI 智能体 | ✅ | ReAct Loop + 评分辅助决策 |
| 风控引擎 | ✅ | 7层风控 (含 P7 评分拦截) |
| 市场感知 | ✅ | 牛熊市判断 |

### 🚧 开发中

| 模块 | 状态 | 说明 |
|------|------|------|
| 反思机制 | 🚧 | 记忆学习与策略优化 |
| 实盘接口 | 🚧 | 券商 API 对接 |

### 📋 待开发

| 模块 | 优先级 | 说明 |
|------|--------|------|
| 撤单功能 | P1 | 订单挂单与撤单 |
| 实时数据推送 | P1 | WebSocket 推送 |
| 财务数据 API | P2 | 基本面分析数据 |

---

## 文档

- [PRD](./PRD.md) - 产品需求文档
- [架构设计](./architecture.md) - 技术架构
- [任务清单](./tasks.md) - 开发任务
- [API 文档](./docs/api.md) - API 接口文档（待补充）

---

## 许可证

MIT License

---

## 免责声明

本项目仅用于模拟交易和学习研究，不构成任何投资建议。实盘交易有风险，投资需谨慎。
