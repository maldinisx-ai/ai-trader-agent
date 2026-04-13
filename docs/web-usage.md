# AI Trader Agent Web 应用

## 快速启动

### 方式一：自动启动脚本
```bash
# Windows 双击运行
scripts/start.bat
```

### 方式二：手动启动

**启动后端:**
```bash
cd D:\projects\ai-trader-agent
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

**启动前端:**
```bash
cd web
npm run dev
```

## 访问地址

- **前端页面**: http://localhost:3004/
- **API 文档**: http://127.0.0.1:8000/docs
- **健康检查**: http://127.0.0.1:8000/health

## 功能说明

### 1. 首页
- 快速股票分析入口
- 系统概览

### 2. 分析页面 (http://localhost:3004/analysis)
- 输入股票代码进行分析
- 显示多个策略的评分结果
- 查看市场数据和技术指标

### 3. 策略页面 (http://localhost:3004/strategy)
- 查看可用策略列表
- 启用/禁用策略

### 4. 设置页面 (http://localhost:3004/settings)
- 系统配置

## API 端点

### 策略管理
- `GET /api/v1/strategy/` - 获取所有策略
- `GET /api/v1/strategy/active` - 获取激活策略
- `POST /api/v1/strategy/{name}/activate` - 激活策略

### 股票分析
- `POST /api/v1/analysis/analyze` - 分析股票
- `GET /api/v1/analysis/history` - 获取历史记录

## 可用策略

| 策略名称 | 类别 | 说明 |
|---------|------|------|
| momentum_trend | 趋势 | 动量趋势分析 |
| value_reversal | 反转 | 价值反转投资 |
| breakout_vol | 形态 | 放量突破策略 |

## 测试脚本

```bash
# 测试后端 API
python scripts/test_api.py

# 测试评分系统
python scripts/test_scoring.py
```

## 技术栈

**后端:**
- FastAPI
- Pandas (数据处理)
- Python 3.10+

**前端:**
- React 18
- React Router
- Tailwind CSS
- Vite

## 问题排查

### 前端页面空白
1. 确认后端服务正在运行
2. 打开浏览器开发者工具查看错误
3. 检查控制台网络请求是否成功

### API 请求失败
1. 检查后端服务: http://127.0.0.1:8000/health
2. 确认 Vite 代理配置正确
3. 检查 CORS 设置

### 端口冲突
前端会自动尝试使用可用端口（3000, 3001, 3002, 3003, 3004...）