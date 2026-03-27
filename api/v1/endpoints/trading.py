"""
交易相关 API

提供账户、持仓、下单、交易历史等功能。
"""
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import re
import threading
import pandas as pd

from simulation.account import Account
from core.schemas import OrderSide, Position, Trade
from src.config import get_config

logger = logging.getLogger(__name__)
config = get_config()
DATA_DIR = Path(config.data_dir)

router = APIRouter()

# 线程安全的账户单例
_account: Optional[Account] = None
_account_lock = threading.Lock()


def _get_current_price(symbol: str) -> Optional[float]:
    """
    获取股票当前价格

    Args:
        symbol: 股票代码

    Returns:
        当前价格，如果找不到返回 None
    """
    # 尝试不同文件路径
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
                    # 获取最后一行的收盘价
                    latest = df.iloc[-1]
                    price = latest.get('close', latest.get('收盘', latest.get('close_price')))
                    if price:
                        return float(price)
            except Exception as e:
                logger.warning(f"读取 {filepath} 失败: {e}")
                continue

    return None


def get_account() -> Account:
    """
    获取账户实例（线程安全单例）

    使用 FastAPI 依赖注入，可在端点中通过 Depends(get_account) 使用
    """
    global _account
    if _account is None:
        with _account_lock:
            # 双重检查锁定
            if _account is None:
                _account = Account(
                    initial_cash=1_000_000.0,
                    db_path="data/trading.db",
                )
    return _account


# ==================== 数据模型 ====================

class AccountInfoResponse(BaseModel):
    """账户信息响应"""
    account_id: int
    cash: float
    initial_cash: float
    total_value: float
    position_value: float
    profit: float
    profit_rate: float
    created_at: str
    updated_at: str


class PositionResponse(BaseModel):
    """持仓响应"""
    symbol: str
    shares: int
    avg_price: float
    current_price: float
    market_value: float
    cost_value: float
    profit: float
    profit_rate: float


class TradeResponse(BaseModel):
    """交易记录响应"""
    trade_id: str
    symbol: str
    side: str
    shares: int
    price: float
    amount: float
    commission: float
    stamp_duty: float
    slippage: float
    total_cost: float
    pnl: Optional[float]
    survival_level: Optional[str]
    market_regime: Optional[str]
    timestamp: str


class OrderRequest(BaseModel):
    """下单请求"""
    symbol: str = Field(..., description="股票代码，格式: 000001.SZ 或 600000.SH")
    side: str = Field(..., description="方向: buy/sell")
    shares: int = Field(..., gt=0, description="股数（必须是100的整数倍）")
    price: Optional[float] = Field(None, description="委托价格（元），市价单可省略")
    order_type: str = Field("market", description="订单类型: market/limit")

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """验证股票代码格式"""
        pattern = r'^\d{6}\.(SH|SZ)$'
        if not re.match(pattern, v):
            raise ValueError(f"股票代码格式错误，应为: 000001.SZ 或 600000.SH")
        return v.upper()

    @field_validator("shares")
    @classmethod
    def validate_shares(cls, v: int) -> int:
        """验证股数是否为100的整数倍"""
        if v % 100 != 0:
            raise ValueError("股数必须是100的整数倍")
        return v


class OrderResponse(BaseModel):
    """下单响应"""
    order_id: str
    status: str
    message: str
    executed: bool
    trade_id: Optional[str] = None
    execution_price: Optional[float] = None
    execution_time: Optional[str] = None


# ==================== 账户相关 API ====================

@router.get("/account", response_model=AccountInfoResponse)
async def get_account_info():
    """
    获取账户信息

    Returns:
        账户信息
    """
    account = get_account()
    info = account.get_account_info()

    # 字段映射：Account.get_account_info() 返回的字段名不同
    return AccountInfoResponse(
        account_id=1,  # 固定账户ID
        cash=info["cash"],
        initial_cash=info["initial_cash"],
        total_value=info["total_value"],
        position_value=info["position_value"],
        profit=info.get("profit_loss", 0.0),
        profit_rate=info.get("profit_loss_ratio", 0.0),
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )


@router.post("/account/reset")
async def reset_account():
    """
    重置账户

    清空所有持仓和交易记录，重置为初始资金。

    Returns:
        重置结果
    """
    account = get_account()
    account.reset()

    return {"status": "ok", "message": "账户已重置"}


