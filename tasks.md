# AI Trader Agent - 任务清单

> **项目**: ai-trader-agent
> **阶段**: Phase 1 - 核心框架
> **创建日期**: 2024-03-23
> **基于**: [PRD v1.2](./PRD.md) | [architecture.md](./architecture.md)

---

## 📋 任务概览

| 状态 | 数量 | 说明 |
|------|------|------|
| 🔄 待开始 | 12 | 等待执行 |
| ✅ 已完成 | 0 | - |
| ⏸️ 阻塞 | 0 | - |
| 🎯 总计 | 12 | 预计 ~21.5 小时 |

---

## 🗂️ Phase 1 任务列表

### T1: 项目初始化

**ID**: `P1-T001`
**优先级**: P0 (阻塞所有其他任务)
**预估**: 0.5小时
**状态**: 🔄 待开始

**描述**:
创建项目目录结构，初始化Python虚拟环境，配置开发工具

**验收标准**:
- [ ] 目录结构符合 architecture.md 定义
- [ ] Python 3.10+ 虚拟环境创建完成
- [ ] requirements.txt 安装无错误
- [ ] .gitignore 配置正确
- [ ] .env.example 文件创建

**输出**:
```
ai-trader-agent/
├── core/
├── tools/
├── simulation/
├── utils/
├── config/
├── tests/
├── data/
├── logs/
├── .env.example
├── requirements.txt
├── .gitignore
└── README.md
```

