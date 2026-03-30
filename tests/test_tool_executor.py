# -*- coding: utf-8 -*-
"""
测试工具执行器

TDD 流程: RED → GREEN → REFACTOR
"""

import pytest
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock

import core.tool_executor
import core.schemas
from core.schemas import ToolResult
from core.tool_executor import Tool, ToolExecutor, register_tool


class TestTool:
    """测试工具基类"""

    def test_register_tool(self):
        """测试注册工具"""
        executor = ToolExecutor()
        tool = MockTool()

        executor.register(tool)

        assert "mock_tool" in executor.list_tools()
        assert executor.get_tool("mock_tool") == tool

    def test_unregister_tool(self):
        """测试注销工具"""
        executor = ToolExecutor()
        tool = MockTool()

        executor.register(tool)
        assert "mock_tool" in executor.list_tools()

        executor.unregister("mock_tool")
        assert "mock_tool" not in executor.list_tools()

    def test_register_duplicate_tool(self):
        """测试注册重复工具"""
        executor = ToolExecutor()
        tool1 = MockTool()
        tool2 = MockTool()

        executor.register(tool1)
        executor.register(tool2)  # 覆盖

        tools = executor.list_tools()
        assert len(tools) == 1
        assert executor.get_tool("mock_tool") == tool2

    def test_get_tool(self):
        """测试获取工具"""
        executor = ToolExecutor()
        tool = MockTool()

        executor.register(tool)

        result = executor.get_tool("mock_tool")
        assert result == tool

    def test_get_nonexistent_tool(self):
        """测试获取不存在的工具"""
        executor = ToolExecutor()

        result = executor.get_tool("nonexistent")
        assert result is None

    def test_list_tools(self):
        """测试列出工具"""
        executor = ToolExecutor()

        assert executor.list_tools() == []

        executor.register(MockTool())
        assert "mock_tool" in executor.list_tools()

    def test_get_tools_info(self):
        """测试获取工具信息"""
        executor = ToolExecutor()
        tool = MockTool()

        executor.register(tool)

        info_list = executor.get_tools_info()
        assert len(info_list) == 1
        assert info_list[0]["name"] == "mock_tool"
        assert "description" in info_list[0]

    @pytest.mark.asyncio
    async def test_execute_tool(self):
        """测试执行工具"""
        executor = ToolExecutor()
        tool = MockTool()

        executor.register(tool)

        result = await executor.execute("mock_tool", data="test")

        assert result.success is True
        assert result.data == {"result": "test"}

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self):
        """测试执行不存在的工具"""
        executor = ToolExecutor()

        result = await executor.execute("nonexistent")

        assert result.success is False
        assert "工具不存在" in result.error

    @pytest.mark.asyncio
    async def test_execute_batch(self):
        """测试批量执行工具"""
        executor = ToolExecutor()
        executor.register(MockTool())

        calls = [
            {"tool_name": "mock_tool", "parameters": {"data": "call1"}},
            {"tool_name": "mock_tool", "parameters": {"data": "call2"}},
        ]

        results = await executor.execute_batch(calls)

        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is True

    def test_get_execution_history(self):
        """测试获取执行历史"""
        executor = ToolExecutor()
        executor.register(MockTool())

        history = executor.get_execution_history()
        assert history == []

    @pytest.mark.asyncio
    async def test_execution_history_recorded(self):
        """测试执行历史被记录"""
        executor = ToolExecutor()
        executor.register(MockTool())

        await executor.execute("mock_tool", data="test")

        history = executor.get_execution_history()
        assert len(history) == 1
        assert history[0]["tool_name"] == "mock_tool"
        assert history[0]["parameters"] == {"data": "test"}
        assert history[0]["success"] is True

    @pytest.mark.asyncio
    async def test_get_execution_history_filter_by_tool(self):
        """测试按工具名称过滤执行历史"""
        executor = ToolExecutor()
        executor.register(MockTool())

        await executor.execute("mock_tool", data="test1")
        await executor.execute("mock_tool", data="test2")

        history = executor.get_execution_history(tool_name="mock_tool")
        assert len(history) == 2

        history_other = executor.get_execution_history(tool_name="nonexistent")
        assert len(history_other) == 0

    @pytest.mark.asyncio
    async def test_get_execution_history_limit(self):
        """测试执行历史数量限制"""
        executor = ToolExecutor()
        executor.register(MockTool())

        for i in range(5):
            await executor.execute("mock_tool", data=f"test{i}")

        history = executor.get_execution_history(limit=3)
        assert len(history) == 3

    def test_decorator_register_tool(self):
        """测试工具注册装饰器"""
        executor = ToolExecutor()

        @register_tool(executor)
        class TestTool(Tool):
            @property
            def name(self) -> str:
                return "test_tool"

            @property
            def description(self) -> str:
                return "Test tool"

            @property
            def parameters_schema(self) -> Dict[str, Any]:
                return {"type": "object", "properties": {}}

            async def _execute(self, **kwargs) -> Any:
                return {"result": "decorated"}

        assert "test_tool" in executor.list_tools()

    @pytest.mark.asyncio
    async def test_tool_call_count(self):
        """测试工具调用计数"""
        executor = ToolExecutor()
        tool = MockTool()

        assert tool.call_count == 0

        executor.register(tool)

        await executor.execute("mock_tool", data="test1")
        assert tool.call_count == 1

        await executor.execute("mock_tool", data="test2")
        assert tool.call_count == 2

    @pytest.mark.asyncio
    async def test_tool_last_called(self):
        """测试工具最后调用时间"""
        executor = ToolExecutor()
        tool = MockTool()

        executor.register(tool)

        assert tool.last_called is None

        await executor.execute("mock_tool", data="test1")
        first_call = tool.last_called

        await executor.execute("mock_tool", data="test2")
        second_call = tool.last_called

        assert second_call > first_call

    @pytest.mark.asyncio
    async def test_tool_parameters_validation_success(self):
        """测试参数校验成功"""
        executor = ToolExecutor()
        tool = ValidatedTool()

        executor.register(tool)

        result = await executor.execute("validated_tool", required_param="test", number_param=123)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_tool_parameters_validation_missing_required(self):
        """测试参数校验失败 - 缺少必需参数"""
        executor = ToolExecutor()
        tool = ValidatedTool()

        executor.register(tool)

        result = await executor.execute("validated_tool", number_param=123)

        assert result.success is False
        assert "参数校验失败" in result.error
        assert "required_param" in result.error

    @pytest.mark.asyncio
    async def test_tool_parameters_validation_wrong_type(self):
        """测试参数校验失败 - 参数类型错误"""
        executor = ToolExecutor()
        tool = ValidatedTool()

        executor.register(tool)

        result = await executor.execute("validated_tool", required_param="test", number_param="not_a_number")

        assert result.success is False
        assert "参数校验失败" in result.error
        assert "number_param" in result.error

    @pytest.mark.asyncio
    async def test_tool_execution_error_handling(self):
        """测试工具执行异常处理"""
        executor = ToolExecutor()
        tool = FailingTool()

        executor.register(tool)

        result = await executor.execute("failing_tool")

        assert result.success is False
        assert "error" in str(result.error).lower() or "Test error" in result.error

    def test_tool_get_info(self):
        """测试获取工具信息"""
        tool = MockTool()

        info = tool.get_info()

        assert info["name"] == "mock_tool"
        assert info["description"] == "Mock tool for testing"
        assert "parameters" in info
        assert "call_count" in info
        assert "last_called" in info