# ==================== 持仓相关 API ====================

@router.get("/positions", response_model=List[PositionResponse])
async def get_positions():
    """
    获取所有持仓

    Returns:
        持仓列表
    """
    account = get_account()
    positions = account.get_positions()

    return [
        PositionResponse(
            symbol=p.symbol,
            shares=p.shares,
            avg_price=float(p.avg_cost),
            current_price=float(p.current_price),
            market_value=float(p.market_value),
            cost_value=float(p.cost_value),
            profit=float(p.pnl),
            profit_rate=float(p.pnl_ratio),
        )
        for p in positions
    ]


@router.get("/positions/{symbol}", response_model=PositionResponse)
async def get_position(symbol: str):
    """
    获取单个股票持仓

    Args:
        symbol: 股票代码

    Returns:
        持仓详情

    Raises:
        404: 如果没有该持仓
    """
    account = get_account()
    position = account.get_position(symbol)

    if position is None:
        raise HTTPException(
            status_code=404,
            detail=f"没有持仓: {symbol}"
        )

    return PositionResponse(
        symbol=position.symbol,
        shares=position.shares,
        avg_price=float(position.avg_cost),
        current_price=float(position.current_price),
        market_value=float(position.market_value),
        cost_value=float(position.cost_value),
        profit=float(position.pnl),
        profit_rate=float(position.pnl_ratio),
    )


@router.post("/positions/update-prices")
async def update_position_prices(prices: Dict[str, float]):
    """
    更新持仓价格

    Args:
        prices: 股票代码到价格的映射

    Returns:
        更新结果
    """
    account = get_account()
    account.update_prices(prices)

    return {
        "status": "ok",
        "updated_count": len(prices),
        "message": f"已更新 {len(prices)} 个持仓的价格"
    }


# ==================== 交易相关 API ====================

@router.post("/orders", response_model=OrderResponse)
async def place_order(request: OrderRequest):
    """
    下单

    Args:
        request: 下单请求

    Returns:
        订单执行结果
    """
    account = get_account()

    # 验证订单方向
    side = request.side.lower()
    if side not in ["buy", "sell"]:
        raise HTTPException(
            status_code=400,
            detail=f"无效的方向: {request.side}，必须是 buy 或 sell"
        )

    # 验证订单类型
    order_type = request.order_type.lower()
    if order_type not in ["market", "limit"]:
        raise HTTPException(
            status_code=400,
            detail=f"无效的订单类型: {request.order_type}，必须是 market 或 limit"
        )

    # 获取执行价格
    execution_price = request.price

    # 市价单自动获取价格
    if order_type == "market" and execution_price is None:
        auto_price = _get_current_price(request.symbol)
        if auto_price is None:
            raise HTTPException(
                status_code=404,
                detail=f"无法获取 {request.symbol} 的实时价格，请手动提供价格"
            )
        execution_price = auto_price
        logger.info(f"市价单自动获取价格: {request.symbol} -> {execution_price}")

    # 计算金额
    amount = execution_price * request.shares

    # 获取当前持仓
    position = account.get_position(request.symbol)

    # 验证卖单
    if side == "sell":
        if position is None or position.shares < request.shares:
            raise HTTPException(
                status_code=400,
                detail=f"持仓不足: {request.symbol}, 当前持仓: {position.shares if position else 0}, 请求卖出: {request.shares}"
            )

    # 计算费用
    fees = account.calculate_total_fee(amount, side)
    total_cost = fees["total"]

    # 对于买单，检查资金是否充足
    if side == "buy":
        cash = account.cash
        if cash < total_cost:
            raise HTTPException(
                status_code=400,
                detail=f"资金不足: 需要资金 {total_cost:.2f}，可用资金 {cash:.2f}"
            )

    # 创建订单和撮合结果
    from core.schemas import MatchResult, Order, OrderType, OrderStatus
    import uuid

    order_id = str(uuid.uuid4())

    order = Order(
        order_id=order_id,
        symbol=request.symbol,
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        quantity=request.shares,  # Order 使用 quantity 而不是 shares
        price=execution_price,
        order_type=OrderType.MARKET if order_type == "market" else OrderType.LIMIT,
        status=OrderStatus.FILLED,
        filled_quantity=request.shares,
        filled_price=execution_price,
    )

    # 创建撮合结果
    match_result = MatchResult(
        order=order,
        filled_quantity=request.shares,
        filled_price=execution_price,
        fully_filled=True,
        reason="订单已成交",
    )

    # 执行交易
    try:
        success = account.update_from_trade(match_result)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="交易执行失败"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    return OrderResponse(
        order_id=order_id,
        status="filled",
        message="订单已成交",
        executed=True,
        trade_id=None,  # 当前实现不返回 trade_id
        execution_price=execution_price,
        execution_time=datetime.now().isoformat(),
    )


