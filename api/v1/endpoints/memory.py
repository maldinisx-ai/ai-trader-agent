"""
记忆系统相关 API

提供交易历史、反思记录、经验查询等功能。
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from src.config import get_config

router = APIRouter()

# 获取配置
config = get_config()
DATA_DIR = Path(config.data_dir)


# ==================== 数据模型 ====================

class TradeHistoryItem(BaseModel):
    """交易历史项"""
    trade_id: str
    symbol: str
    side: str
    shares: int
    price: float
    amount: float
    commission: float
    pnl: Optional[float] = None
    survival_level: Optional[str] = None
    market_regime: Optional[str] = None
    timestamp: str


class ReflectionRecord(BaseModel):
    """反思记录"""
    reflection_id: str
    trade_id: Optional[str] = None
    error_type: str
    analysis: str
    lesson: str
    avoid_action: str
    confidence: float
    timestamp: str


class TradeRecommendation(BaseModel):
    """交易建议"""
    symbol: str
    reason: str
    action: str
    confidence: float


# ==================== 交易历史 API ====================

@router.get("/trades", response_model=List[TradeHistoryItem])
async def get_trade_history(
    symbol: Optional[str] = Query(None, description="股票代码筛选"),
    limit: int = Query(50, description="返回数量限制", ge=1, le=500),
):
    """
    获取交易历史

    Args:
        symbol: 可选，股票代码筛选
        limit: 返回数量限制

    Returns:
        交易历史列表
    """
    # 从模拟账户获取交易记录
    from simulation.account import Account

    account = Account(db_path="data/trading.db")
    trades = account.get_trades(symbol=symbol, limit=limit)

    # Account.get_trades() 返回 Dict 列表，不是 Trade 对象
    return [
        TradeHistoryItem(
            trade_id=t["trade_id"],
            symbol=t["symbol"],
            side=t["side"],
            shares=t["shares"],
            price=float(t["price"]),
            amount=float(t["amount"]),
            commission=float(t["commission"]),
            pnl=None,  # 数据库中不存储 pnl
            survival_level=None,
            market_regime=None,
            timestamp=t["timestamp"],
        )
        for t in trades
    ]


@router.get("/trades/statistics")
async def get_trade_statistics(
    symbol: Optional[str] = Query(None, description="股票代码筛选"),
):
    """
    获取交易统计

    Args:
        symbol: 可选，股票代码筛选

    Returns:
        交易统计数据
    """
    from simulation.account import Account

    account = Account(db_path="data/trading.db")
    trades = account.get_trades(symbol=symbol, limit=10000)

    # trades 是 Dict 列表
    buy_trades = [t for t in trades if t["side"] == "buy"]
    sell_trades = [t for t in trades if t["side"] == "sell"]

    # 注意：数据库中不存储 pnl，所以无法计算准确的胜率等指标
    total_amount = sum(t["amount"] for t in trades)

    return {
        "total_trades": len(trades),
        "buy_trades": len(buy_trades),
        "sell_trades": len(sell_trades),
        "completed_trades": 0,  # 需要基于买卖配对计算
        "win_trades": 0,
        "loss_trades": 0,
        "win_rate": 0,
        "total_pnl": 0,
        "total_amount": round(total_amount, 2),
        "avg_win": 0,
        "avg_loss": 0,
        "profit_factor": 0,
        "note": "胜率数据需要基于持仓盈亏计算，当前版本仅提供基础统计",
    }


# ==================== 反思记录 API ====================

@router.get("/reflections", response_model=List[ReflectionRecord])
async def get_reflections(
    error_type: Optional[str] = Query(None, description="错误类型筛选"),
    limit: int = Query(20, description="返回数量限制", ge=1, le=100),
):
    """
    获取反思记录

    Args:
        error_type: 可选，错误类型筛选
        limit: 返回数量限制

    Returns:
        反思记录列表
    """
    reflections = []

    # 从记忆系统获取反思记录
    try:
        from core.memory.reflection_store import ReflectionStore

        store = ReflectionStore(db_path="data/trading.db")

        # 获取所有反思
        all_reflections = store.get_all_reflections(limit=limit)

        # 筛选错误类型
        if error_type:
            all_reflections = [r for r in all_reflections if r.error_type.value == error_type]

        for r in all_reflections:
            reflections.append(ReflectionRecord(
                reflection_id=r.reflection_id,
                trade_id=r.trade_id,
                error_type=r.error_type.value,
                analysis=r.analysis,
                lesson=r.lesson,
                avoid_action=r.avoid_action,
                confidence=r.confidence,
                timestamp=r.timestamp,
            ))
    except Exception as e:
        # 如果记忆系统未初始化，返回空列表
        pass

    return reflections


@router.get("/reflections/error-types")
async def get_error_types():
    """
    获取所有错误类型

    Returns:
        错误类型列表
    """
    from core.schemas import ErrorType

    error_types = [
        {"value": et.value, "description": et.name.replace("_", " ").title()}
        for et in ErrorType
    ]

    return {
        "error_types": error_types,
        "total": len(error_types),
    }


# ==================== 交易建议 API ====================

@router.get("/recommendations", response_model=List[TradeRecommendation])
async def get_trade_recommendations(
    symbol: Optional[str] = Query(None, description="股票代码"),
    limit: int = Query(5, description="返回数量限制", ge=1, le=10),
):
    """
    获取交易建议

    基于记忆系统中的经验和反思记录。

    Args:
        symbol: 可选，股票代码
        limit: 返回数量限制

    Returns:
        交易建议列表
    """
    recommendations = []

    try:
        from simulation.account import Account

        account = Account(db_path="data/trading.db")
        recs = account.get_trade_recommendations(symbol=symbol, limit=limit)

        for rec in recs:
            recommendations.append(TradeRecommendation(
                symbol=rec.get("symbol", ""),
                reason=rec.get("reason", ""),
                action=rec.get("action", ""),
                confidence=rec.get("confidence", 0.0),
            ))
    except Exception as e:
        # 如果获取失败，返回空列表
        pass

    return recommendations


# ==================== 记忆查询 API ====================

@router.get("/memory/summary")
async def get_memory_summary():
    """
    获取记忆系统摘要

    Returns:
        记忆系统统计信息
    """
    from simulation.account import Account

    account = Account(db_path="data/trading.db")

    # 获取交易统计
    trades = account.get_trades(limit=10000)

    # 获取反思记录
    reflection_count = 0
    try:
        from core.memory.reflection_store import ReflectionStore
        store = ReflectionStore(db_path="data/trading.db")
        reflection_count = len(store.get_all_reflections(limit=1000))
    except Exception:
        pass

    return {
        "total_trades": len(trades),
        "total_reflections": reflection_count,
        "survival_level": "normal",  # TODO: 从账户获取当前生存等级
        "market_regime": "bull",  # TODO: 从市场感知获取当前状态
        "last_trade": trades[0]["timestamp"] if trades else None,
        "last_reflection": datetime.now().isoformat(),  # TODO: 从反思存储获取
    }


@router.post("/memory/record-reflection")
async def record_reflection(
    trade_id: Optional[str] = None,
    error_type: str = "UNKNOWN",
    analysis: str = "",
    lesson: str = "",
    avoid_action: str = "",
    confidence: float = 0.5,
):
    """
    记录反思

    Args:
        trade_id: 关联的交易ID
        error_type: 错误类型
        analysis: 分析内容
        lesson: 经验教训
        avoid_action: 避免措施
        confidence: 信心度 (0-1)

    Returns:
        记录结果
    """
    try:
        from core.memory.reflection_store import ReflectionStore
        from core.schemas import ErrorType

        store = ReflectionStore(db_path="data/trading.db")

        # 转换错误类型
        try:
            error_type_enum = ErrorType(error_type)
        except ValueError:
            error_type_enum = ErrorType.UNKNOWN

        reflection_id = store.store_reflection(
            trade_id=trade_id,
            error_type=error_type_enum,
            analysis=analysis,
            lesson=lesson,
            avoid_action=avoid_action,
            confidence=confidence,
        )

        return {
            "status": "ok",
            "reflection_id": reflection_id,
            "message": "反思记录已保存",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"保存失败: {str(e)}"
        )


# ==================== 经验学习 API ====================

@router.get("/memory/lessons")
async def get_lessons(
    symbol: Optional[str] = Query(None, description="股票代码"),
    limit: int = Query(10, description="返回数量限制", ge=1, le=50),
):
    """
    获取经验教训

    Args:
        symbol: 可选，股票代码
        limit: 返回数量限制

    Returns:
        经验教训列表
    """
    lessons = []

    try:
        from core.memory.reflection_store import ReflectionStore

        store = ReflectionStore(db_path="data/trading.db")
        reflections = store.get_all_reflections(limit=limit * 2)

        for r in reflections:
            # 筛选高信心的反思
            if r.confidence >= 0.7:
                lessons.append({
                    "lesson": r.lesson,
                    "avoid_action": r.avoid_action,
                    "confidence": r.confidence,
                    "symbol": r.trade_id[:6] if r.trade_id and len(r.trade_id) >= 6 else None,
                    "error_type": r.error_type.value,
                })

        # 限制返回数量
        lessons = lessons[:limit]
    except Exception:
        pass

    return {
        "lessons": lessons,
        "total": len(lessons),
    }