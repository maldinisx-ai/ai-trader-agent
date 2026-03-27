@echo off
chcp 65001 >nul

echo ========================================
echo 启动 AI Trader Agent
echo ========================================

cd /d D:\projects\ai-trader-agent

echo.
echo [1/2] 启动后端服务...
start "AI Trader Backend" python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

timeout /t 3 /nobreak >nul

echo.
echo [2/2] 启动前端服务...
cd web
start "AI Trader Frontend" npm run dev

timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo 服务启动完成！
echo ========================================
echo 后端地址: http://127.0.0.1:8000
echo 前端地址: http://localhost:3004 (或自动分配的端口)
echo API文档: http://127.0.0.1:8000/docs
echo ========================================
echo 按任意键查看当前运行的进程...
pause >nul

echo.
echo 正在运行的进程:
tasklist | findstr /i "python node.exe vite.exe"
echo.
echo 按任意键关闭此窗口（服务将继续运行）...
pause >nul