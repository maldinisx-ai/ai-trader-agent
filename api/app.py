"""
FastAPI 应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .v1 import api_router
from src.config import get_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    config = get_config()
    print(f"[START] AI Trader Agent API starting")
    print(f"[DATA] Data directory: {config.data_dir}")
    yield
    # 关闭时清理
    print("[STOP] AI Trader Agent API shutting down")


app = FastAPI(
    title="AI Trader Agent API",
    description="智能交易系统 API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "ai-trader-agent"}


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "AI Trader Agent",
        "version": "0.1.0",
        "docs": "/docs",
    }
