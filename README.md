# AI Trader Agent

> 智能交易系统 - 基于 AI 的股票分析和交易策略平台

**项目代号**: ai-trader-agent
**版本**: v0.1.0
**状态**: 🚧 开发中

---

## 项目简介

AI Trader Agent 是一个智能交易系统，提供：
- **YAML 策略系统** - 用自然语言定义交易策略
- **AI 智能分析** - 多维度分析股票，提供精准买卖点位
- **React Web 界面** - 现代化的可视化管理界面
- **多数据源支持** - finshare、akshare、tushare 等

### 核心特性

- **策略系统**: YAML 定义策略，无需编程
- **AI 分析**: 结合技术面、基本面、资金面
- **Web 界面**: React + TypeScript + TailwindCSS
- **API 接口**: RESTful API，方便集成

---

## 快速开始

### 环境要求

- Python 3.10+
- Redis（可选，用于缓存）
- 8GB+ RAM（本地模型需要）

### 安装

```bash
# 克隆项目
git clone <repo-url>
cd ai-trader-agent

# 创建虚拟环境
python -3.10 -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Keys
```

### 运行

```bash
# 更新数据（获取前一日行情）
python scripts/update_data.py

# 启动 Agent
python -m core.main

# 启动监控面板（Phase 4）
streamlit run monitoring/dashboard.py
```

---

## 项目结构

```
ai-trader-agent/
├── core/                  # 核心智能体逻辑
│   ├── agent_loop.py      # ReAct Loop
│   ├── model_router.py    # 双模型路由
│   ├── policy_engine.py   # 风控引擎
│   ├── survival_rules.py  # 生存等级
│   ├── market_regime.py   # 市场状态感知
│   ├── reflection.py      # 反思机制
│   ├── schemas.py         # Pydantic 模型
│   └── memory/            # 6层记忆系统
├── tools/                 # 工具定义
│   ├── data/              # 数据工具
│   ├── trading/           # 交易工具
│   └── analysis/          # 分析工具
├── simulation/            # 模拟交易
│   ├── account.py         # 虚拟账户
│   └── matcher.py         # 撮合引擎
├── utils/                 # 工具函数
├── config/                # 配置文件
├── tests/                 # 测试套件
├── data/                  # 数据存储
├── scripts/               # 脚本工具
└── monitoring/            # 监控面板
```

---

## 开发

### 运行测试

```bash
# 所有测试
pytest tests/ -v

# 覆盖率报告
pytest tests/ --cov=core --cov=tools --cov=simulation --cov-report=html

# 单个测试文件
pytest tests/test_schemas.py -v
```

### 代码风格

```bash
# 格式化代码
black core/ tools/ simulation/

# 检查代码风格
flake8 core/ tools/ simulation/

# 类型检查
mypy core/
```

---

## 文档

- [PRD](./PRD.md) - 产品需求文档
- [架构设计](./architecture.md) - 技术架构
- [任务清单](./tasks.md) - 开发任务

---

## 许可证

MIT License

---

## 免责声明

本项目仅用于模拟交易和学习研究，不构成任何投资建议。实盘交易有风险，投资需谨慎。