# 测试用工具类

class MockTool(Tool):
    """模拟工具"""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "Mock tool for testing"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "data": {"type": "string"}
            }
        }

    async def _execute(self, **kwargs) -> Any:
        return {"result": kwargs.get("data", "default")}


class ValidatedTool(Tool):
    """需要参数校验的工具"""

    @property
    def name(self) -> str:
        return "validated_tool"

    @property
    def description(self) -> str:
        return "Tool with parameter validation"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "required": ["required_param"],
            "properties": {
                "required_param": {"type": "string"},
                "number_param": {"type": "number"}
            }
        }

    async def _execute(self, **kwargs) -> Any:
        return {"validated": True, "params": kwargs}


class FailingTool(Tool):
    """会失败的工具"""

    @property
    def name(self) -> str:
        return "failing_tool"

    @property
    def description(self) -> str:
        return "Tool that always fails"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def _execute(self, **kwargs) -> Any:
        raise Exception("Test error")


class TestToolParameterValidationExtended:
    """扩展的参数校验测试"""

    @pytest.mark.asyncio
    async def test_validate_string_type_success(self):
        """测试字符串类型校验成功"""
        executor = ToolExecutor()
        tool = AllTypesTool()
        executor.register(tool)

        result = await executor.execute(
            "all_types_tool",
            string_param="test",
            number_param=123.45,
            integer_param=10,
            array_param=[1, 2, 3]
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_validate_string_type_failure(self):
        """测试字符串类型校验失败"""
        executor = ToolExecutor()
        tool = AllTypesTool()
        executor.register(tool)

        result = await executor.execute(
            "all_types_tool",
            string_param=123,  # 错误：应该是字符串
            number_param=123.45,
            integer_param=10,
            array_param=[1, 2, 3]
        )

        assert result.success is False
        assert "string_param" in result.error
        assert "应为字符串" in result.error

    @pytest.mark.asyncio
    async def test_validate_number_type_with_int(self):
        """测试数字类型接受整数"""
        executor = ToolExecutor()
        tool = AllTypesTool()
        executor.register(tool)

        result = await executor.execute(
            "all_types_tool",
            string_param="test",
            number_param=123,  # 整数应该被接受
            integer_param=10,
            array_param=[1, 2, 3]
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_validate_number_type_failure(self):
        """测试数字类型校验失败"""
        executor = ToolExecutor()
        tool = AllTypesTool()
        executor.register(tool)

        result = await executor.execute(
            "all_types_tool",
            string_param="test",
            number_param="not_number",  # 错误
            integer_param=10,
            array_param=[1, 2, 3]
        )

        assert result.success is False
        assert "number_param" in result.error
        assert "应为数字" in result.error

    @pytest.mark.asyncio
    async def test_validate_integer_type_failure(self):
        """测试整数类型校验失败"""
        executor = ToolExecutor()
        tool = AllTypesTool()
        executor.register(tool)

        result = await executor.execute(
            "all_types_tool",
            string_param="test",
            number_param=123.45,
            integer_param=10.5,  # 错误：应该是整数
            array_param=[1, 2, 3]
        )

        assert result.success is False
        assert "integer_param" in result.error
        assert "应为整数" in result.error

    @pytest.mark.asyncio
    async def test_validate_array_type_failure(self):
        """测试数组类型校验失败"""
        executor = ToolExecutor()
        tool = AllTypesTool()
        executor.register(tool)

        result = await executor.execute(
            "all_types_tool",
            string_param="test",
            number_param=123.45,
            integer_param=10,
            array_param="not_array"  # 错误：应该是数组
        )

        assert result.success is False
        assert "array_param" in result.error
        assert "应为数组" in result.error

    @pytest.mark.asyncio
    async def test_optional_parameter_provided(self):
        """测试提供可选参数"""
        executor = ToolExecutor()
        tool = OptionalTool()
        executor.register(tool)

        result = await executor.execute(
            "optional_tool",
            required_param="test",
            optional_param="provided"
        )

        assert result.success is True
        assert result.data["has_optional"] is True

    @pytest.mark.asyncio
    async def test_optional_parameter_not_provided(self):
        """测试不提供可选参数"""
        executor = ToolExecutor()
        tool = OptionalTool()
        executor.register(tool)

        result = await executor.execute(
            "optional_tool",
            required_param="test"
        )

        assert result.success is True
        assert result.data.get("has_optional") is False

    @pytest.mark.asyncio
    async def test_empty_parameters_schema(self):
        """测试空参数模式"""
        executor = ToolExecutor()
        tool = EmptyPropertiesTool()
        executor.register(tool)

        result = await executor.execute("empty_properties_tool")

        assert result.success is True
        assert result.data == {"executed": True}

    @pytest.mark.asyncio
    async def test_extra_parameters_allowed(self):
        """测试允许额外参数"""
        executor = ToolExecutor()
        tool = MockTool()
        executor.register(tool)

        # 提供额外参数
        result = await executor.execute(
            "mock_tool",
            data="test",
            extra_param="extra"  # 额外参数
        )

        assert result.success is True


class TestToolGetInfoNoCalls:
    """测试工具信息 - 无调用情况"""

    def test_get_info_without_calls(self):
        """测试未调用的工具信息"""
        tool = MockTool()

        info = tool.get_info()

        assert info["name"] == "mock_tool"
        assert info["description"] == "Mock tool for testing"
        assert info["call_count"] == 0
        assert info["last_called"] is None


class TestExecutorUnregister:
    """测试注销工具的各种情况"""

    def test_unregister_nonexistent_tool(self):
        """测试注销不存在的工具"""
        executor = ToolExecutor()

        # 不应该抛出异常
        executor.unregister("nonexistent")

        assert "nonexistent" not in executor.list_tools()


class TestExecutorGetToolsInfo:
    """测试获取所有工具信息"""

    def test_get_tools_info_empty_executor(self):
        """测试空执行器的工具信息"""
        executor = ToolExecutor()

        info = executor.get_tools_info()

        assert info == []

    def test_get_tools_info_multiple_tools(self):
        """测试多个工具的信息"""
        executor = ToolExecutor()
        executor.register(MockTool())
        executor.register(ValidatedTool())

        info = executor.get_tools_info()

        assert len(info) == 2
        names = {item["name"] for item in info}
        assert "mock_tool" in names
        assert "validated_tool" in names


class TestExecuteBatchExtended:
    """扩展的批量执行测试"""

    @pytest.mark.asyncio
    async def test_execute_batch_empty_list(self):
        """测试空批量执行"""
        executor = ToolExecutor()

        results = await executor.execute_batch([])

        assert results == []

    @pytest.mark.asyncio
    async def test_execute_batch_missing_tool_name(self):
        """测试批量执行中缺少工具名称"""
        executor = ToolExecutor()

        calls = [
            {"parameters": {"data": "test"}}  # 缺少 tool_name
        ]

        results = await executor.execute_batch(calls)

        assert len(results) == 1
        assert results[0].success is False

    @pytest.mark.asyncio
    async def test_execute_batch_missing_parameters(self):
        """测试批量执行中缺少参数字段"""
        executor = ToolExecutor()
        executor.register(MockTool())

        calls = [
            {"tool_name": "mock_tool"}  # 缺少 parameters
        ]

        results = await executor.execute_batch(calls)

        assert len(results) == 1
        # 缺少 data 参数，MockTool 会使用默认值
        assert results[0].success is True


class TestExecutionHistoryExtended:
    """扩展的执行历史测试"""

    @pytest.mark.asyncio
    async def test_execution_history_limit_zero(self):
        """测试历史限制为0返回所有历史（因为-0等于0，history[-0:]返回全部）"""
        executor = ToolExecutor()
        executor.register(MockTool())

        await executor.execute("mock_tool", data="test")

        history = executor.get_execution_history(limit=0)
        # 注意：limit=0时，history[-0:]返回所有历史（因为-0==0）
        assert len(history) == 1
        assert history[0]["tool_name"] == "mock_tool"

    @pytest.mark.asyncio
    async def test_execution_history_filter_by_nonexistent_tool(self):
        """测试按不存在的工具过滤历史"""
        executor = ToolExecutor()
        executor.register(MockTool())

        await executor.execute("mock_tool", data="test")

        history = executor.get_execution_history(tool_name="nonexistent")
        assert history == []

    @pytest.mark.asyncio
    async def test_execution_history_records_error(self):
        """测试执行历史记录错误信息"""
        executor = ToolExecutor()
        executor.register(FailingTool())

        result = await executor.execute("failing_tool")

        assert result.success is False

        history = executor.get_execution_history()
        assert len(history) == 1
        assert history[0]["success"] is False
        assert "error" in history[0]


class TestToolDecoratorExtended:
    """扩展的工具装饰器测试"""

    def test_decorator_multiple_tools(self):
        """测试装饰器注册多个工具"""
        executor = ToolExecutor()

        @register_tool(executor)
        class Tool1(Tool):
            @property
            def name(self) -> str:
                return "tool1"

            @property
            def description(self) -> str:
                return "Tool 1"

            @property
            def parameters_schema(self) -> Dict[str, Any]:
                return {"type": "object", "properties": {}}

            async def _execute(self, **kwargs) -> Any:
                return {"tool": "1"}

        @register_tool(executor)
        class Tool2(Tool):
            @property
            def name(self) -> str:
                return "tool2"

            @property
            def description(self) -> str:
                return "Tool 2"

            @property
            def parameters_schema(self) -> Dict[str, Any]:
                return {"type": "object", "properties": {}}

            async def _execute(self, **kwargs) -> Any:
                return {"tool": "2"}

        tools = executor.list_tools()
        assert "tool1" in tools
        assert "tool2" in tools


class TestToolExecutionTime:
    """测试执行时间记录"""

    @pytest.mark.asyncio
    async def test_execution_time_recorded_on_success(self):
        """测试成功时记录执行时间"""
        executor = ToolExecutor()
        tool = MockTool()
        executor.register(tool)

        result = await executor.execute("mock_tool", data="test")

        assert result.success is True
        assert result.execution_time >= 0

    @pytest.mark.asyncio
    async def test_execution_time_recorded_on_failure(self):
        """测试失败时也记录执行时间"""
        executor = ToolExecutor()
        tool = FailingTool()
        executor.register(tool)

        result = await executor.execute("failing_tool")

        assert result.success is False
        assert result.execution_time >= 0


class TestToolInfoLastCalledFormat:
    """测试 last_called 时间格式"""

    @pytest.mark.asyncio
    async def test_last_called_iso_format(self):
        """测试 last_called 以 ISO 格式存储"""
        executor = ToolExecutor()
        tool = MockTool()
        executor.register(tool)

        await executor.execute("mock_tool", data="test")

        info = tool.get_info()
        assert "last_called" in info
        # 验证是 ISO 格式
        assert "T" in info["last_called"] or ":" in info["last_called"]


class AllTypesTool(Tool):
    """测试所有参数类型的工具"""

    @property
    def name(self) -> str:
        return "all_types_tool"

    @property
    def description(self) -> str:
        return "Tool with all parameter types"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "required": ["string_param", "number_param", "integer_param", "array_param"],
            "properties": {
                "string_param": {"type": "string"},
                "number_param": {"type": "number"},
                "integer_param": {"type": "integer"},
                "array_param": {"type": "array"}
            }
        }

    async def _execute(self, **kwargs) -> Any:
        return {"validated": True, "params": kwargs}


class OptionalTool(Tool):
    """测试可选参数的工具"""

    @property
    def name(self) -> str:
        return "optional_tool"

    @property
    def description(self) -> str:
        return "Tool with optional parameters"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "required": ["required_param"],
            "properties": {
                "required_param": {"type": "string"},
                "optional_param": {"type": "string"}
            }
        }

    async def _execute(self, **kwargs) -> Any:
        return {"has_optional": "optional_param" in kwargs}


class EmptyPropertiesTool(Tool):
    """测试空属性的工具"""

    @property
    def name(self) -> str:
        return "empty_properties_tool"

    @property
    def description(self) -> str:
        return "Tool with empty properties"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def _execute(self, **kwargs) -> Any:
        return {"executed": True}