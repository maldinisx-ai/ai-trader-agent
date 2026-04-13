# AI Trader Agent - 待办事项清单

> 更新时间: 2026-03-29
> 当前进度: Phase 1 核心功能已完成，评分系统已集成，撤单功能已完成，反思机制已集成
> 测试覆盖率: 待确认 (目标 ≥80%，新增8个测试文件，部分测试待修复)

## 🚀 高优先级 (P0) - 近期必须完成

### 1. 单元测试覆盖率提升 ⚠️
**目标**: 从当前 54% 提升到 ≥80%

**状态**: 进行中 (新增8个测试文件，500+测试用例，部分测试待修复)

**已完成的测试文件**:
- ✅ `tests/test_cancel_order.py`: 新增 18 个测试用例（100% 通过）
- ✅ `tests/test_main.py`: 新增 20 个测试用例（100% 通过）
- ✅ `tests/test_akshare_fetcher.py`: 新增 25 个测试用例（99% 覆盖）
- ✅ `tests/test_efinance_fetcher.py`: 新增 29 个测试用例（99% 覆盖）
- ✅ `tests/test_pytdx_fetcher.py`: 新增 46 个测试用例（100% 覆盖）
- ✅ `tests/test_backtester_engine.py`: 新增 50 个测试用例（31% 覆盖 backtester.py）
- ✅ `tests/test_strategies.py`: 新增 46 个测试用例（63% 覆盖策略模块）
- ✅ `tests/test_config.py`: 新增 19 个测试用例（100% 覆盖 config.py）
- ✅ `tests/test_data_manager.py`: 新增 21 个测试用例（56% 覆盖 data_manager.py）
- ✅ `tests/test_strategy.py`: 新增 57 个测试用例（73% 覆盖 src/strategy/*）
- ✅ `tests/test_trader.py`: 新增 40 个测试用例（77% 覆盖 src/trader.py）
- ✅ `tests/test_agent_loop.py`: 新增 38 个测试用例（70% 覆盖 core/agent_loop.py）

**新增测试文件 (2026-03-29)**:
- ✅ `tests/test_sector_service.py`: ~80个测试用例（部分待修复）
- ✅ `tests/test_stock_name_service.py`: ~100个测试用例
- ⚠️ `tests/test_analysis_history.py`: ~60个测试用例（17个失败待修复）
- ⚠️ `tests/test_performance.py`: ~100个测试用例（5个失败待修复）
- ✅ `tests/test_tools_get_quote.py`: 获取行情工具测试
- ✅ `tests/test_tools_get_positions.py`: 获取持仓工具测试
- ✅ `tests/test_tools_place_order.py`: 下单工具测试
- ✅ `tests/test_tools_get_stock_list.py`: 获取股票列表工具测试

**当前问题**:
1. ⚠️ **pytest Windows 捕获系统bug**: 运行所有测试时出现 `I/O operation on closed file` 错误
   - 单个测试文件可正常运行
   - 需要使用 `-o capture=fd` 选项绕过
2. ⚠️ **部分测试失败**:
   - `test_analysis_history.py`: 17个测试失败
   - `test_performance.py`: 5个测试失败

**下一步**:
- [ ] 修复 `test_analysis_history.py` 中的失败测试
- [ ] 修复 `test_performance.py` 中的失败测试
- [ ] 解决 pytest 运行所有测试的问题
- [ ] 运行完整覆盖率报告验证是否达到80%目标

### ~~2. 撤单功能实现 📋~~
**状态**: ✅ 已完成
- ✅ 在 `simulation/matcher.py` 添加 `cancel_order()` 方法
- ✅ 在 `tools/trading/` 下创建 `cancel_order.py` 工具
- ✅ 在 `ToolExecutor` 中注册撤单工具
- ✅ 更新 `PolicyEngine` 添加撤单风控规则
- ✅ 添加撤单测试用例 (18 个测试，100% 通过)

### 3. 反思记忆机制 🧠
**描述**: Phase 2 核心功能，从交易中学习

**当前状态**: ✅ 已完成
- ✅ `core/reflection.py` 已实现并有 100% 测试覆盖
- ✅ `core/reflection_storage.py` 已实现 SQLite 持久化存储
- ✅ 已集成到 `AgentLoop` 主流程
- ✅ 反思数据包含在模型记忆中
- ✅ 测试覆盖 12 个集成测试 (100% 通过)

**完成内容**:
- ✅ 在 `AgentLoop` 中注入 `ReflectionEngine`
- ✅ 在 `_prepare_memories()` 中加载历史反思
- ✅ 在 `_think()` 阶段传递反思数据给模型
- ✅ 实现 `ReflectStorage` 反思持久化 (SQLite)
- ✅ 端到端反思流程测试通过

**参考**: `tests/test_reflection.py` (已实现的测试用例)

---

## 🔧 中优先级 (P1) - 近期规划

### 4. 实时数据接入 📡
**目标**: 从本地 CSV 切换到实时行情数据

**方案 A - AkShare**:
- [ ] 实现 `tools/data/akshare_fetcher.py::get_realtime_quote()`
- [ ] 添加实时行情缓存 (避免频繁请求)
- [ ] 处理异常情况 (网络超时、数据缺失)

**方案 B - Tushare**:
- [ ] 配置 Tushare Pro Token
- [ ] 实现实时行情接口
- [ ] 处理 API 限流

**参考**:
- `tools/data/akshare_fetcher.py` (已有框架)
- `tools/data/local_data_loader.py` (数据格式参考)

### 5. Redis 缓存层 💾
**目标**: 减少重复计算，提升性能

**缓存内容**:
- [ ] 行情数据缓存 (TTL: 5秒)
- [ ] 股票评分缓存 (TTL: 1小时)
- [ ] 技术指标缓存 (TTL: 5分钟)
- [ ] AI 决策结果缓存 (TTL: 30秒)

**实现**:
- [ ] 创建 `core/cache.py` 封装 Redis 操作
- [ ] 在 `LocalDataLoader` 中集成缓存
- [ ] 在 `ComprehensiveScoringSystem` 中集成缓存
- [ ] 添加缓存降级逻辑 (Redis 不可用时使用内存)

### 6. 本地模型部署 (Qwen2.5-7B) 🤖
**目标**: 降低 API 成本，实现离线运行

**部署步骤**:
- [ ] 安装 Ollama
- [ ] 下载 Qwen2.5:7b 模型
- [ ] 配置 `ModelRouter` 自动降级到本地模型
- [ ] 实现本地模型置信度计算
- [ ] 测试本地模型响应速度和质量

**配置参考**:
```yaml
# config/config.yaml
local_model:
  enabled: true
  provider: ollama
  model_name: qwen2.5:7b
  base_url: http://localhost:11434
  max_tokens: 2048
```

### 7. 融合决策模式 🔀
**描述**: API 模型 + 本地模型 双模型决策

**实现要点**:
- [ ] API 模型生成初步决策
- [ ] 本地模型对高风险交易进行二次确认
- [ ] 冲突解决策略 (保守/激进/加权平均)
- [ ] 融合决策日志记录

**参考**: `core/model_router.py:_merge_decisions()` (已有框架)

### 8. Token 预算控制 💰
**目标**: 控制 API 成本，避免超限

**实现**:
- [ ] 记录每次调用的 Token 使用量
- [ ] 实现每日 Token 预算 (100万 tokens/天)
- [ ] 超限时自动降级到本地模型
- [ ] 添加 Token 使用统计面板

**当前状态**:
- ✅ `ModelRouter` 已有 `_daily_tokens` 计数
- ⏳ 需要完善自动降级逻辑

---

## 📊 低优先级 (P2) - 长期规划

### 9. 回测引擎 📈
**当前状态**:
- ✅ `tests/test_backtester.py` 已有基础测试
- ⏳ `src/backtester.py` 实现不完整 (89% 覆盖，缺少 127 行代码)

**待完善**:
- [ ] 完善回测引擎核心逻辑
- [ ] 添加交易成本模拟 (滑点、手续费)
- [ ] 添加回测报告生成
- [ ] 实现参数优化功能

### 10. 监控面板 (Streamlit) 📺
**目标**: 实时监控交易状态和性能

**功能**:
- [ ] 账户资产曲线图
- [ ] 持仓明细表
- [ ] 交易历史记录
- [ ] AI 决策日志展示
- [ ] 模型性能指标

**技术选型**: Streamlit + Plotly

### 11. 真实券商 API 对接 🏦
**目标**: 从模拟交易切换到实盘

**风险**: ⚠️ 高风险，需要充分测试

**步骤**:
- [ ] 选择券商 API (华泰、东方财富等)
- [ ] 实现认证和签名
- [ ] 对接下单/撤单接口
- [ ] 对接行情接口
- [ ] 添加实盘风控 (比模拟更严格)
- [ ] 小资金试运行

### 12. WebSocket 实时推送 🔌
**目标**: 实时推送行情和交易信号

**实现**:
- [ ] 搭建 WebSocket 服务器
- [ ] 推送实时行情数据
- [ ] 推送 AI 交易信号
- [ ] 前端实时展示

---

## 📝 文档完善

### 13. API 文档
- [ ] 使用 Sphinx 生成 API 文档
- [ ] 添加模块说明
- [ ] 添加使用示例

### 14. 部署文档
- [ ] Docker 容器化
- [ ] 编写 docker-compose.yml
- [ ] 添加环境变量说明
- [ ] 编写部署指南

### 15. 用户手册
- [ ] 快速开始指南
- [ ] 配置说明
- [ ] 常见问题 FAQ
- [ ] 故障排查指南

---

## 🐛 Bug 修复

### 已知问题
1. **市场状态检测错误**: `'dict' object has no attribute 'ma5'`
   - 位置: `core/agent_loop.py:_detect_market_state()`
   - 优先级: P1
   - 状态: 已识别，未修复

2. **数据库连接未关闭**: 测试中的 ResourceWarning
   - 位置: `simulation/account.py`
   - 优先级: P2
   - 修复: 添加 `__del__` 方法显式关闭连接

---

## 📈 进度追踪

### Phase 1 - 核心功能 (95% 完成)
- [x] ReAct 循环框架
- [x] 生存规则系统
- [x] 风控引擎 (7层)
- [x] 市场状态检测
- [x] 评分系统集成
- [x] 本地数据加载
- [x] 撤单功能
- [ ] 测试覆盖率 ≥80% (进行中: 新增8个测试文件，500+测试用例，待修复并验证)

### Phase 2 - 智能增强 (50% 完成)
- [x] 反思机制框架
- [x] 反思机制集成到主流程
- [x] 反思持久化 (SQLite)
- [x] 反思数据注入模型记忆
- [ ] 本地模型部署
- [ ] 融合决策

### Phase 3 - 生产就绪 (10% 完成)
- [ ] 实时数据接入
- [ ] Redis 缓存
- [ ] 回测引擎
- [ ] 监控面板
- [ ] 真实券商对接

---

## 🎯 下周计划

1. **周一**: 修复测试覆盖率问题
   - 修复 `test_analysis_history.py` 失败测试
   - 修复 `test_performance.py` 失败测试
   - 解决 pytest Windows 运行问题
2. **周二**: 运行完整覆盖率报告
   - 验证是否达到80%目标
   - 如未达到，继续补充测试
3. **周三**: 配置 AkShare 实时数据
4. **周四**: Redis 缓存层实现
5. **周五**: 测试和文档更新

---

## 📞 联系方式

- 项目路径: `D:\projects\ai-trader-agent`
- 配置文件: `config/config.yaml`
- 测试命令: `python -m pytest tests/ -v`
- 运行命令: `python -m src.main run -m demo`