@router.post("/orders/cancel")
async def cancel_order(order_id: str):
    """
    取消订单

    注意：当前实现中订单直接执行，不支持撤单。
    此接口为保留接口，未来可实现挂单功能。

    Args:
        order_id: 订单ID

    Returns:
        取消结果
    """
    raise HTTPException(
        status_code=501,
        detail="当前版本不支持撤单功能"
    )


# ==================== 交易历史 API ====================

@router.get("/trades", response_model=List[TradeResponse])
async def get_trades_history(
    symbol: Optional[str] = None,
    limit: int = 50,
):
    """
    获取交易历史

    Args:
        symbol: 可选，股票代码筛选
        limit: 返回数量限制

    Returns:
        交易记录列表
    """
    account = get_account()
    trades = account.get_trades(symbol=symbol, limit=limit)

    # Account.get_trades() 返回 Dict 列表，不是 Trade 对象
    return [
        TradeResponse(
            trade_id=t["trade_id"],
            symbol=t["symbol"],
            side=t["side"],
            shares=t["shares"],
            price=float(t["price"]),
            amount=float(t["amount"]),
            commission=float(t["commission"]),
            stamp_duty=float(t.get("stamp_duty", 0)),
            slippage=float(t.get("slippage", 0)),
            total_cost=float(t["amount"]) + float(t["commission"]) + float(t.get("stamp_duty", 0)),
            pnl=None,  # 数据库中不存储 pnl
            survival_level=None,
            market_regime=None,
            timestamp=t["timestamp"],
        )
        for t in trades
    ]


@router.get("/trades/summary")
async def get_trades_summary():
    """
    获取交易汇总

    Returns:
        交易汇总信息
    """
    account = get_account()
    trades = account.get_trades(limit=10000)  # 获取所有交易

    # trades 是 Dict 列表
    buy_trades = [t for t in trades if t["side"] == "buy"]
    sell_trades = [t for t in trades if t["side"] == "sell"]

    buy_amount = sum(t["amount"] for t in buy_trades)
    sell_amount = sum(t["amount"] for t in sell_trades)
    total_commission = sum(t["commission"] for t in trades)
    total_stamp_duty = sum(t.get("stamp_duty", 0) for t in trades)

    return {
        "total_trades": len(trades),
        "buy_trades": len(buy_trades),
        "sell_trades": len(sell_trades),
        "buy_amount": buy_amount,
        "sell_amount": sell_amount,
        "total_commission": total_commission,
        "total_stamp_duty": total_stamp_duty,
        "total_fees": total_commission + total_stamp_duty,
    }


# ==================== 盈亏分析 API ====================

@router.get("/performance")
async def get_performance():
    """
    获取账户性能指标

    Returns:
        性能指标
    """
    account = get_account()
    info = account.get_account_info()

    # 获取交易记录
    # 注意：数据库中不存储 pnl，所以无法计算准确的胜率
    trades = account.get_trades(limit=10000)
    buy_trades = [t for t in trades if t["side"] == "buy"]
    sell_trades = [t for t in trades if t["side"] == "sell"]

    # 简化的性能指标（不含胜率）
    return {
        "total_value": info["total_value"],
        "cash": info["cash"],
        "position_value": info["position_value"],
        "profit": info.get("profit_loss", 0.0),
        "profit_rate": info.get("profit_loss_ratio", 0.0),
        "total_trades": len(trades),
        "buy_trades": len(buy_trades),
        "sell_trades": len(sell_trades),
        "note": "胜率数据需要基于持仓盈亏计算，当前版本仅提供基础指标",
    }