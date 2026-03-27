# -*- coding: utf-8 -*-
"""
监控面板

提供 Web 界面展示账户状态和交易信息。
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List
from threading import Lock

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from core.schemas import SurvivalLevel
from core.stock_name_service import get_stock_name_service


logger = logging.getLogger(__name__)


# ============================================
# FastAPI 应用
# ============================================

app = FastAPI(title="AI Trader Agent Monitoring")

# 股票名称服务（延迟初始化）
_stock_name_service = None


def _get_stock_name_service():
    """获取股票名称服务（延迟初始化）"""
    global _stock_name_service
    if _stock_name_service is None:
        _stock_name_service = get_stock_name_service(data_dir="data")
    return _stock_name_service


# 全局状态（使用线程锁保护）
_shared_state: Dict[str, Any] = {
    "account_info": None,
    "positions": [],
    "survival_level": SurvivalLevel.NORMAL,
    "last_trade": None,
    "connected_clients": 0,
}
_state_lock = Lock()


# ============================================
# 静态文件挂载
# ============================================

# 注意：实际部署时需要创建这些目录
# app.mount("/static", StaticFiles(directory="monitoring/static"), name="static")


# ============================================
# API 端点
# ============================================

@app.get("/", response_class=HTMLResponse)
async def index():
    """主页"""
    return HTMLResponse(content=_get_index_html())


@app.get("/api/status")
async def get_status() -> Dict[str, Any]:
    """获取账户状态"""
    with _state_lock:
        return {
            "timestamp": datetime.now().isoformat(),
            "account": _shared_state.get("account_info"),
            "survival_level": _shared_state.get("survival_level"),
            "last_trade": _shared_state.get("last_trade"),
        }


@app.get("/api/positions")
async def get_positions() -> List[Dict[str, Any]]:
    """获取持仓列表"""
    stock_name_service = _get_stock_name_service()
    with _state_lock:
        positions = _shared_state.get("positions", [])
    return [
        {
            "symbol": p.symbol,
            "name": stock_name_service.get_name(p.symbol),
            "shares": p.shares,
            "avg_cost": p.avg_cost,
            "current_price": p.current_price,
            "market_value": p.market_value,
            "cost_value": p.cost_value,
            "pnl": p.pnl,
            "pnl_ratio": p.pnl_ratio,
        }
        for p in positions
    ]


@app.get("/api/trades")
async def get_trades(limit: int = 10) -> List[Dict[str, Any]]:
    """获取交易记录"""
    # TODO: 从数据库读取交易记录
    return []


@app.post("/api/update")
async def update_state(data: Dict[str, Any]) -> Dict[str, str]:
    """
    更新状态（由主程序调用）

    Args:
        data: 包含 account_info, positions, survival_level 等
    """
    with _state_lock:
        _shared_state.update(data)
    return {"status": "ok"}


# ============================================
# WebSocket 端点
# ============================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接用于实时推送"""
    await websocket.accept()
    with _state_lock:
        _shared_state["connected_clients"] += 1
        logger.info(f"[Monitoring] 客户端连接，当前连接数: {_shared_state['connected_clients']}")

    try:
        while True:
            # 等待客户端消息（心跳）
            await websocket.receive_text()
            # 发送当前状态（加锁保护）
            with _state_lock:
                state_copy = _shared_state.copy()
            await websocket.send_json(state_copy)

    except WebSocketDisconnect:
        with _state_lock:
            _shared_state["connected_clients"] -= 1
            logger.info(f"[Monitoring] 客户端断开，当前连接数: {_shared_state['connected_clients']}")


# ============================================
# HTML 模板
# ============================================

