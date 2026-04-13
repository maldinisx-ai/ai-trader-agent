"""
策略相关 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from src.strategy import get_strategy_manager, Strategy

router = APIRouter()


class StrategyResponse(BaseModel):
    """策略响应模型"""
    name: str
    display_name: str
    description: str
    category: str
    default_active: bool
    enabled: bool
    default_priority: int
    aliases: List[str]
    required_tools: List[str]


class StrategyUpdateRequest(BaseModel):
    """策略更新请求"""
    enabled: bool


@router.get("/", response_model=List[StrategyResponse])
async def list_strategies(category: Optional[str] = None):
    """
    获取所有策略列表

    Args:
        category: 可选，按类别筛选

    Returns:
        策略列表
    """
    manager = get_strategy_manager()
    strategies = manager.list_strategies(category=category)

    return [
        StrategyResponse(
            name=s.name,
            display_name=s.display_name,
            description=s.description,
            category=s.category,
            default_active=s.default_active,
            enabled=s.enabled,
            default_priority=s.default_priority,
            aliases=s.aliases,
            required_tools=s.required_tools,
        )
        for s in strategies
    ]


@router.get("/{strategy_name}", response_model=StrategyResponse)
async def get_strategy(strategy_name: str):
    """
    获取单个策略详情

    Args:
        strategy_name: 策略名称

    Returns:
        策略详情
    """
    manager = get_strategy_manager()
    strategy = manager.get_strategy(strategy_name)

    if not strategy:
        raise HTTPException(status_code=404, detail=f"策略不存在: {strategy_name}")

    return StrategyResponse(
        name=strategy.name,
        display_name=strategy.display_name,
        description=strategy.description,
        category=strategy.category,
        default_active=strategy.default_active,
        enabled=strategy.enabled,
        default_priority=strategy.default_priority,
        aliases=strategy.aliases,
        required_tools=strategy.required_tools,
    )


@router.post("/{strategy_name}", response_model=StrategyResponse)
async def update_strategy(strategy_name: str, request: StrategyUpdateRequest):
    """
    更新策略状态

    Args:
        strategy_name: 策略名称
        request: 更新请求

    Returns:
        更新后的策略
    """
    manager = get_strategy_manager()
    strategy = manager.get_strategy(strategy_name)

    if not strategy:
        raise HTTPException(status_code=404, detail=f"策略不存在: {strategy_name}")

    # 更新状态
    if request.enabled:
        manager.activate([strategy_name])
    else:
        strategy.enabled = False

    # 重新获取更新后的策略
    strategy = manager.get_strategy(strategy_name)

    return StrategyResponse(
        name=strategy.name,
        display_name=strategy.display_name,
        description=strategy.description,
        category=strategy.category,
        default_active=strategy.default_active,
        enabled=strategy.enabled,
        default_priority=strategy.default_priority,
        aliases=strategy.aliases,
        required_tools=strategy.required_tools,
    )


@router.post("/activate")
async def activate_strategies(strategy_names: List[str]):
    """
    批量激活策略

    Args:
        strategy_names: 策略名称列表

    Returns:
        激活的策略列表
    """
    manager = get_strategy_manager()
    activated = manager.activate(strategy_names)

    return {
        "activated": activated,
        "count": len(activated),
    }


@router.post("/deactivate-all")
async def deactivate_all_strategies():
    """
    停用所有策略

    Returns:
        操作结果
    """
    manager = get_strategy_manager()
    manager.deactivate_all()

    return {"status": "ok", "message": "所有策略已停用"}


@router.get("/active", response_model=List[StrategyResponse])
async def get_active_strategies():
    """
    获取所有已激活的策略

    Returns:
        已激活的策略列表
    """
    manager = get_strategy_manager()
    strategies = manager.get_active_strategies()

    return [
        StrategyResponse(
            name=s.name,
            display_name=s.display_name,
            description=s.description,
            category=s.category,
            default_active=s.default_active,
            enabled=s.enabled,
            default_priority=s.default_priority,
            aliases=s.aliases,
            required_tools=s.required_tools,
        )
        for s in strategies
    ]


@router.get("/instructions")
async def get_strategy_instructions():
    """
    获取已激活策略的指令文本

    Returns:
        策略指令文本
    """
    manager = get_strategy_manager()
    instructions = manager.get_strategy_instructions()

    return {
        "instructions": instructions,
        "active_count": len(manager.get_active_strategies()),
    }
