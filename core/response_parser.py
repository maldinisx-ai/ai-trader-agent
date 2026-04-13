# -*- coding: utf-8 -*-
"""
大模型响应解析器 (Response Parser)

用于解析大模型返回的结构化响应，提供多层兜底机制。
"""

import json
import re
import logging
from typing import Optional

from core.schemas import AIModelResponse

logger = logging.getLogger(__name__)


class ResponseParser:
    """大模型响应解析器"""

    @staticmethod
    def parse(text: str) -> AIModelResponse:
        """
        解析响应文本

        Args:
            text: 大模型返回的原始文本

        Returns:
            AIModelResponse: 解析后的结构化响应
        """
        # 第一层：尝试直接解析 JSON
        response = ResponseParser._try_parse_json(text)
        if response is not None:
            return response

        # 第二层：尝试正则提取 JSON
        response = ResponseParser._try_extract_json(text)
        if response is not None:
            return response

        # 第三层：尝试提取 Markdown 代码块
        response = ResponseParser._try_extract_markdown(text)
        if response is not None:
            return response

        # 兜底：返回默认决策
        logger.warning(f"无法解析响应，使用默认决策: {text[:200]}")
        return AIModelResponse(
            thought=text[:500],  # 截断长文本
            tool_calls=[],
            decision="wait",
            confidence=0.5,
            risk_reason="响应格式错误，保持观望",
            is_final=True
        )

    @staticmethod
    def _try_parse_json(text: str) -> Optional[AIModelResponse]:
        """第一层：直接解析 JSON"""
        try:
            # 去除前后空白
            text = text.strip()

            # 如果是纯 JSON 字符串，直接解析
            if text.startswith('{') and text.endswith('}'):
                data = json.loads(text)
                return AIModelResponse.model_validate(data)

        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"JSON 解析失败: {e}")

        return None

    @staticmethod
    def _try_extract_json(text: str) -> Optional[AIModelResponse]:
        """第二层：正则提取 JSON"""
        try:
            # 找到第一个 { 的位置
            start = text.find('{')
            if start == -1:
                return None

            # 使用更简单的方法：找到第一个完整的 JSON 对象
            # 通过匹配括号计数
            brace_count = 0
            in_string = False
            escape = False
            json_end = -1

            for i in range(start, len(text)):
                char = text[i]

                if escape:
                    escape = False
                    continue

                if char == '\\':
                    escape = True
                    continue

                if char == '"':
                    in_string = not in_string
                    continue

                if in_string:
                    continue

                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1

                if brace_count == 0:
                    json_end = i + 1
                    break

            if json_end > start:
                json_str = text[start:json_end]
                data = json.loads(json_str)
                return AIModelResponse.model_validate(data)

        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"正则提取 JSON 失败: {e}")

        return None

    @staticmethod
    def _try_extract_markdown(text: str) -> Optional[AIModelResponse]:
        """第三层：提取 Markdown 代码块"""
        try:
            # 提取 ```json 代码块
            pattern = r'```json\s*(.*?)\s*```'
            match = re.search(pattern, text, re.DOTALL)

            if match:
                json_str = match.group(1).strip()
                data = json.loads(json_str)
                return AIModelResponse.model_validate(data)

            # 提取普通 ``` 代码块
            pattern = r'```\s*(.*?)\s*```'
            match = re.search(pattern, text, re.DOTALL)

            if match:
                json_str = match.group(1).strip()
                # 尝试解析为 JSON
                try:
                    data = json.loads(json_str)
                    return AIModelResponse.model_validate(data)
                except json.JSONDecodeError:
                    # 不是 JSON，继续尝试
                    pass

        except (json.JSONDecodeError, ValueError, re.error) as e:
            logger.debug(f"Markdown 提取失败: {e}")

        return None