def _get_index_html() -> str:
    """返回主页 HTML"""
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Trader Agent - 监控面板</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        h1 {
            text-align: center;
            margin-bottom: 30px;
            color: #60a5fa;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .card {
            background: #1e293b;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }

        .card h2 {
            font-size: 18px;
            margin-bottom: 15px;
            color: #94a3b8;
            border-bottom: 1px solid #334155;
            padding-bottom: 10px;
        }

        .stat {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #334155;
        }

        .stat:last-child {
            border-bottom: none;
        }

        .stat-label {
            color: #94a3b8;
        }

        .stat-value {
            font-weight: bold;
        }

        .profit {
            color: #4ade80;
        }

        .loss {
            color: #f87171;
        }

        .status {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 14px;
            font-weight: 500;
        }

        .status.normal {
            background: #dcfce7;
            color: #166534;
        }

        .status.low_compute {
            background: #fef9c3;
            color: #854d0e;
        }

        .status.critical {
            background: #fee2e2;
            color: #991b1b;
        }

        .status.dead {
            background: #6b7280;
            color: #f9fafb;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #334155;
        }

        th {
            color: #94a3b8;
            font-weight: 500;
        }

        .chart-container {
            height: 300px;
            margin-top: 20px;
        }

        .last-update {
            text-align: center;
            color: #64748b;
            font-size: 14px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 AI Trader Agent 监控面板</h1>

        <div class="grid">
            <!-- 账户概览 -->
            <div class="card">
                <h2>💰 账户概览</h2>
                <div class="stat">
                    <span class="stat-label">初始资金</span>
                    <span class="stat-value" id="initial-cash">--</span>
                </div>
                <div class="stat">
                    <span class="stat-label">当前现金</span>
                    <span class="stat-value" id="cash">--</span>
                </div>
                <div class="stat">
                    <span class="stat-label">持仓市值</span>
                    <span class="stat-value" id="position-value">--</span>
                </div>
                <div class="stat">
                    <span class="stat-label">总资产</span>
                    <span class="stat-value" id="total-value">--</span>
                </div>
                <div class="stat">
                    <span class="stat-label">盈亏</span>
                    <span class="stat-value" id="profit-loss">--</span>
                </div>
                <div class="stat">
                    <span class="stat-label">盈亏比例</span>
                    <span class="stat-value" id="profit-loss-ratio">--</span>
                </div>
            </div>

            <!-- 生存状态 -->
            <div class="card">
                <h2>🛡️ 生存状态</h2>
                <div class="stat">
                    <span class="stat-label">当前等级</span>
                    <span class="stat-value">
                        <span class="status" id="survival-level">--</span>
                    </span>
                </div>
                <div class="stat">
                    <span class="stat-label">回撤率</span>
                    <span class="stat-value" id="drawdown">--</span>
                </div>
                <div class="stat">
                    <span class="stat-label">最大仓位</span>
                    <span class="stat-value" id="max-position">--</span>
                </div>
                <div class="stat">
                    <span class="stat-label">交易间隔</span>
                    <span class="stat-value" id="trading-interval">--</span>
                </div>
            </div>

            <!-- 连接状态 -->
            <div class="card">
                <h2>🔗 连接状态</h2>
                <div class="stat">
                    <span class="stat-label">WebSocket</span>
                    <span class="stat-value" id="ws-status">连接中...</span>
                </div>
                <div class="stat">
                    <span class="stat-label">最后更新</span>
                    <span class="stat-value" id="last-update">--</span>
                </div>
            </div>
        </div>

        <!-- 持仓列表 -->
        <div class="card">
            <h2>📈 持仓列表</h2>
            <table>
                <thead>
                    <tr>
                        <th>股票代码</th>
                        <th>持股数量</th>
                        <th>成本价</th>
                        <th>当前价</th>
                        <th>市值</th>
                        <th>盈亏</th>
                        <th>盈亏比例</th>
                    </tr>
                </thead>
                <tbody id="positions-body">
                    <tr>
                        <td colspan="7" style="text-align: center;">暂无持仓</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- 净值曲线 -->
        <div class="card" style="margin-top: 20px;">
            <h2>📉 净值曲线</h2>
            <div class="chart-container">
                <canvas id="equity-chart"></canvas>
            </div>
        </div>

        <div class="last-update">
            最后更新: <span id="page-update">--</span>
        </div>
    </div>

    <script>
        // WebSocket 连接
        const ws = new WebSocket('ws://localhost:8000/ws');
        let equityChart;

        ws.onopen = () => {
            document.getElementById('ws-status').textContent = '已连接';
            document.getElementById('ws-status').style.color = '#4ade80';
        };

        ws.onclose = () => {
            document.getElementById('ws-status').textContent = '已断开';
            document.getElementById('ws-status').style.color = '#f87171';
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            updateDashboard(data);
        };

        // 初始化图表
        function initChart() {
            const ctx = document.getElementById('equity-chart').getContext('2d');
            equityChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: '净值',
                        data: [],
                        borderColor: '#60a5fa',
                        backgroundColor: 'rgba(96, 165, 250, 0.1)',
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            grid: { color: '#334155' },
                            ticks: { color: '#94a3b8' }
                        },
                        y: {
                            grid: { color: '#334155' },
                            ticks: { color: '#94a3b8' }
                        }
                    },
                    plugins: {
                        legend: {
                            labels: { color: '#e2e8f0' }
                        }
                    }
                }
            });
        }

        // 更新仪表板
        function updateDashboard(data) {
            const account = data.account || {};
            const positions = data.positions || [];

            // 账户概览
            document.getElementById('initial-cash').textContent = formatMoney(account.initial_cash || 0);
            document.getElementById('cash').textContent = formatMoney(account.cash || 0);
            document.getElementById('position-value').textContent = formatMoney(account.position_value || 0);
            document.getElementById('total-value').textContent = formatMoney(account.total_value || 0);

            const profitLoss = account.profit_loss || 0;
            const profitLossEl = document.getElementById('profit-loss');
            profitLossEl.textContent = formatMoney(profitLoss, true);
            profitLossEl.className = 'stat-value ' + (profitLoss >= 0 ? 'profit' : 'loss');

            const profitLossRatio = account.profit_loss_ratio || 0;
            const profitLossRatioEl = document.getElementById('profit-loss-ratio');
            profitLossRatioEl.textContent = (profitLossRatio * 100).toFixed(2) + '%';
            profitLossRatioEl.className = 'stat-value ' + (profitLossRatio >= 0 ? 'profit' : 'loss');

            // 生存状态
            const levelEl = document.getElementById('survival-level');
            levelEl.textContent = data.survival_level || 'normal';
            levelEl.className = 'status ' + (data.survival_level || 'normal');

            document.getElementById('drawdown').textContent = (data.drawdown * 100).toFixed(2) + '%';

            // 持仓列表
            const tbody = document.getElementById('positions-body');
            if (positions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align: center;">暂无持仓</td></tr>';
            } else {
                tbody.innerHTML = positions.map(p => `
                    <tr>
                        <td>${p.symbol}</td>
                        <td>${p.shares}</td>
                        <td>¥${p.avg_cost.toFixed(2)}</td>
                        <td>¥${p.current_price.toFixed(2)}</td>
                        <td>¥${p.market_value.toFixed(0)}</td>
                        <td class="${p.pnl >= 0 ? 'profit' : 'loss'}">¥${p.pnl.toFixed(2)}</td>
                        <td class="${p.pnl_ratio >= 0 ? 'profit' : 'loss'}">${(p.pnl_ratio * 100).toFixed(2)}%</td>
                    </tr>
                `).join('');
            }

            // 更新时间
            const now = new Date();
            document.getElementById('last-update').textContent = now.toLocaleTimeString();
            document.getElementById('page-update').textContent = now.toLocaleString();

            // 更新图表
            if (equityChart && account.total_value) {
                const nowStr = now.toLocaleTimeString();
                equityChart.data.labels.push(nowStr);
                equityChart.data.datasets[0].data.push(account.total_value);

                // 限制数据点数量
                if (equityChart.data.labels.length > 50) {
                    equityChart.data.labels.shift();
                    equityChart.data.datasets[0].data.shift();
                }

                equityChart.update('none');
            }
        }

        // 格式化金额
        function formatMoney(value, withSign = false) {
            const formatted = '¥' + value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            return withSign ? (value >= 0 ? '+' + formatted : formatted) : formatted;
        }

        // 定期心跳
        setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send('ping');
            }
        }, 30000);

        // 初始化
        initChart();

        // 定期刷新
        setInterval(async () => {
            const response = await fetch('/api/status');
            const data = await response.json();
            updateDashboard(data);
        }, 5000);
    </script>
</body>
</html>
    """


# ============================================
# 启动函数
# ============================================

def start_monitoring(host: str = "0.0.0.0", port: int = 8000):
    """
    启动监控面板

    Args:
        host: 监听地址
        port: 监听端口
    """
    uvicorn.run(app, host=host, port=port)


# ============================================
# 状态更新函数
# ============================================

def update_account_state(account, positions: list, survival_level: SurvivalLevel = SurvivalLevel.NORMAL):
    """
    更新账户状态（供主程序调用）

    Args:
        account: 账户对象
        positions: 持仓列表
        survival_level: 生存等级
    """
    _shared_state.update({
        "account_info": account.get_account_info() if hasattr(account, 'get_account_info') else None,
        "positions": positions,
        "survival_level": survival_level,
        "last_update": datetime.now().isoformat(),
    })