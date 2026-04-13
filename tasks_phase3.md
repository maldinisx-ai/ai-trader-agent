# AI Trader Agent - Phase 3 任务清单

> **项目**: ai-trader-agent
> **阶段**: Phase 3 - 功能扩展
> **基于**: Phase 1 & 2 完成

---

## 📋 任务概览

| 状态 | 数量 | 说明 |
|------|------|------|
| 🔄 待开始 | 4 | 等待执行 |
| ✅ 已完成 | 0 | - |
| ⏸️ 阻塞 | 0 | - |
| 🎯 总计 | 4 | 预计 ~10 小时 |

---

## 🗂️ Phase 3 任务列表

### T15: 主程序入口 (CLI)

**ID**: `P3-T001`
**优先级**: P0
**预估**: 2小时
**状态**: 🔄 待开始

**描述**:
创建统一的 CLI 入口，启动 Agent 循环和交易系统。

**验收标准**:
- [ ] CLI 参数解析 (交易模式/回测模式/演示模式)
- [ ] 配置文件加载 (.env + config.yaml)
- [ ] 数据库初始化
- [ ] 主循环启动 (定时执行或实时交互)
- [ ] 优雅退出处理 (信号捕获、状态保存)
- [ ] 日志配置 (控制台 + 文件)

**文件**:
- `src/main.py` - 主程序入口
- `config/config.yaml` - 配置文件
- `src/cli.py` - CLI 解析

**依赖**: T1-T14

**使用示例**:
```bash
# 交易模式（实盘）
python main.py --mode trade --symbol 600519

# 回测模式
python main.py --mode backtest --start 2024-01-01 --end 2024-03-24

# 演示模式（模拟）
python main.py --mode demo
```

---

### T16: 实盘数据对接

**ID**: `P3-T002`
**优先级**: P0
**预估**: 3小时
**状态**: 🔄 待开始

**描述**:
接入真实行情数据源，替换模拟数据。

**验收标准**:
- [ ] AkShare 实时行情获取
- [ ] 多股票批量行情
- [ ] K 线数据获取 (日K/周K)
- [ ] 数据缓存机制 (避免频繁请求)
- [ ] 请求限流控制
- [ ] 数据异常处理

**文件**:
- `tools/data/real_quote.py` - 真实行情工具
- `src/data_manager.py` - 数据管理器

**依赖**: T9 (工具系统), T12 (数据脚本)

**API 参考**:
```python
# AkShare 实时行情
ak.stock_zh_a_spot_em()  # 沪深A股实时行情
ak.stock_zh_a_hist()     # 历史K线
```

---

### T17: 监控面板

**ID**: `P3-T003`
**优先级**: P1
**预估**: 3小时
**状态**: 🔄 待开始

**描述**:
创建 Web 监控面板，实时展示交易状态。

**验收标准**:
- [ ] 账户总览 (现金、持仓、盈亏)
- [ ] 持仓列表 (股票、成本、市值、盈亏)
- [ ] 交易历史 (最新N笔交易)
- [ ] 生存状态 (当前等级、回撤)
- [ ] 决策日志 (Agent 思考过程)
- [ ] 实时图表 (净值曲线)

**文件**:
- `monitoring/app.py` - Flask/FastAPI 应用
- `monitoring/templates/index.html` - 前端模板
- `monitoring/static/` - 静态资源

**依赖**: T10 (account.py), T15 (主程序)

**技术选型**:
- 后端: FastAPI
- 前端: HTML + Chart.js (轻量级)

**页面示例**:
```html
<!-- 账户总览 -->
<div class="card">
  <h3>账户总览</h3>
  <p>现金: ¥<span id="cash">...</span></p>
  <p>持仓: ¥<span id="position">...</span></p>
  <p>总资产: ¥<span id="total">...</span></p>
  <p>盈亏: <span id="pnl" class="profit">...</span></p>
</div>
```

---

### T18: 记忆系统

**ID**: `P3-T004`
**优先级**: P1
**预估**: 2小时
**状态**: 🔄 待开始

**描述**:
持久化交易历史和反思记录，支持智能体学习。

**验收标准**:
- [ ] 交易历史存储 (SQLite/PostgreSQL)
- [ ] 反思记录存储
- [ ] 决策链路保存
- [ ] 历史查询 API
- [ ] 经验总结功能
- [ ] 持久化配置

**文件**:
- `core/memory/trade_history.py` - 交易历史
- `core/memory/reflection_store.py` - 反思存储
- `core/memory/query_engine.py` - 查询引擎

**依赖**: T7 (reflection.py), T10 (account.py)

**数据结构**:
```sql
CREATE TABLE trade_history (
    trade_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    shares INTEGER,
    price REAL,
    amount REAL,
    pnl REAL,
    survival_level TEXT,
    decision_chain JSON,
    timestamp TEXT
);

CREATE TABLE reflections (
    reflection_id TEXT PRIMARY KEY,
    trade_id TEXT,
    error_type TEXT,
    analysis TEXT,
    lesson TEXT,
    timestamp TEXT
);
```

---

## 📊 Phase 3 任务依赖图

```
T15 (主程序入口)
 ├── T16 (实盘数据)
 │    └── T17 (监控面板)
 └── T18 (记忆系统)
```

---

## 🎯 Phase 3 验收清单

### 功能验收

- [ ] **F1**: `python main.py --mode demo` 启动演示模式
- [ ] **F2**: 能获取真实行情数据 (AkShare)
- [ ] **F3**: 监控面板实时显示账户状态
- [ ] **F4**: 交易历史持久化存储

### 质量验收

- [ ] **Q1**: CLI 参数验证完善
- [ ] **Q2**: 异常处理覆盖所有数据请求
- [ ] **Q3**: 日志记录关键操作

---

## 📅 时间规划

| 任务 | 预估时间 | 说明 |
|------|---------|------|
| T15 | 2小时 | CLI 入口 |
| T16 | 3小时 | 真实数据 |
| T17 | 3小时 | 监控面板 |
| T18 | 2小时 | 记忆系统 |

---

**文档状态**: ✅ v1.0 已创建
**下一步**: 开始 T15 (主程序入口)