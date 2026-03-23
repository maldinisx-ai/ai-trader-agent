# -*- coding: utf-8 -*-
"""
核心数据模型

使用 Pydantic 定义所有核心数据模型，确保类型安全和数据验证。
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
from enum import Enum, IntEnum
from decimal import Decimal


# ============================================
# 枚举定义
# ============================================

class SurvivalLevel(str, Enum):
    """生存等级"""
    NORMAL = "normal"
    LOW_COMPUTE = "low_compute"
    CRITICAL = "critical"
    DEAD = "dead"


class MarketRegime(str, Enum):
    """市场状态"""
    BULL = "bull"          # 牛市
    BEAR = "bear"          # 熊市
    SIDEWAYS = "sideways"  # 震荡


class OrderSide(str, Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """订单类型"""
    MARKET = "market"  # 市价单
    LIMIT = "limit"    # 限价单


class OrderStatus(str, Enum):
    """订单状态"""
    PENDING = "pending"            # 待成交
    FILLED = "filled"              # 已成交
    PARTIALLY_FILLED = "partially_filled"  # 部分成交
    CANCELLED = "cancelled"        # 已撤销
    REJECTED = "rejected"          # 已拒绝


class PolicyPriority(IntEnum):
    """风控规则优先级"""
    P0_FUND_CHECK = 0
    P1_CIRCUIT_BREAKER = 1
    P2_BLACKLIST = 2
    P3_TRADING_RULES = 3
    P4_POSITION_LIMIT = 4
    P5_COOLDOWN = 5
    P6_DAILY_LIMIT = 6


class ErrorType(str, Enum):
    """错误类型（用于反思记忆）"""
    ENTRY = "entry"        # 入场错误
    EXIT = "exit"          # 出场错误
    POSITION = "position"  # 仓位错误
    TIMING = "timing"      # 时机错误


# ============================================
# 数据模型
# ============================================

class QuoteData(BaseModel):
    """行情数据"""
    symbol: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    price: float = Field(..., gt=0, description="最新价")
    change: float = Field(..., ge=-11, le=11, description="涨跌幅(%)")
    volume: int = Field(..., ge=0, description="成交量(手)")
    amount: float = Field(..., ge=0, description="成交额(元)")
    high: Optional[float] = Field(None, description="最高价")
    low: Optional[float] = Field(None, description="最低价")
    open: Optional[float] = Field(None, description="开盘价")
    upper_limit: Optional[float] = Field(None, description="涨停价")
    lower_limit: Optional[float] = Field(None, description="跌停价")
    is_suspended: bool = Field(False, description="是否停牌")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")


class Order(BaseModel):
    """订单"""
    order_id: str = Field(..., description="订单ID")
    symbol: str = Field(..., description="股票代码")
    side: OrderSide = Field(..., description="买卖方向")
    quantity: int = Field(..., gt=0, multiple_of=100, description="数量（股）")
    price: Optional[float] = Field(None, gt=0, description="委托价格（限价单）")
    order_type: OrderType = Field(..., description="订单类型")
    status: OrderStatus = Field(OrderStatus.PENDING, description="订单状态")
    filled_quantity: int = Field(0, ge=0, description="已成交数量")
    filled_price: Optional[float] = Field(None, description="成交价格")
    reject_reason: Optional[str] = Field(None, description="拒绝原因")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    filled_at: Optional[datetime] = Field(None, description="成交时间")

    @property
    def estimated_amount(self) -> float:
        """预估金额（含手续费）"""
        if self.price is None:
            return 0.0
        return self.quantity * self.price

    @property
    def is_fully_filled(self) -> bool:
        """是否完全成交"""
        return self.status == OrderStatus.FILLED

    @property
    def is_buy(self) -> bool:
        """是否买入"""
        return self.side == OrderSide.BUY


class Position(BaseModel):
    """持仓"""
    symbol: str = Field(..., description="股票代码")
    shares: int = Field(..., ge=0, description="持股数量")
    avg_cost: float = Field(..., gt=0, description="平均成本")
    current_price: float = Field(..., gt=0, description="当前价格")
    opened_at: datetime = Field(..., description="建仓时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    @property
    def market_value(self) -> float:
        """市值"""
        return self.shares * self.current_price

    @property
    def cost_value(self) -> float:
        """成本"""
        return self.shares * self.avg_cost

    @property
    def pnl(self) -> float:
        """浮动盈亏"""
        return (self.current_price - self.avg_cost) * self.shares

    @property
    def pnl_ratio(self) -> float:
        """盈亏比例"""
        return (self.current_price - self.avg_cost) / self.avg_cost


class Trade(BaseModel):
    """交易记录"""
    trade_id: str = Field(..., description="交易ID")
    symbol: str = Field(..., description="股票代码")
    side: OrderSide = Field(..., description="买卖方向")
    shares: int = Field(..., gt=0, description="成交数量")
    price: float = Field(..., gt=0, description="成交价格")
    amount: float = Field(..., gt=0, description="成交金额")
    commission: float = Field(0, ge=0, description="佣金")
    stamp_duty: float = Field(0, ge=0, description="印花税")
    slippage: float = Field(0, ge=0, description="滑点")
    timestamp: datetime = Field(..., description="成交时间")
    order_id: Optional[str] = Field(None, description="关联订单ID")

    # 决策相关
    survival_level: Optional[SurvivalLevel] = Field(None, description="生存等级")
    market_regime: Optional[MarketRegime] = Field(None, description="市场状态")
    model_used: Optional[str] = Field(None, description="使用的模型")
    decision_chain: Optional[Dict[str, Any]] = Field(None, description="决策链路")

    @property
    def total_cost(self) -> float:
        """总成本（含手续费）"""
        return self.amount + self.commission + self.stamp_duty + self.slippage


class AgentResponse(BaseModel):
    """Agent 响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    thought_process: Optional[str] = Field(None, description="思考过程")
    actions_taken: List[str] = Field(default_factory=list, description="执行的操作")
    final_result: Optional[Dict[str, Any]] = Field(None, description="最终结果")
    execution_time: float = Field(..., gt=0, description="执行时间（秒）")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")


