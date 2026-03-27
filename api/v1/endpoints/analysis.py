"""
分析相关 API
"""
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)

from src.strategy import get_strategy_manager, StrategyExecutor
from src.strategy.data_preparer import MarketDataPreparer, FinancialDataPreparer
from src.config import get_config
from core.analysis_history import get_analysis_history_store, AnalysisRecord
from core.stock_name_service import get_stock_name_service

router = APIRouter()

# 获取配置
config = get_config()
DATA_DIR = Path(config.data_dir)

# 获取股票名称服务
stock_name_service = get_stock_name_service(data_dir=config.data_dir)


class AnalysisRequest(BaseModel):
    """分析请求"""
    stock_code: str
    strategies: Optional[List[str]] = None


class StrategySignalResponse(BaseModel):
    """策略信号响应"""
    strategy_name: str
    display_name: str
    signal: str  # buy, sell, hold
    confidence: float
    score: int
    reasoning: str
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class AnalysisResponse(BaseModel):
    """分析响应"""
    stock_code: str
    stock_name: str
    current_price: Optional[float] = None
    change_pct: Optional[float] = None
    overall_signal: str
    overall_score: int
    signals: List[StrategySignalResponse]
    active_strategies: List[str]
    analysis_time: str
    market_data: Optional[dict] = None


def get_stock_name(stock_code: str) -> str:
    """获取股票名称"""
    return stock_name_service.get_name(stock_code)


def load_kline_data(stock_code: str) -> Optional[pd.DataFrame]:
    """加载K线数据"""
    # 尝试多种文件名格式
    possible_names = [
        f"{stock_code.replace('.', '_')}.csv",
        f"{stock_code}.csv",
    ]

    for name in possible_names:
        filepath = DATA_DIR / "stocks" / name
        if filepath.exists():
            return pd.read_csv(filepath)

    return None