**依赖**: 无
**相关文件**: - [ ] 创建目录脚本
**参考**: [architecture.md#6.3 目录结构](./architecture.md#63-目录结构)

---

### T2: 核心数据模型 (schemas.py)

**ID**: `P1-T002`
**优先级**: P0
**预估**: 1小时
**状态**: 🔄 待开始

**描述**:
使用 Pydantic 定义所有核心数据模型，确保类型安全和数据验证

**验收标准**:
- [ ] QuoteData: 行情数据模型
- [ ] Order: 订单模型
- [ ] Position: 持仓模型
- [ ] Trade: 交易记录模型
- [ ] AgentResponse: Agent响应模型
- [ ] AgentContext: Agent上下文模型
- [ ] Decision: 决策模型
- [ ] PolicyResult: 风控结果模型
- [ ] 所有模型有完整的类型提示和描述
- [ ] 通过 pytest 数据验证测试

**文件**: `core/schemas.py`

**依赖**: T1
**测试**: `tests/test_schemas.py`

**代码框架**:
```python
# core/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import IntEnum

class QuoteData(BaseModel):
    """行情数据"""
    symbol: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    price: float = Field(..., gt=0, description="最新价")
    change: float = Field(..., ge=-11, le=11, description="涨跌幅(%)")
    # ... 其他字段

class Order(BaseModel):
    """订单"""
    order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int = Field(..., gt=0, multiple_of=100)
    # ... 其他字段
```

---

### T3: 双模型路由器 (model_router.py)

**ID**: `P1-T003`
**优先级**: P0
**预估**: 2小时
**状态**: 🔄 待开始

**描述**:
实现智能模型路由，支持API模型和本地模型融合，含Token预算控制

**验收标准**:
- [ ] 根据生存等级选择模型策略
- [ ] Token预算统计和限制
- [ ] 融合决策逻辑（API + 本地）
- [ ] 置信度计算和阈值判断
- [ ] 降级模式（预算耗尽/危急状态）
- [ ] 完整的错误处理
- [ ] 单元测试覆盖率 ≥ 80%

**文件**: `core/model_router.py`

**依赖**: T2 (schemas.py)
**测试**: `tests/test_model_router.py`

**关键接口**:
```python
class ModelRouter:
    async def generate_decision(self, context: AgentContext) -> Decision:
        """
        根据生存等级路由到不同模型

        normal: 融合双模型
        low_compute/critical: 仅本地模型
        dead: 抛出异常
        """
```

**Token预算分配**:
```python
TOKEN_BUDGET = {
    "system": 2000,
    "working_memory": 10000,
    "episodic": 30000,
    "semantic": 20000,
    "market_data": 50000,
    "output": 10000,
    "buffer": 78000,
}
```

---

### T4: 生存等级系统 (survival_rules.py)

**ID**: `P1-T004`
**优先级**: P0
**预估**: 1.5小时
**状态**: 🔄 待开始

**描述**:
实现4级生存等级状态机，支持自动切换和恢复验证

**验收标准**:
- [ ] 4个等级定义：normal, low_compute, critical, dead
- [ ] 回撤率计算（基于初始资金）
- [ ] 状态切换逻辑（立即升级，延迟恢复）
- [ ] 等级配置：最大仓位、交易频率
- [ ] 持续时间验证（恢复条件）
- [ ] 状态持久化
- [ ] 单元测试（含时间模拟）

**文件**: `core/survival_rules.py`

**依赖**: T2 (schemas.py)
**测试**: `tests/test_survival_rules.py`

**状态机**:
```python
class SurvivalLevel(Enum):
    NORMAL = "normal"          # <10% 回撤
    LOW_COMPUTE = "low_compute" # 10-20% 回撤
    CRITICAL = "critical"       # 20-30% 回撤
    DEAD = "dead"              # >30% 回撤

LEVEL_CONFIG = {
    SurvivalLevel.NORMAL: {"max_position": 0.30, "trading_interval": 60},
    SurvivalLevel.LOW_COMPUTE: {"max_position": 0.20, "trading_interval": 300},
    SurvivalLevel.CRITICAL: {"max_position": 0.10, "trading_interval": 600},
    SurvivalLevel.DEAD: {"max_position": 0.0, "trading_interval": 0},
}
```

**测试场景**:
- [ ] 回撤从8% → 12%: 立即切换到 low_compute
- [ ] 回撤从12% → 8%: 维持5分钟后恢复 normal
- [ ] 回撤≥30%: 立即停止，标记 dead
- [ ] 手动重启: 从 low_compute 开始

---

### T5: 风控引擎 (policy_engine.py)

**ID**: `P1-T005`
**优先级**: P0
**预估**: 2小时
**状态**: 🔄 待开始

**描述**:
实现7条风控规则，按优先级顺序执行，含异常场景处理

**验收标准**:
- [ ] P0: 资金检查（买入金额 < 可用资金）
- [ ] P1: 熔断机制（单日亏损>5%暂停1小时）
- [ ] P2: 黑名单（ST股禁止买入）
- [ ] P3: 交易时间（9:30-15:00）
- [ ] P3: 涨跌停处理（涨停禁止买、跌停禁止卖）
- [ ] P3: 停牌处理（禁止交易）
- [ ] P4: 仓位限制（单只股票≤30%）
- [ ] P5: 冷却机制（30分钟反向限制）
- [ ] P6: 单日限额（≤10笔交易）
- [ ] 按优先级顺序执行
- [ ] 风控拒绝有明确原因
- [ ] 完整单元测试

**文件**: `core/policy_engine.py`

**依赖**: T2 (schemas.py), T4 (survival_rules.py)
**测试**: `tests/test_policy_engine.py`

**优先级枚举**:
```python
class PolicyPriority(IntEnum):
    P0_FUND_CHECK = 0
    P1_CIRCUIT_BREAKER = 1
    P2_BLACKLIST = 2
    P3_TRADING_RULES = 3
    P4_POSITION_LIMIT = 4
    P5_COOLDOWN = 5
    P6_DAILY_LIMIT = 6
```

**测试用例**:
```python
def test_p0_fund_insufficient():
    """资金不足，P0拒绝"""
    order = Order(symbol="600519", side="buy", quantity=1000, price=2000)
    account.cash = 1000000  # 100万
    # 1000股 × 2000元 = 200万 > 100万，应该拒绝

def test_p3_limit_up_buy():
    """涨停买入，P3拒绝"""
    order = Order(symbol="600519", side="buy", quantity=100, price=1690)
    quote = QuoteData(symbol="600519", price=1685, upper_limit=1680)
    # 委托价1690 > 涨停价1680，应该拒绝
```

---

### T6: 市场状态感知 (market_regime.py)

**ID**: `P1-T006`
**优先级**: P1
**预估**: 1.5小时
**状态**: 🔄 待开始

**描述**:
检测大盘市场状态（牛市/熊市/震荡），调整仓位上限

**验收标准**:
- [ ] 获取上证指数数据
- [ ] 计算均线排列（MA5/MA10/MA20/MA60）
- [ ] 判断市场状态
- [ ] 计算置信度
- [ ] 设置仓位上限
- [ ] 单元测试

**文件**: `core/market_regime.py`

**依赖**: T2 (schemas.py)
**测试**: `tests/test_market_regime.py`

**判断逻辑**:
```python
def detect(self, market_data: MarketData) -> MarketState:
    """
    牛市: MA5 > MA10 > MA20 > MA60 且涨跌家数比>1.5
    熊市: MA5 < MA10 < MA20 < MA60 或涨跌家数比<0.67
    震荡: 其他情况
    """
```

---

### T7: 反思机制 (reflection.py)

**ID**: `P1-T007`
**优先级**: P1
**预估**: 1.5小时
**状态**: 🔄 待开始

**描述**:
对亏损交易进行反思分析，生成改进建议

**验收标准**:
- [ ] 亏损离场触发反思（收益率 < -2%）
- [ ] 提取决策链路
- [ ] 分类错误类型（entry/exit/position/timing）
- [ ] 生成反思内容
- [ ] 存储到记忆系统
- [ ] 单元测试

**文件**: `core/reflection.py`

**依赖**: T2 (schemas.py)
**测试**: `tests/test_reflection.py`

**错误分类**:
```python
def _classify_error(self, chain: DecisionChain, trade: Trade) -> str:
    """
    entry: 入场时机错误（2小时内亏损>5%）
    timing: 追高（入场价 > 最高价×0.95）
    position: 仓位过重（持仓比例>20%）
    exit: 出场决策错误（其他情况）
    """
```

---

### T8: Agent循环 (agent_loop.py)

**ID**: `P1-T008`
**优先级**: P0
**预估**: 2小时
**状态**: 🔄 待开始

**描述**:
实现ReAct循环核心逻辑，协调各模块完成决策

**验收标准**:
- [ ] Observe: 获取当前状态（持仓、行情、记忆）
- [ ] Think: 调用模型生成决策
- [ ] Act: 执行工具调用
- [ ] Reflect: 更新记忆和状态
- [ ] 循环控制（最大迭代次数）
- [ ] 完整日志记录
- [ ] 单元测试

**文件**: `core/agent_loop.py`

**依赖**: T2, T3, T5, T8 (tool_executor)
**测试**: `tests/test_agent_loop.py`

**循环逻辑**:
```python
async def react_loop(self, user_input: str) -> AgentResponse:
    """
    1. 构建上下文（持仓+行情+记忆+风控规则）
    2. 调用 ModelRouter.generate_decision()
    3. 执行工具调用（ToolExecutor）
    4. 更新记忆和状态
    5. 判断是否需要继续
    6. 返回最终响应
    """
```

---

### T9: 工具执行器 + 3个核心工具

**ID**: `P1-T009`
**优先级**: P0
**预估**: 2小时
**状态**: 🔄 待开始

**描述**:
实现工具执行器和3个核心工具（get_quote, place_order, get_positions）

**验收标准**:
- [ ] ToolExecutor: 工具注册、参数校验、执行调度
- [ ] GetQuoteTool: 获取股票实时行情
- [ ] PlaceOrderTool: 下单（含风控检查）
- [ ] GetPositionsTool: 查询持仓
- [ ] 错误处理和日志
- [ ] 单元测试

**文件**:
- `core/tool_executor.py`
- `tools/data/get_quote.py`
- `tools/trading/place_order.py`
- `tools/trading/get_positions.py`

**依赖**: T2, T5 (policy_engine)
**测试**: `tests/test_tools.py`

**工具接口**:
```python
class Tool(ABC, Generic[T]):
    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def parameters_schema(self) -> dict: ...

    async def execute(self, **kwargs) -> ToolResult[T]: ...
```

---

### T10: 模拟账户系统 (account.py)

**ID**: `P1-T010`
**优先级**: P0
**预估**: 2小时
**状态**: 🔄 待开始

**描述**:
实现虚拟账户管理，含原子性保证和撮合逻辑

**验收标准**:
- [ ] 初始资金100万
- [ ] 买入/卖出操作（原子性）
- [ ] 手续费计算（佣金+印花税+滑点）
- [ ] 持仓市值实时计算
- [ ] 持仓数据持久化（SQLite）
- [ ] 事务回滚测试
- [ ] 单元测试

**文件**: `simulation/account.py`

**依赖**: T2 (schemas.py)
**测试**: `tests/test_account.py`

**原子性保证**:
```python
@contextmanager
def _transaction(self):
    """SQLite事务上下文管理器"""
    cursor = self.db.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        yield cursor
        self.db.commit()
    except Exception:
        self.db.rollback()
        raise

def update_from_trade(self, match_result: MatchResult) -> bool:
    """从交易结果更新账户（原子操作）"""
    with self._transaction() as cursor:
        # 扣款/加款 + 加持仓/减持仓
        # 任何失败都会回滚
```

**手续费计算**:
```python
def calculate_commission(self, amount: float, side: str) -> float:
    """
    佣金: max(amount × 0.0003, 5)
    印花税: amount × 0.001 (仅卖出)
    滑点: amount × 0.0005
    """
```

---

### T11: 撮合引擎 (matcher.py)

**ID**: `P1-T011`
**优先级**: P1
**预估**: 1.5小时
**状态**: 🔄 待开始

**描述**:
模拟订单撮合逻辑，处理涨跌停和停牌

**验收标准**:
- [ ] 市价单撮合（以当前价成交）
- [ ] 限价单撮合（以限价或更优价格成交）
- [ ] 涨停买入拒绝
- [ ] 跌停卖出拒绝
- [ ] 停牌拒绝交易
- [ ] T+1规则（当日买入次日才能卖）
- [ ] 单元测试

**文件**: `simulation/matcher.py`

**依赖**: T2 (schemas.py)
**测试**: `tests/test_matcher.py`

**撮合逻辑**:
```python
async def match(self, order: Order) -> MatchResult:
    """
    1. 获取实时行情
    2. 检查涨跌停限制
    3. 检查停牌状态
    4. 检查T+1规则
    5. 确定成交价格
    6. 计算成交数量
    7. 返回撮合结果
    """
```

---

### T12: 数据更新脚本 (update_data.py)

**ID**: `P1-T012`
**优先级**: P0
**预估**: 1小时
**状态**: 🔄 待开始

**描述**:
创建数据更新脚本，获取前一日真实数据

**验收标准**:
- [ ] 调用 AkShare 获取日K线数据
- [ ] 支持指定日期参数
- [ ] 自动创建目录结构
- [ ] 保存为 CSV 格式
- [ ] 更新数据索引文件
- [ ] 错误处理和日志
- [ ] 命令行参数解析

**文件**: `scripts/update_data.py`

**依赖**: T1 (项目初始化)
**测试**: 手动测试

**使用方式**:
```bash
# 获取昨日数据
python scripts/update_data.py

# 获取指定日期数据
python scripts/update_data.py --date 2024-03-22

# 获取沪深300成分股
python scripts/update_data.py --index csi300
```

**数据格式**:
```csv
date,symbol,open,high,low,close,volume,amount,turnover
2024-03-22,600519,1680.00,1695.00,1675.00,1690.00,1234567,2100000000.0
```

---

### T13: 单元测试 (≥80% 覆盖率)

**ID**: `P1-T013`
**优先级**: P0
**预估**: 4小时
**状态**: 🔄 待开始

**描述**:
为所有核心模块编写单元测试，确保代码质量

**验收标准**:
- [ ] 测试覆盖率 ≥ 80% (pytest-cov)
- [ ] 所有CRITICAL/HIGH问题修复
- [ ] 代码符合 PEP 8 (flake8)
- [ ] 类型检查通过 (mypy)
- [ ] 测试用例包含边界情况

**文件**:
- `tests/test_schemas.py`
- `tests/test_model_router.py`
- `tests/test_survival_rules.py`
- `tests/test_policy_engine.py`
- `tests/test_market_regime.py`
- `tests/test_reflection.py`
- `tests/test_agent_loop.py`
- `tests/test_tools.py`
- `tests/test_account.py`
- `tests/test_matcher.py`

**依赖**: T2-T12
**命令**:
```bash
# 运行测试
pytest tests/ -v

# 覆盖率报告
pytest tests/ --cov=core --cov=tools --cov=simulation --cov-report=html

# 代码风格检查
flake8 core/ tools/ simulation/

# 类型检查
mypy core/
```

**测试夹具** (`tests/conftest.py`):
```python
@pytest.fixture
def mock_account():
    """模拟账户"""
    account = Account(initial_cash=1000000, db_path=":memory:")
    return account

@pytest.fixture
def sample_quote():
    """示例行情数据"""
    return QuoteData(
        symbol="600519",
        name="贵州茅台",
        price=1680.00,
        change=1.2,
        volume=1234567,
        amount=2100000000.0
    )
```

---

### T14: 集成测试

**ID**: `P1-T014`
**优先级**: P1
**预估**: 2小时
**状态**: 🔄 待开始

**描述**:
端到端集成测试，验证完整交易流程

**验收标准**:
- [ ] 完整交易流程测试
- [ ] 风控拒绝场景测试
- [ ] 生存等级切换测试
- [ ] 数据加载测试
- [ ] 错误恢复测试

**文件**: `tests/test_integration.py`

**依赖**: T13 (单元测试全部通过)

**测试场景**:
```python
async def test_buy_order_full_flow():
    """
    完整买入流程:
    1. Agent接收"买入1000股茅台"
    2. 获取实时行情
    3. 风控检查通过
    4. 撮合成交
    5. 更新账户（原子性）
    6. 记录交易
    7. 返回结果
    """

async def test_survival_level_upgrade():
    """
    生存等级升级:
    1. 初始状态 normal
    2. 模拟回撤达到12%
    3. 验证切换到 low_compute
    4. 验证交易频率降低
    5. 验证最大仓位降低
    """
```

---

## 📊 任务依赖图

```
T1 (项目初始化)
 ├── T2 (schemas.py)
 │    ├── T3 (model_router.py)
 │    ├── T4 (survival_rules.py)
 │    │    └── T5 (policy_engine.py)
 │    ├── T6 (market_regime.py)
 │    ├── T7 (reflection.py)
 │    └── T10 (account.py)
 │         └── T11 (matcher.py)
 ├── T8 (agent_loop.py) ──┐
 │    └── T3, T5           │
 ├── T9 (工具)             │
 │    └── T2, T5           │
 └── T12 (数据脚本)        │
                           │
T13 (单元测试) ←───────────┘
    └── T2-T12
    └── T14 (集成测试)
```

---

## 🎯 Phase 1 验收清单

### 功能验收

- [ ] **F1**: 输入"买入1000股贵州茅台（600519）"，Agent在3秒内完成全流程
- [ ] **F2**: 成交价格符合滑点规则（±0.05%）
- [ ] **F3**: 手续费计算准确（佣金≥5元或万三，印花税千一）
- [ ] **F4**: 持仓市值实时更新
- [ ] **F5**: 回撤10%/20%/30%时5秒内切换生存等级
- [ ] **F6**: 风控规则按优先级正确执行
- [ ] **F7**: 涨跌停场景正确处理
- [ ] **F8**: 能加载前一日真实数据

### 质量验收

- [ ] **Q1**: 单元测试覆盖率 ≥ 80%
- [ ] **Q2**: 所有CRITICAL/HIGH问题已修复
- [ ] **Q3**: 代码符合PEP 8规范
- [ ] **Q4**: 关键函数有类型提示和文档
- [ ] **Q5**: 账户操作满足原子性

### 性能验收

- [ ] **P1**: 决策响应时间 < 3秒
- [ ] **P2**: 内存占用 < 4GB

---

## 📝 开发笔记

### 环境准备

```bash
# 创建虚拟环境
python -3.10 -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt

# 安装开发依赖
pip install pytest pytest-cov flake8 mypy black
```

### requirements.txt

```
# 核心依赖
pydantic>=2.0.0
anthropic>=0.18.0
openai>=1.0.0
akshare>=1.12.0
pandas>=2.0.0
numpy>=1.24.0
redis>=5.0.0

# 开发依赖
pytest>=7.4.0
pytest-cov>=4.1.0
flake8>=6.1.0
mypy>=1.5.0
black>=23.7.0
```

### Git 工作流

```bash
# 创建功能分支
git checkout -b feature/phase1-core

# 提交规范
git commit -m "feat(core): implement schemas.py with Pydantic models"
git commit -m "fix(policy): handle limit up scenario correctly"
git commit -m "test(account): add atomic transaction test"
```

---

## 📅 时间规划

| 周期 | 任务 | 交付物 |
|------|------|--------|
| Day 1 | T1-T4 | 项目结构 + 核心模型 |
| Day 2 | T5-T7 | 风控引擎 + 市场感知 |
| Day 3 | T8-T9 | Agent循环 + 工具 |
| Day 4 | T10-T12 | 账户系统 + 数据脚本 |
| Day 5 | T13-T14 | 测试 + 验收 |

---

**文档状态**: ✅ v1.0 已完成
**下一步**: 开始执行 T1 (项目初始化)
