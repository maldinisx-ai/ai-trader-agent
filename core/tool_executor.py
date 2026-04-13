# -*- coding: utf-8 -*-
"""
工具执行器

管理和执行各种工具，包括参数校验、执行调度、错误处理。
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Dict, Any, Optional, List, Type
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from .schemas import ToolResult, ToolCall


# ============================================
# 日志配置
# ============================================

logger = logging.getLogger(__name__)


# ============================================
# 类型定义
# ============================================

T = TypeVar('T')


# ============================================
# 工具基类
# ============================================

class Tool(ABC):
    """
    工具基类

    所有工具必须继承此类并实现 execute 方法。
    """

    def __init__(self):
        """初始化工具"""
        self._call_count = 0
        self._last_called: Optional[datetime] = None

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        ...

    @property
    @abstractmethod
    def parameters_schema(self) -> Dict[str, Any]:
        """
        参数模式（JSON Schema 格式）

        用于参数校验和提示给模型
        """
        ...

    @property
    def call_count(self) -> int:
        """调用次数"""
        return self._call_count

    @property
    def last_called(self) -> Optional[datetime]:
        """最后调用时间"""
        return self._last_called

    async def execute(self, **kwargs) -> ToolResult:
        """
        执行工具

        Args:
            **kwargs: 工具参数

        Returns:
            ToolResult[T]: 执行结果
        """
        self._call_count += 1
        self._last_called = datetime.now()

        start_time = datetime.now()

        try:
            # 参数校验
            validation_error = self._validate_parameters(kwargs)
            if validation_error:
                return ToolResult(
                    success=False,
                    error=f"参数校验失败: {validation_error}",
                    execution_time=0.0,
                )

            # 执行工具逻辑
            result = await self._execute(**kwargs)

            execution_time = (datetime.now() - start_time).total_seconds()

            return ToolResult(
                success=True,
                data=result,
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"[Tool] {self.name} 执行失败: {e}", exc_info=True)

            return ToolResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    def _validate_parameters(self, params: Dict[str, Any]) -> Optional[str]:
        """
        校验参数

        Args:
            params: 参数字典

        Returns:
            Optional[str]: 错误信息，None 表示校验通过
        """
        schema = self.parameters_schema

        # 检查必需参数
        required = schema.get("required", [])
        for param_name in required:
            if param_name not in params:
                return f"缺少必需参数: {param_name}"

        # 检查参数类型
        properties = schema.get("properties", {})
        for param_name, param_value in params.items():
            if param_name in properties:
                param_schema = properties[param_name]
                expected_type = param_schema.get("type")

                if expected_type == "string" and not isinstance(param_value, str):
                    return f"参数 {param_name} 应为字符串"
                elif expected_type == "number" and not isinstance(param_value, (int, float)):
                    return f"参数 {param_name} 应为数字"
                elif expected_type == "integer" and not isinstance(param_value, int):
                    return f"参数 {param_name} 应为整数"
                elif expected_type == "array" and not isinstance(param_value, list):
                    return f"参数 {param_name} 应为数组"

        return None

    @abstractmethod
    async def _execute(self, **kwargs) -> Any:
        """
        实际执行逻辑（子类实现）

        Args:
            **kwargs: 工具参数

        Returns:
            Any: 执行结果
        """
        ...

    def get_info(self) -> Dict[str, Any]:
        """
        获取工具信息

        Returns:
            Dict[str, Any]: 工具信息
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters_schema,
            "call_count": self._call_count,
            "last_called": self._last_called.isoformat() if self._last_called else None,
        }


# ============================================
# 工具执行器
# ============================================

class ToolExecutor:
    """
    工具执行器

    管理工具注册、查找、执行。
    """

    def __init__(self):
        """初始化工具执行器"""
        self._tools: Dict[str, Tool] = {}
        self._execution_history: List[Dict[str, Any]] = []

    def register(self, tool: Tool) -> None:
        """
        注册工具

        Args:
            tool: 工具实例
        """
        if tool.name in self._tools:
            logger.warning(f"[ToolExecutor] 工具 {tool.name} 已存在，将被覆盖")

        self._tools[tool.name] = tool
        logger.info(f"[ToolExecutor] 已注册工具: {tool.name}")

    def unregister(self, tool_name: str) -> None:
        """
        注销工具

        Args:
            tool_name: 工具名称
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            logger.info(f"[ToolExecutor] 已注销工具: {tool_name}")

    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """
        获取工具

        Args:
            tool_name: 工具名称

        Returns:
            Optional[Tool]: 工具实例，不存在返回 None
        """
        return self._tools.get(tool_name)

    def list_tools(self) -> List[str]:
        """
        列出所有已注册工具名称

        Returns:
            List[str]: 工具名称列表
        """
        return list(self._tools.keys())

    def get_tools_info(self) -> List[Dict[str, Any]]:
        """
        获取所有工具信息

        Returns:
            List[Dict[str, Any]]: 工具信息列表
        """
        return [tool.get_info() for tool in self._tools.values()]

    async def execute(
        self,
        tool_name: str,
        **kwargs
    ) -> ToolResult:
        """
        执行工具

        Args:
            tool_name: 工具名称
            **kwargs: 工具参数

        Returns:
            ToolResult: 执行结果
        """
        tool = self.get_tool(tool_name)

        if tool is None:
            logger.error(f"[ToolExecutor] 工具不存在: {tool_name}")
            return ToolResult(
                success=False,
                error=f"工具不存在: {tool_name}",
                execution_time=0.0,
            )

        # 记录执行历史
        call_id = str(uuid4())
        start_time = datetime.now()

        # 执行工具
        result = await tool.execute(**kwargs)

        # 记录历史
        self._execution_history.append({
            "call_id": call_id,
            "tool_name": tool_name,
            "parameters": kwargs,
            "success": result.success,
            "error": result.error,
            "timestamp": start_time.isoformat(),
        })

        return result

    async def execute_batch(
        self,
        calls: List[Dict[str, Any]]
    ) -> List[ToolResult]:
        """
        批量执行工具

        Args:
            calls: 调用列表，每个元素包含 tool_name 和 parameters

        Returns:
            List[ToolResult]: 执行结果列表
        """
        tasks = []
        for call in calls:
            tool_name = call.get("tool_name")
            params = call.get("parameters", {})
            tasks.append(self.execute(tool_name, **params))

        return await asyncio.gather(*tasks)

    def get_execution_history(
        self,
        tool_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取执行历史

        Args:
            tool_name: 工具名称（可选，过滤特定工具）
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 执行历史列表
        """
        history = self._execution_history

        if tool_name:
            history = [h for h in history if h["tool_name"] == tool_name]

        return history[-limit:]


# ============================================
# 工具装饰器
# ============================================

def register_tool(executor: ToolExecutor):
    """
    工具注册装饰器

    用法:
        @register_tool(executor)
        class MyTool(Tool):
            ...
    """
    def decorator(tool_class: Type[Tool]) -> Type[Tool]:
        tool_instance = tool_class()
        executor.register(tool_instance)
        return tool_class

    return decorator
