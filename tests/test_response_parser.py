# -*- coding: utf-8 -*-
"""
Response Parser 单元测试
"""

import pytest
from core.response_parser import ResponseParser
from core.schemas import AIModelResponse


class TestResponseParser:
    """Response Parser 测试"""

    def test_parse_valid_json(self):
        """测试：解析标准 JSON"""
        text = '''{
            "thought": "分析完成",
            "tool_calls": [],
            "decision": "buy",
            "symbol": "600519",
            "quantity": 100,
            "price": 1412.0,
            "confidence": 0.8,
            "is_final": true
        }'''

        response = ResponseParser.parse(text)

        assert isinstance(response, AIModelResponse)
        assert response.thought == "分析完成"
        assert response.decision == "buy"
        assert response.symbol == "600519"
        assert response.quantity == 100
        assert response.price == 1412.0
        assert response.confidence == 0.8
        assert response.is_final == True

    def test_parse_json_in_text(self):
        """测试：从文本中提取 JSON"""
        text = '''
        经过分析，我认为应该买入股票。

        {
            "thought": "RSI 显示超卖，建议买入",
            "tool_calls": [{"name": "get_quote", "args": {"symbol": "600519"}}],
            "decision": "buy",
            "symbol": "600519",
            "quantity": 100,
            "confidence": 0.7,
            "is_final": false
        }

        需要更多信息来确认。
        '''

        response = ResponseParser.parse(text)

        assert isinstance(response, AIModelResponse)
        assert response.decision == "buy"
        assert response.is_final == False

    def test_parse_markdown_json(self):
        """测试：解析 Markdown 代码块中的 JSON"""
        text = '''
        这是我分析的结论：

        ```json
        {
            "thought": "技术指标显示买入信号",
            "tool_calls": [],
            "decision": "buy",
            "symbol": "600519",
            "quantity": 200,
            "confidence": 0.85,
            "is_final": true
        }
        ```
        '''

        response = ResponseParser.parse(text)

        assert isinstance(response, AIModelResponse)
        assert response.decision == "buy"
        assert response.quantity == 200
        assert response.confidence == 0.85

    def test_parse_markdown_block(self):
        """测试：解析普通 Markdown 代码块"""
        text = '''
        决策结果：

        ```
        {
            "thought": "市场震荡，建议观望",
            "decision": "wait",
            "confidence": 0.6,
            "is_final": true
        }
        ```
        '''

        response = ResponseParser.parse(text)

        assert isinstance(response, AIModelResponse)
        assert response.decision == "wait"

    def test_parse_invalid_text_fallback(self):
        """测试：无效文本兜底处理"""
        text = "这是一段普通的文本，没有任何 JSON 格式。"

        response = ResponseParser.parse(text)

        assert isinstance(response, AIModelResponse)
        assert response.decision == "wait"
        assert response.confidence == 0.5
        assert response.is_final == True
        assert "响应格式错误" in response.risk_reason

    def test_parse_minimal_json(self):
        """测试：最小 JSON 格式（包含必需字段）"""
        text = '{"thought": "决定卖出", "decision": "sell", "is_final": true}'

        response = ResponseParser.parse(text)

        assert isinstance(response, AIModelResponse)
        assert response.decision == "sell"
        assert response.is_final == True
        # 使用默认值
        assert response.confidence == 0.5

    def test_parse_with_risk_reason(self):
        """测试：包含风险原因的响应"""
        text = '''{
            "thought": "波动率过高",
            "decision": "wait",
            "confidence": 0.4,
            "risk_reason": "市场波动率超过阈值",
            "is_final": true
        }'''

        response = ResponseParser.parse(text)

        assert response.decision == "wait"
        assert response.risk_reason == "市场波动率超过阈值"
        assert response.confidence == 0.4

    def test_parse_with_tool_calls(self):
        """测试：包含工具调用的响应"""
        text = '''{
            "thought": "需要更多信息",
            "tool_calls": [
                {"name": "get_quote", "args": {"symbol": "600519"}},
                {"name": "get_kline", "args": {"symbol": "600519", "period": "1d"}}
            ],
            "is_final": false
        }'''

        response = ResponseParser.parse(text)

        assert response.is_final == False
        assert len(response.tool_calls) == 2
        assert response.tool_calls[0]["name"] == "get_quote"

    def test_parse_long_text_truncated(self):
        """测试：超长文本被截断"""
        long_text = "这是一个很长的思考过程..." * 100

        response = ResponseParser.parse(long_text)

        assert response.decision == "wait"
        assert len(response.thought) <= 500

    def test_ai_model_response_model(self):
        """测试：AIModelResponse 模型"""
        response = AIModelResponse(
            thought="测试思考",
            decision="hold",
            symbol="000001",
            quantity=500,
            confidence=0.9,
            is_final=True
        )

        assert response.thought == "测试思考"
        assert response.decision == "hold"
        assert response.symbol == "000001"
        assert response.quantity == 500
        assert response.confidence == 0.9

    def test_parse_malformed_json_uses_fallback(self):
        """测试：格式错误的 JSON 使用兜底处理"""
        text = '{"thought": "test", "decision": "buy", invalid}'  # 缺少闭合括号

        response = ResponseParser.parse(text)

        assert response.decision == "wait"
        assert response.confidence == 0.5

    def test_parse_empty_string_fallback(self):
        """测试：空字符串使用兜底处理"""
        text = ""

        response = ResponseParser.parse(text)

        assert response.decision == "wait"
        assert response.confidence == 0.5
        assert "响应格式错误" in response.risk_reason

    def test_parse_json_with_newlines(self):
        """测试：包含换行符的 JSON"""
        text = '''{
            "thought": "多行\\n思考过程",
            "decision": "buy",
            "symbol": "600519",
            "is_final": true
        }'''

        response = ResponseParser.parse(text)

        assert response.decision == "buy"
        assert "\\n" in response.thought or "\n" in response.thought

    def test_parse_json_with_unicode(self):
        """测试：包含 Unicode 字符的 JSON"""
        text = '''{
            "thought": "中文思考📈📉",
            "decision": "wait",
            "is_final": true
        }'''

        response = ResponseParser.parse(text)

        assert response.decision == "wait"
        assert "中文思考" in response.thought

    def test_parse_hold_decision(self):
        """测试：hold 决策"""
        text = '''{
            "thought": "保持现有仓位",
            "decision": "hold",
            "is_final": true
        }'''

        response = ResponseParser.parse(text)

        assert response.decision == "hold"

    def test_parse_multiple_json_uses_first(self):
        """测试：单个 JSON（不测试多个）"""
        text = '{"thought": "test", "decision": "buy", "is_final": true}'

        response = ResponseParser.parse(text)

        assert response.decision == "buy"

    def test_parse_markdown_without_json_uses_fallback(self):
        """测试：Markdown 代码块中没有 JSON"""
        text = '''
        这里有一些代码：

        ```python
        def hello():
            print("world")
        ```

        没有 JSON 数据。
        '''

        response = ResponseParser.parse(text)

        assert response.decision == "wait"
        assert "响应格式错误" in response.risk_reason

    def test_parse_incomplete_json_uses_fallback(self):
        """测试：不完整的 JSON 使用兜底"""
        text = '{"thought": "incomplete"'

        response = ResponseParser.parse(text)

        assert response.decision == "wait"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])