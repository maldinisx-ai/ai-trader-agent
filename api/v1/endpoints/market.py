"""
行情数据相关 API

提供股票行情、K线数据、市场概览等功能。
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

from src.config import get_config
from core.stock_name_service import get_stock_name_service
from core.sector_service import get_sector_service

router = APIRouter()

# 获取配置
config = get_config()
DATA_DIR = Path(config.data_dir)

# 获取股票名称服务
stock_name_service = get_stock_name_service(data_dir=config.data_dir)

# 获取行业板块服务
sector_service = get_sector_service(data_dir=config.data_dir)


# ==================== 数据模型 ====================

class QuoteData(BaseModel):
    """行情数据"""
    symbol: str
    name: str
    price: float
    change: float
    change_pct: float
    volume: float
    amount: float
    high: float
    low: float
    open: float
    pre_close: float


class KlineData(BaseModel):
    """K线数据"""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float


class MarketOverview(BaseModel):
    """市场概览"""
    index_name: str
    index_value: float
    change: float
    change_pct: float
    timestamp: str


# ==================== 股票行情 API ====================

@router.get("/quote/{symbol}", response_model=QuoteData)
async def get_quote(symbol: str):
    """
    获取股票最新行情

    Args:
        symbol: 股票代码，如 000001.SZ 或 600519.SH

    Returns:
        行情数据

    Raises:
        404: 如果找不到数据
    """
    # 尝试从不同数据源获取
    quote = None

    # 1. 尝试从 klines 目录获取
    kline_files = [
        DATA_DIR / "klines" / f"{symbol.replace('.', '_')}.csv",
        DATA_DIR / "stocks" / f"stock_{symbol.replace('.', '_')}.csv",
        DATA_DIR / "stocks" / f"{symbol.replace('.', '_')}.csv",
    ]

    for filepath in kline_files:
        if filepath.exists():
            try:
                df = pd.read_csv(filepath)
                if not df.empty:
                    # 获取最后一行数据
                    latest = df.iloc[-1]

                    # 标准化列名
                    col_map = {
                        'open': 'open', 'open_price': 'open', '开盘': 'open',
                        'high': 'high', 'high_price': 'high', '最高': 'high',
                        'low': 'low', 'low_price': 'low', '最低': 'low',
                        'close': 'close', 'close_price': 'close', '收盘': 'close',
                        'volume': 'volume', '成交量': 'volume',
                        'amount': 'amount', '成交额': 'amount',
                    }

                    for key, value in col_map.items():
                        if key in latest:
                            latest[value] = latest[key]

                    # 计算涨跌幅
                    close = latest.get('close', 0)
                    pre_close = latest.get('pre_close', latest.get('close', 0))
                    if len(df) > 1:
                        pre_close = df.iloc[-2].get('close', close)

                    change = close - pre_close
                    change_pct = (change / pre_close * 100) if pre_close > 0 else 0

                    quote = QuoteData(
                        symbol=symbol,
                        name=stock_name_service.get_name(symbol),
                        price=float(close),
                        change=float(change),
                        change_pct=float(change_pct),
                        volume=float(latest.get('volume', 0)),
                        amount=float(latest.get('amount', 0)),
                        high=float(latest.get('high', close)),
                        low=float(latest.get('low', close)),
                        open=float(latest.get('open', close)),
                        pre_close=float(pre_close),
                    )
                    break
            except Exception:
                continue

    if quote is None:
        raise HTTPException(
            status_code=404,
            detail=f"找不到股票数据: {symbol}"
        )

    return quote


@router.get("/quotes", response_model=List[QuoteData])
async def get_quotes(
    symbols: str = Query(..., description="股票代码，用逗号分隔"),
):
    """
    批量获取股票行情

    Args:
        symbols: 股票代码列表，逗号分隔，如 "000001.SZ,600519.SH"

    Returns:
        行情数据列表
    """
    symbol_list = symbols.split(',')
    quotes = []

    for symbol in symbol_list:
        try:
            quote = await get_quote(symbol.strip())
            quotes.append(quote)
        except HTTPException:
            continue  # 跳过找不到的股票

    return quotes


# ==================== K线数据 API ====================

@router.get("/klines/{symbol}", response_model=List[KlineData])
async def get_klines(
    symbol: str,
    days: int = Query(30, description="获取最近N天的数据", ge=1, le=365),
):
    """
    获取股票K线数据

    Args:
        symbol: 股票代码
        days: 获取天数

    Returns:
        K线数据列表

    Raises:
        404: 如果找不到数据
    """
    # 尝试不同文件路径
    kline_files = [
        DATA_DIR / "klines" / f"{symbol.replace('.', '_')}.csv",
        DATA_DIR / "stocks" / f"stock_{symbol.replace('.', '_')}.csv",
        DATA_DIR / "stocks" / f"{symbol.replace('.', '_')}.csv",
    ]

    df = None
    for filepath in kline_files:
        if filepath.exists():
            try:
                df = pd.read_csv(filepath)
                break
            except Exception:
                continue

    if df is None or df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"找不到K线数据: {symbol}"
        )

    # 获取最近N天数据
    df = df.tail(days)

    # 标准化列名
    col_map = {
        'date': 'date', 'trade_date': 'date', '日期': 'date',
        'open': 'open', 'open_price': 'open', '开盘': 'open',
        'high': 'high', 'high_price': 'high', '最高': 'high',
        'low': 'low', 'low_price': 'low', '最低': 'low',
        'close': 'close', 'close_price': 'close', '收盘': 'close',
        'volume': 'volume', '成交量': 'volume',
        'amount': 'amount', '成交额': 'amount',
    }

    for key, value in col_map.items():
        if key in df.columns:
            df[value] = df[key]

    # 转换为响应格式
    klines = []
    for _, row in df.iterrows():
        klines.append(KlineData(
            date=str(row.get('date', '')),
            open=float(row.get('open', 0)),
            high=float(row.get('high', 0)),
            low=float(row.get('low', 0)),
            close=float(row.get('close', 0)),
            volume=float(row.get('volume', 0)),
            amount=float(row.get('amount', 0)),
        ))

    return klines


# ==================== 股票列表 API ====================

@router.get("/stocks")
async def get_stock_list(
    limit: int = Query(100, description="返回数量限制", ge=1, le=1000),
    offset: int = Query(0, description="偏移量", ge=0),
):
    """
    获取股票列表

    Args:
        limit: 返回数量限制
        offset: 偏移量

    Returns:
        股票列表
    """
    # 从 all_stocks.json 读取
    stock_list_file = DATA_DIR / "all_stocks.json"

    if stock_list_file.exists():
        import json
        with open(stock_list_file, 'r', encoding='utf-8') as f:
            stock_data = json.load(f)

        codes = stock_data.get("codes", [])
        total = len(codes)

        # 分页
        codes = codes[offset:offset + limit]

        stocks = []
        for code in codes:
            stocks.append({
                "code": code,
                "name": stock_name_service.get_name(code),
                "exchange": code.split('.')[-1],
            })

        return {
            "stocks": stocks,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    # 如果没有股票列表文件，扫描 klines 目录
    klines_dir = DATA_DIR / "klines"
    if klines_dir.exists():
        stock_files = list(klines_dir.glob("*.csv"))
        stock_files.sort()

        total = len(stock_files)
        stock_files = stock_files[offset:offset + limit]

        stocks = []
        for f in stock_files:
            code = f.stem.replace('_', '.')
            stocks.append({
                "code": code,
                "name": stock_name_service.get_name(code),
                "exchange": code.split('.')[-1],
            })

        return {
            "stocks": stocks,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    return {
        "stocks": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
    }


@router.get("/stocks/search")
async def search_stocks(
    keyword: str = Query(..., description="搜索关键词"),
    limit: int = Query(10, description="返回数量限制", ge=1, le=50),
):
    """
    搜索股票

    Args:
        keyword: 搜索关键词（股票代码或名称）
        limit: 返回数量限制

    Returns:
        匹配的股票列表
    """
    # 使用股票名称服务搜索（同时支持代码和名称搜索）
    results = stock_name_service.search(keyword, limit=limit)

    return {
        "stocks": [{"code": r["code"], "name": r["name"]} for r in results],
        "total": len(results),
    }

    return {
        "stocks": [],
        "total": 0,
    }


# ==================== 市场概览 API ====================

@router.get("/market/overview", response_model=List[MarketOverview])
async def get_market_overview():
    """
    获取市场概览

    Returns:
        主要指数行情
    """
    # 主要指数代码
    indices = [
        {"code": "000001.SH", "name": "上证指数"},
        {"code": "399001.SZ", "name": "深证成指"},
        {"code": "399006.SZ", "name": "创业板指"},
    ]

    overview = []

    for idx in indices:
        try:
            # 尝试获取指数数据
            index_file = DATA_DIR / "index" / f"index_{idx['code'].replace('.', '_')}.csv"

            if index_file.exists():
                df = pd.read_csv(index_file)
                if not df.empty:
                    latest = df.iloc[-1]

                    # 计算涨跌幅
                    close = latest.get('close', 0)
                    pre_close = latest.get('pre_close', close)
                    if len(df) > 1:
                        pre_close = df.iloc[-2].get('close', close)

                    change = close - pre_close
                    change_pct = (change / pre_close * 100) if pre_close > 0 else 0

                    overview.append(MarketOverview(
                        index_name=idx['name'],
                        index_value=float(close),
                        change=float(change),
                        change_pct=float(change_pct),
                        timestamp=latest.get('date', ''),
                    ))
        except Exception:
            continue

    return overview


@router.get("/market/sectors")
async def get_market_sectors(
    limit: int = Query(50, description="返回数量限制", ge=1, le=200),
):
    """
    获取行业板块数据

    Args:
        limit: 返回数量限制

    Returns:
        行业板块行情
    """
    sectors = sector_service.get_all_sectors()

    # 按涨跌幅排序
    sectors = sorted(sectors, key=lambda x: x.change_pct, reverse=True)

    return {
        "sectors": [s.to_dict() for s in sectors[:limit]],
        "total": len(sectors),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/market/hot")
async def get_hot_stocks(
    limit: int = Query(10, description="返回数量限制", ge=1, le=50),
):
    """
    获取热门股票

    Args:
        limit: 返回数量限制

    Returns:
        涨幅榜股票列表
    """
    # 从 all_stocks.json 获取所有股票
    stock_list_file = DATA_DIR / "all_stocks.json"

    if not stock_list_file.exists():
        return {"stocks": [], "total": 0}

    import json
    with open(stock_list_file, 'r', encoding='utf-8') as f:
        stock_data = json.load(f)

    codes = stock_data.get("codes", [])

    # 随机选取一些股票作为示例（实际应该按涨跌幅排序）
    import random
    sampled = random.sample(codes, min(limit, len(codes)))

    stocks = []
    for code in sampled:
        try:
            quote = await get_quote(code)
            stocks.append({
                "code": quote.symbol,
                "name": quote.name,
                "price": quote.price,
                "change_pct": quote.change_pct,
            })
        except HTTPException:
            continue

    # 按涨幅排序
    stocks.sort(key=lambda x: x['change_pct'], reverse=True)

    return {
        "stocks": stocks[:limit],
        "total": len(stocks),
    }


@router.get("/market/sectors/top-gainers")
async def get_top_sector_gainers(
    limit: int = Query(5, description="返回数量限制", ge=1, le=20),
):
    """
    获取行业板块涨幅榜

    Args:
        limit: 返回数量限制

    Returns:
        涨幅最大的板块列表
    """
    sectors = sector_service.get_top_gainers(limit=limit)

    return {
        "sectors": [s.to_dict() for s in sectors],
        "total": len(sectors),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/market/sectors/top-losers")
async def get_top_sector_losers(
    limit: int = Query(5, description="返回数量限制", ge=1, le=20),
):
    """
    获取行业板块跌幅榜

    Args:
        limit: 返回数量限制

    Returns:
        跌幅最大的板块列表
    """
    sectors = sector_service.get_top_losers(limit=limit)

    return {
        "sectors": [s.to_dict() for s in sectors],
        "total": len(sectors),
        "timestamp": datetime.now().isoformat(),
    }