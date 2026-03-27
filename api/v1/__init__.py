"""
API v1 路由
"""
from fastapi import APIRouter

from .endpoints import strategy, analysis, system, trading, market, memory

api_router = APIRouter()

# 注册各个端点
api_router.include_router(strategy.router, prefix="/strategy", tags=["策略"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["分析"])
api_router.include_router(system.router, prefix="/system", tags=["系统"])
api_router.include_router(trading.router, prefix="/trading", tags=["交易"])
api_router.include_router(market.router, prefix="/market", tags=["行情"])
api_router.include_router(memory.router, prefix="/memory", tags=["记忆"])