class Decision(BaseModel):
    """决策"""
    action: Literal["buy", "sell", "hold", "wait"] = Field(..., description="动作")
    symbol: Optional[str] = Field(None, description="股票代码")
    quantity: Optional[int] = Field(None, gt=0, multiple_of=100, description="数量")
    price: Optional[float] = Field(None, gt=0, description="价格")
    confidence: float = Field(..., ge=0, le=1, description="置信度(0-1)")
    reasoning: str = Field(..., description="推理过程")
    tools_to_use: List[str] = Field(default_factory=list, description="需要使用的工具")
    is_final: bool = Field(False, description="是否为最终决策")


class PolicyResult(BaseModel):
    """风控结果"""
    allowed: bool = Field(..., description="是否允许")
    reason: Optional[str] = Field(None, description="拒绝原因")
    policy: Optional[str] = Field(None, description="触发的策略名称")
    priority: Optional[PolicyPriority] = Field(None, description="优先级")


class AgentContext(BaseModel):
    """Agent 上下文"""
    user_input: str = Field(..., description="用户输入")
    current_cash: float = Field(..., ge=0, description="当前资金")
    total_value: float = Field(..., ge=0, description="总资产")
    initial_cash: float = Field(..., gt=0, description="初始资金")
    positions: List[Position] = Field(default_factory=list, description="当前持仓")
    survival_level: SurvivalLevel = Field(SurvivalLevel.NORMAL, description="生存等级")
    market_regime: MarketRegime = Field(MarketRegime.SIDEWAYS, description="市场状态")
    max_position_ratio: float = Field(0.30, ge=0, le=1, description="最大仓位比例")
    trading_enabled: bool = Field(True, description="是否允许交易")

    @property
    def drawdown(self) -> float:
        """回撤率"""
        if self.total_value >= self.initial_cash:
            return 0.0
        return (self.initial_cash - self.total_value) / self.initial_cash

    @property
    def position_value(self) -> float:
        """持仓市值"""
        return sum(p.market_value for p in self.positions)

    @property
    def cash_ratio(self) -> float:
        """现金比例"""
        return self.current_cash / self.total_value if self.total_value > 0 else 0


# ============================================
# 记忆相关模型
# ============================================

class ReflectionRecord(BaseModel):
    """反思记录"""
    reflection_id: str = Field(..., description="反思ID")
    trade_id: str = Field(..., description="关联交易ID")
    loss_amount: float = Field(..., description="亏损金额")
    loss_ratio: float = Field(..., description="亏损比例")
    error_type: ErrorType = Field(..., description="错误类型")
    analysis: str = Field(..., description="分析内容")
    lesson: str = Field(..., description="经验教训")
    avoid_action: str = Field(..., description="避免措施")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")


class MarketState(BaseModel):
    """市场状态"""
    regime: MarketRegime = Field(..., description="市场状态")
    confidence: float = Field(..., ge=0, le=1, description="置信度")
    max_position_ratio: float = Field(..., ge=0, le=1, description="建议最大仓位")
    indicators: Dict[str, float] = Field(default_factory=dict, description="技术指标")
    timestamp: datetime = Field(default_factory=datetime.now, description="更新时间")


class SurvivalState(BaseModel):
    """生存状态"""
    level: SurvivalLevel = Field(..., description="生存等级")
    drawdown: float = Field(..., ge=0, description="当前回撤率")
    max_position: float = Field(..., ge=0, le=1, description="最大仓位")
    trading_interval: int = Field(..., ge=0, description="交易间隔（秒）")
    last_update: datetime = Field(default_factory=datetime.now, description="更新时间")


# ============================================
# 工具相关模型
# ============================================

class ToolResult(BaseModel):
    """工具执行结果"""
    success: bool = Field(..., description="是否成功")
    data: Optional[Any] = Field(None, description="返回数据")
    error: Optional[str] = Field(None, description="错误信息")
    execution_time: float = Field(0, ge=0, description="执行时间（秒）")


class ToolCall(BaseModel):
    """工具调用"""
    name: str = Field(..., description="工具名称")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="参数")
    call_id: Optional[str] = Field(None, description="调用ID")


# ============================================
# 撮合相关模型
# ============================================

class MatchResult(BaseModel):
    """撮合结果"""
    order: Order = Field(..., description="原始订单")
    filled_quantity: int = Field(..., ge=0, description="成交数量")
    filled_price: Optional[float] = Field(None, description="成交价格")
    fully_filled: bool = Field(..., description="是否完全成交")
    reason: str = Field(..., description="撮合结果说明")
