"""
系统相关 API
"""
import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any, Optional

from src.config import get_config

logger = logging.getLogger(__name__)
router = APIRouter()

# 获取配置
config = get_config()


class SystemInfoResponse(BaseModel):
    """系统信息响应"""
    version: str
    name: str
    description: str
    features: Dict[str, Any]


@router.get("/info", response_model=SystemInfoResponse)
async def get_system_info():
    """
    获取系统信息

    Returns:
        系统信息
    """
    return SystemInfoResponse(
        version="0.4.0",
        name="AI Trader Agent",
        description="智能交易系统 - 基于 ReAct 框架的自主交易代理",
        features={
            "strategies": True,
            "web_ui": True,
            "api": True,
            "data_sources": ["akshare", "efinance", "pytdx"],
            "agent_features": {
                "react_loop": True,
                "dual_model": True,
                "risk_control": True,
                "market_regime": True,
                "reflection": True,
                "memory": True,
            },
            "backtesting": True,
            "live_trading": True,
            "monitoring": True,
        },
    )


@router.get("/config")
async def get_system_config():
    """
    获取系统配置（不含敏感信息）

    Returns:
        系统配置
    """
    # 获取数据目录信息
    data_dir = Path(config.data_dir)

    # 计算数据文件统计
    stock_files = 0
    total_size = 0

    if data_dir.exists():
        for ext in ['*.csv', '*.json', '*.db']:
            for f in data_dir.rglob(ext):
                stock_files += 1
                total_size += f.stat().st_size

    # 转换大小为 MB
    total_size_mb = round(total_size / 1024 / 1024, 2)

    return {
        "data_dir": str(data_dir),
        "log_dir": str(config.log_dir),
        "strategy_dir": "src/strategies",
        "statistics": {
            "data_files": stock_files,
            "total_size_mb": total_size_mb,
        },
        "available_data_sources": {
            "akshare": True,
            "efinance": True,
            "pytdx": True,
        },
    }


@router.get("/health")
async def health_check():
    """
    健康检查

    Returns:
        健康状态
    """
    # 检查数据目录
    data_dir = Path(config.data_dir)
    data_accessible = data_dir.exists() and data_dir.is_dir()

    # 检查数据库文件
    db_path = data_dir / "trading.db"
    db_accessible = db_path.exists()

    # 检查配置文件
    config_valid = config is not None

    # 总体状态
    overall_status = "healthy" if all([data_accessible, config_valid]) else "degraded"

    return {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "checks": {
            "data_directory": {
                "status": "ok" if data_accessible else "error",
                "path": str(data_dir),
            },
            "database": {
                "status": "ok" if db_accessible else "warning",
                "path": str(db_path),
                "message": "数据库存在" if db_accessible else "数据库尚未初始化",
            },
            "configuration": {
                "status": "ok" if config_valid else "error",
            },
        },
        "uptime_seconds": None,  # 可选：记录服务启动时间
    }


@router.get("/statistics")
async def get_system_statistics():
    """
    获取系统统计信息

    Returns:
        统计数据
    """
    data_dir = Path(config.data_dir)
    stats = {
        "data_files": {
            "stocks": 0,
            "indices": 0,
            "sectors": 0,
        },
        "database_records": {},
        "cache_status": {},
    }

    # 统计各类数据文件
    if data_dir.exists():
        stocks_dir = data_dir / "stocks"
        if stocks_dir.exists():
            stats["data_files"]["stocks"] = len(list(stocks_dir.glob("*.csv")))

        klines_dir = data_dir / "klines"
        if klines_dir.exists():
            stats["data_files"]["stocks"] += len(list(klines_dir.glob("*.csv")))

        index_dir = data_dir / "index"
        if index_dir.exists():
            stats["data_files"]["indices"] = len(list(index_dir.glob("*.csv")))

    # 统计数据库记录
    try:
        import sqlite3
        db_path = data_dir / "trading.db"

        if db_path.exists():
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                # 获取各表的记录数
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()

                for (table_name,) in tables:
                    # Validate table_name against whitelist to prevent SQL injection
                    if not table_name.replace('_', '').isalnum():
                        logger.warning(f"跳过无效表名: {table_name}")
                        continue
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = cursor.fetchone()[0]
                        stats["database_records"][table_name] = count
                    except Exception:
                        pass

    except Exception as e:
        logger.warning(f"获取数据库统计失败: {e}")

    # 检查缓存文件
    cache_files = {
        "stock_names": data_dir / "stock_names.json",
        "sectors": data_dir / "sectors.json",
        "analysis_history": data_dir / "analysis_history.db",
    }

    for name, path in cache_files.items():
        if path.exists():
            # 获取文件修改时间
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            stats["cache_status"][name] = {
                "exists": True,
                "last_update": mtime.isoformat(),
            }
        else:
            stats["cache_status"][name] = {
                "exists": False,
                "last_update": None,
            }

    return stats


@router.post("/cache/refresh")
async def refresh_cache():
    """
    刷新系统缓存

    Returns:
        刷新结果
    """
    results = {}

    # 刷新股票名称缓存
    try:
        from core.stock_name_service import get_stock_name_service
        stock_service = get_stock_name_service(data_dir=config.data_dir)
        count = stock_service.refresh()
        results["stock_names"] = {
            "status": "ok",
            "count": count,
        }
    except Exception as e:
        results["stock_names"] = {
            "status": "error",
            "message": str(e),
        }

    # 刷新行业板块缓存
    try:
        from core.sector_service import get_sector_service
        sector_service = get_sector_service(data_dir=config.data_dir)
        count = sector_service.refresh()
        results["sectors"] = {
            "status": "ok",
            "count": count,
        }
    except Exception as e:
        results["sectors"] = {
            "status": "error",
            "message": str(e),
        }

    return {
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }
