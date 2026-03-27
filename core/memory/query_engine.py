# -*- coding: utf-8 -*-
"""
记忆查询引擎

提供统一的记忆查询接口，整合交易历史和反思记录。
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from core.memory.trade_history import TradeHistory
from core.memory.reflection_store import ReflectionStore
from core.schemas import (
    OrderSide,
    SurvivalLevel,
    MarketRegime,
    ErrorType,
)


logger = logging.getLogger(__name__)


# ============================================
# 记忆查询接口
# ============================================

class MemoryQuery:
    """
    记忆查询引擎

    提供统一的记忆查询接口，支持交易历史和反思记录的组合查询。
    """

    def __init__(
        self,
        trade_history: Optional[TradeHistory] = None,
        reflection_store: Optional[ReflectionStore] = None,
        db_path: str = "data/trading.db",
    ):
        """
        初始化记忆查询引擎

        Args:
            trade_history: 交易历史存储
            reflection_store: 反思记录存储
            db_path: 数据库路径（用于创建默认存储）
        """
        self.trade_history = trade_history or TradeHistory(db_path)
        self.reflection_store = reflection_store or ReflectionStore(db_path)

    # ============================================
    # 交易历史查询
    # ============================================

    def get_trades(
        self,
        limit: int = 100,
        symbol: Optional[str] = None,
        side: Optional[OrderSide] = None,
        survival_level: Optional[SurvivalLevel] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        查询交易记录

        Args:
            limit: 返回数量限制
            symbol: 股票代码过滤
            side: 买卖方向过滤
            survival_level: 生存等级过滤
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            List[Dict[str, Any]]: 交易记录列表
        """
        return self.trade_history.get_trades(
            limit=limit,
            symbol=symbol,
            side=side,
            survival_level=survival_level,
            start_time=start_time,
            end_time=end_time,
        )

    def get_trade_with_reflection(
        self,
        trade_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        获取交易及其关联的反思记录

        Args:
            trade_id: 交易ID

        Returns:
            Optional[Dict[str, Any]]: 包含交易和反思的字典
        """
        trade = self.trade_history.get_trade(trade_id)
        if trade is None:
            return None

        reflections = self.reflection_store.get_reflections_by_trade_id(trade_id)

        return {
            "trade": trade,
            "reflections": reflections,
        }

    def get_trades_with_reflections(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取交易及其关联的反思记录列表

        Args:
            symbol: 股票代码（可选）
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 包含交易和反思的字典列表
        """
        trades = self.trade_history.get_trades(
            limit=limit,
            symbol=symbol,
        )

        result = []
        for trade in trades:
            reflections = self.reflection_store.get_reflections_by_trade_id(trade["trade_id"])
            result.append({
                "trade": trade,
                "reflections": reflections,
            })

        return result

    # ============================================
    # 反思记录查询
    # ============================================

    def get_reflections(
        self,
        limit: int = 100,
        error_type: Optional[ErrorType] = None,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        查询反思记录

        Args:
            limit: 返回数量限制
            error_type: 错误类型过滤
            symbol: 股票代码过滤

        Returns:
            List[Dict[str, Any]]: 反思记录列表
        """
        if error_type:
            return self.reflection_store.get_reflections_by_error_type(error_type, limit)
        elif symbol:
            return self.reflection_store.get_reflections_by_symbol(symbol, limit)
        else:
            return self.reflection_store.get_all_reflections(limit)

    def get_lessons_for_error_type(self, error_type: ErrorType) -> List[str]:
        """
        获取指定错误类型的所有教训

        Args:
            error_type: 错误类型

        Returns:
            List[str]: 教训列表
        """
        return self.reflection_store.get_lessons_by_error_type(error_type)

    def get_avoid_actions_for_error_type(self, error_type: ErrorType) -> List[str]:
        """
        获取指定错误类型的所有避免措施

        Args:
            error_type: 错误类型

        Returns:
            List[str]: 避免措施列表
        """
        return self.reflection_store.get_avoid_actions_by_error_type(error_type)

    # ============================================
    # 智能查询
    # ============================================

    def get_loss_pattern_summary(self, hours: int = 168) -> Dict[str, Any]:
        """
        获取亏损模式总结

        Args:
            hours: 时间范围（小时数，默认168=7天）

        Returns:
            Dict[str, Any]: 亏损模式总结
        """
        start_time = datetime.now() - timedelta(hours=hours)

        # 获取亏损交易
        loss_trades = [
            t for t in self.trade_history.get_trades(
                start_time=start_time,
            )
            if t.get("pnl", 0) < 0
        ]

        # 按错误类型分组反思
        error_summary = {}
        for trade in loss_trades:
            reflections = self.reflection_store.get_reflections_by_trade_id(trade["trade_id"])
            for ref in reflections:
                error_type = ref["error_type"]
                if error_type not in error_summary:
                    error_summary[error_type] = {
                        "count": 0,
                        "total_loss": 0.0,
                        "lessons": set(),
                        "avoid_actions": set(),
                    }
                error_summary[error_type]["count"] += 1
                error_summary[error_type]["total_loss"] += abs(trade.get("pnl", 0))
                error_summary[error_type]["lessons"].add(ref["lesson"])
                error_summary[error_type]["avoid_actions"].add(ref["avoid_action"])

        # 转换为最终格式
        result = {
            "total_loss_trades": len(loss_trades),
            "total_loss_amount": sum(abs(t.get("pnl", 0)) for t in loss_trades),
            "by_error_type": {},
        }

        for error_type, data in error_summary.items():
            result["by_error_type"][error_type] = {
                "count": data["count"],
                "total_loss": data["total_loss"],
                "avg_loss": data["total_loss"] / data["count"] if data["count"] > 0 else 0,
                "lessons": list(data["lessons"]),
                "avoid_actions": list(data["avoid_actions"]),
            }

        return result

    def get_symbol_performance(self, symbol: str) -> Dict[str, Any]:
        """
        获取指定股票的交易表现

        Args:
            symbol: 股票代码

        Returns:
            Dict[str, Any]: 股票表现总结
        """
        trades = self.trade_history.get_trades_by_symbol(symbol, limit=1000)

        if not trades:
            return {
                "symbol": symbol,
                "total_trades": 0,
                "total_pnl": 0.0,
            }

        buy_trades = [t for t in trades if t["side"] == "buy"]
        sell_trades = [t for t in trades if t["side"] == "sell"]

        # 计算盈亏
        pnl_values = [t.get("pnl", 0) for t in trades if t.get("pnl") is not None]
        win_trades = [p for p in pnl_values if p > 0]
        loss_trades = [p for p in pnl_values if p < 0]

        # 获取相关反思
        all_reflections = []
        for trade in trades:
            reflections = self.reflection_store.get_reflections_by_trade_id(trade["trade_id"])
            all_reflections.extend(reflections)

        # 按错误类型统计
        error_types = {}
        for ref in all_reflections:
            error_type = ref["error_type"]
            error_types[error_type] = error_types.get(error_type, 0) + 1

        return {
            "symbol": symbol,
            "total_trades": len(trades),
            "buy_trades": len(buy_trades),
            "sell_trades": len(sell_trades),
            "total_pnl": sum(pnl_values),
            "win_trades": len(win_trades),
            "loss_trades": len(loss_trades),
            "win_rate": len(win_trades) / len(pnl_values) if pnl_values else 0,
            "avg_pnl": sum(pnl_values) / len(pnl_values) if pnl_values else 0,
            "max_profit": max(win_trades) if win_trades else 0,
            "max_loss": min(loss_trades) if loss_trades else 0,
            "reflection_count": len(all_reflections),
            "error_types": error_types,
        }

    def get_recent_activity(self, hours: int = 24) -> Dict[str, Any]:
        """
        获取最近活动总结

        Args:
            hours: 时间范围（小时数）

        Returns:
            Dict[str, Any]: 活动总结
        """
        trades = self.trade_history.get_recent_trades(hours=hours)
        reflections = self.reflection_store.get_recent_reflections(hours=hours)

        # 交易统计
        buy_count = sum(1 for t in trades if t["side"] == "buy")
        sell_count = sum(1 for t in trades if t["side"] == "sell")

        # 盈亏统计
        pnl_values = [t.get("pnl", 0) for t in trades if t.get("pnl") is not None]

        # 涉及股票
        symbols = set(t["symbol"] for t in trades)

        return {
            "time_range_hours": hours,
            "total_trades": len(trades),
            "buy_trades": buy_count,
            "sell_trades": sell_count,
            "total_pnl": sum(pnl_values),
            "total_reflections": len(reflections),
            "unique_symbols": len(symbols),
            "symbols": list(symbols),
        }

    def get_recommendations(
        self,
        symbol: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        基于反思记录获取交易建议

        Args:
            symbol: 股票代码（可选）
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 建议列表
        """
        # 获取最近的反思记录
        if symbol:
            reflections = self.reflection_store.get_reflections_by_symbol(symbol, limit=limit * 2)
        else:
            reflections = self.reflection_store.get_recent_reflections(hours=168, limit=limit * 2)

        # 按错误类型分组并生成建议
        recommendations = []
        for reflection in reflections:
            recommendations.append({
                "type": "avoid",
                "error_type": reflection["error_type"],
                "action": reflection["avoid_action"],
                "lesson": reflection["lesson"],
                "trade_id": reflection["trade_id"],
                "timestamp": reflection["timestamp"],
            })

        # 按错误类型去重，返回最近的建议
        seen = set()
        unique_recommendations = []
        for rec in reversed(recommendations):
            key = (rec["error_type"], rec["action"])
            if key not in seen and len(unique_recommendations) < limit:
                seen.add(key)
                unique_recommendations.append(rec)

        unique_recommendations.reverse()
        return unique_recommendations

    # ============================================
    # 统计查询
    # ============================================

    def get_full_statistics(self) -> Dict[str, Any]:
        """
        获取完整统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        trade_stats = self.trade_history.get_statistics()
        reflection_stats = self.reflection_store.get_error_type_statistics()

        return {
            "trades": trade_stats,
            "reflections": reflection_stats,
        }

    # ============================================
    # 资源管理
    # ============================================

    def close(self) -> None:
        """关闭所有连接"""
        self.trade_history.close()
        self.reflection_store.close()
        logger.debug("[MemoryQuery] 所有连接已关闭")