def load_financial_data(stock_code: str) -> dict:
    """加载财务数据"""
    financial_data = {}

    # 加载财务指标
    indicator_file = DATA_DIR / "fundamentals" / f"indicator_{stock_code.replace('.', '_')}.csv"
    if indicator_file.exists():
        try:
            financial_data["indicator_df"] = pd.read_csv(indicator_file)
        except Exception:
            pass

    # 加载利润表
    income_file = DATA_DIR / "financial" / f"income_{stock_code.replace('.', '_')}.csv"
    if income_file.exists():
        try:
            financial_data["income_df"] = pd.read_csv(income_file)
        except Exception:
            pass

    # 加载资产负债表
    balance_file = DATA_DIR / "financial" / f"balance_{stock_code.replace('.', '_')}.csv"
    if balance_file.exists():
        try:
            financial_data["balance_df"] = pd.read_csv(balance_file)
        except Exception:
            pass

    return financial_data


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_stock(request: AnalysisRequest):
    """
    分析股票

    Args:
        request: 分析请求

    Returns:
        分析结果
    """
    # 获取策略管理器
    strategy_manager = get_strategy_manager()

    # 如果指定了策略，激活这些策略
    if request.strategies:
        strategy_manager.activate(request.strategies)

    # 检查是否有激活的策略
    active_strategies = strategy_manager.get_active_strategies()
    if not active_strategies:
        # 默认激活所有策略
        all_strategies = strategy_manager.list_strategies()
        strategy_manager.activate([s.name for s in all_strategies])
        active_strategies = strategy_manager.get_active_strategies()

    if not active_strategies:
        raise HTTPException(
            status_code=400,
            detail="没有可用的策略"
        )

    # 加载K线数据
    kline_df = load_kline_data(request.stock_code)
    if kline_df is None or kline_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"找不到股票数据: {request.stock_code}"
        )

    # 准备市场数据
    try:
        market_data = MarketDataPreparer.prepare_from_df(kline_df)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"数据处理失败: {str(e)}"
        )

    # 加载财务数据
    financial_files = load_financial_data(request.stock_code)

    # 准备财务数据
    current_price = market_data.get("close", 0)
    if financial_files:
        financial_data = FinancialDataPreparer.prepare_from_multiple(
            income_df=financial_files.get("income_df"),
            balance_df=financial_files.get("balance_df"),
            indicator_df=financial_files.get("indicator_df"),
            current_price=current_price
        )
    else:
        financial_data = None

    # 创建执行器
    executor = StrategyExecutor(strategy_manager)

    # 执行分析
    try:
        result = executor.analyze_with_active_strategies(
            stock_code=request.stock_code,
            stock_name=get_stock_name(request.stock_code),
            market_data=market_data,
            financial_data=financial_data,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"分析执行失败: {str(e)}"
        )

    # 构建市场数据摘要
    market_summary = {
        "close": market_data.get("close"),
        "change_pct": market_data.get("change_pct"),
        "ma5": market_data.get("ma5"),
        "ma10": market_data.get("ma10"),
        "ma20": market_data.get("ma20"),
        "volume_ratio": market_data.get("volume_ratio"),
        "n20_gain_pct": market_data.get("n20_gain_pct"),
        "bias_ma5": market_data.get("bias_ma5"),
    }

    # 转换为响应格式
    return AnalysisResponse(
        stock_code=result.stock_code,
        stock_name=result.stock_name,
        current_price=market_data.get("close"),
        change_pct=market_data.get("change_pct"),
        overall_signal=result.overall_signal,
        overall_score=result.overall_score,
        signals=[
            StrategySignalResponse(
                strategy_name=s.strategy_name,
                display_name=s.display_name,
                signal=s.signal,
                confidence=s.confidence,
                score=s.score,
                reasoning=s.reasoning,
                entry_price=s.entry_price,
                stop_loss=s.stop_loss,
                take_profit=s.take_profit,
            )
            for s in result.signals
        ],
        active_strategies=[s.name for s in active_strategies],
        analysis_time=datetime.now().isoformat(),
        market_data=market_summary,
    )

    # 保存分析记录
    try:
        history_store = get_analysis_history_store()
        history_store.store_analysis(AnalysisRecord(
            stock_code=result.stock_code,
            stock_name=result.stock_name,
            analysis_time=datetime.now().isoformat(),
            overall_signal=result.overall_signal,
            overall_score=result.overall_score,
            current_price=market_data.get("close"),
            change_pct=market_data.get("change_pct"),
            active_strategies=[s.name for s in active_strategies],
            signals=[
                {
                    "strategy_name": s.strategy_name,
                    "display_name": s.display_name,
                    "signal": s.signal,
                    "confidence": s.confidence,
                    "score": s.score,
                    "reasoning": s.reasoning,
                }
                for s in result.signals
            ],
            market_data=market_summary,
        ))
    except Exception as e:
        # 保存失败不影响响应
        logger.warning(f"保存分析记录失败: {e}")


@router.get("/history")
async def get_analysis_history(
    stock_code: Optional[str] = None,
    limit: int = 20,
):
    """
    获取历史分析记录

    Args:
        stock_code: 可选，股票代码筛选
        limit: 返回数量限制

    Returns:
        历史记录列表
    """
    history_store = get_analysis_history_store()
    records = history_store.get_history(stock_code=stock_code, limit=limit)

    # 转换为响应格式
    return {
        "records": [
            {
                "id": r.id,
                "stock_code": r.stock_code,
                "stock_name": r.stock_name,
                "analysis_time": r.analysis_time,
                "overall_signal": r.overall_signal,
                "overall_score": r.overall_score,
                "current_price": r.current_price,
                "change_pct": r.change_pct,
                "active_strategies": r.active_strategies,
                "signals": r.signals,
            }
            for r in records
        ],
        "total": len(records),
    }


@router.get("/available-stocks")
async def get_available_stocks():
    """
    获取可分析的股票列表

    Returns:
        股票列表
    """
    stocks_dir = DATA_DIR / "stocks"
    if not stocks_dir.exists():
        return {"stocks": [], "total": 0}

    stock_files = list(stocks_dir.glob("*.csv"))
    stocks = []
    for f in stock_files:
        # 从文件名提取股票代码: 600519_SH.csv -> 600519.SH
        code = f.stem.replace('_', '.')
        stocks.append({
            "code": code,
            "name": stock_name_service.get_name(code),
        })

    return {
        "stocks": sorted(stocks, key=lambda x: x["code"]),
        "total": len(stocks),
    }
