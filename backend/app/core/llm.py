from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0


@dataclass
class ToolCallItem:
    """单次工具调用（OpenAI 原生 tool_calls 元素）。"""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallResponse:
    """chat_with_tools 的返回：完整 message 结构（含 tool_calls）。

    - ``content``: 模型的文本输出（可能为 None，当模型只调工具不给文本时）
    - ``tool_calls``: 原生工具调用列表；为空表示模型已给出最终文本结论
    - ``finish_reason``: stop（正常结束）/ tool_calls（要求调工具）/ length 等
    - ``reasoning_content``: 推理模型（如 deepseek-v4-flash）的思维链。
      推理模型的多轮协议要求：下一轮回灌 assistant 消息时必须带回此字段，
      否则 API 报 400（"reasoning_content must be passed back"）。
    """

    content: str | None
    tool_calls: list[ToolCallItem] = field(default_factory=list)
    finish_reason: str = ""
    reasoning_content: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMClientError(Exception):
    """LLM 调用失败。"""


class LLMClient:
    """OpenAI-compatible LLM 客户端，支持 mock 模式。"""

    def __init__(self) -> None:
        self._api_key = settings.llm_api_key
        self._api_base = settings.llm_api_base.rstrip("/")
        self._timeout = settings.llm_timeout_seconds or _DEFAULT_TIMEOUT
        self._mock_mode = settings.llm_mock_mode

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        response_format: dict[str, str] | None = None,
    ) -> str:
        if self._mock_mode or not self.is_configured:
            reason = "mock_mode enabled" if self._mock_mode else "no API key configured"
            logger.info("[LLM] MOCK mode active (%s), skipping real call", reason)
            return self._mock_response(messages)

        resolved_model = model or settings.llm_model_summary
        api_url = f"{self._api_base}/chat/completions"
        logger.info(
            "[LLM] Calling API | url=%s model=%s temperature=%s timeout=%ss",
            api_url, resolved_model, temperature, self._timeout,
        )
        payload: dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format is not None:
            payload["response_format"] = response_format
            logger.info("[LLM] response_format=%s", response_format)

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    api_url,
                    headers=headers,
                    json=payload,
                )
                logger.info("[LLM] Response status=%s content_length=%s", resp.status_code, len(resp.content))
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                logger.info("[LLM] Success | model=%s input_tokens=%s output_tokens=%s",
                    data.get("model", "?"),
                    data.get("usage", {}).get("prompt_tokens", "?"),
                    data.get("usage", {}).get("completion_tokens", "?"),
                )
                return content
        except httpx.TimeoutException as exc:
            logger.error("[LLM] TIMEOUT after %ss | url=%s", self._timeout, api_url)
            raise LLMClientError(f"LLM request timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500]
            logger.error("[LLM] HTTP_ERROR status=%s url=%s body=%s", exc.response.status_code, api_url, body)
            raise LLMClientError(f"LLM HTTP {exc.response.status_code}: {body}") from exc
        except Exception as exc:
            logger.error("[LLM] UNEXPECTED_ERROR type=%s msg=%s", type(exc).__name__, exc)
            raise LLMClientError(f"LLM call failed: {exc}") from exc

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.0,
        tool_choice: str = "auto",
    ) -> ToolCallResponse:
        """带原生工具调用的 chat（OpenAI Function Calling 协议）。

        与 ``chat()`` 的区别：
        - 透传 ``tools`` / ``tool_choice`` 字段给 API；
        - 返回完整 message 结构（``ToolCallResponse``，含 ``tool_calls``），
          而非只返回字符串——这是 Agent Loop 多轮工具调用的前提。

        现有 4 个 agent 仍用 ``chat()``，本方法仅供 Planner 等 Agent Loop 组件使用。
        """
        if self._mock_mode or not self.is_configured:
            reason = "mock_mode enabled" if self._mock_mode else "no API key configured"
            logger.info("[LLM] MOCK mode active (%s), chat_with_tools returns empty tool_calls", reason)
            return self._mock_tool_response(messages)

        resolved_model = model or settings.llm_model_summary
        api_url = f"{self._api_base}/chat/completions"
        payload: dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature,
            "tools": tools,
            "tool_choice": tool_choice,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        logger.info(
            "[LLM] chat_with_tools | url=%s model=%s tools=%d tool_choice=%s",
            api_url, resolved_model, len(tools), tool_choice,
        )
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(api_url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                choice = data["choices"][0]
                message = choice.get("message", {})
                content = message.get("content")
                finish_reason = str(choice.get("finish_reason", ""))
                tool_calls = self._parse_native_tool_calls(message.get("tool_calls"))
                reasoning_content = message.get("reasoning_content")
                logger.info(
                    "[LLM] chat_with_tools OK | finish=%s tool_calls=%d content_len=%s reasoning=%s",
                    finish_reason, len(tool_calls), len(content) if content else 0,
                    bool(reasoning_content),
                )
                return ToolCallResponse(
                    content=content, tool_calls=tool_calls, finish_reason=finish_reason,
                    reasoning_content=reasoning_content,
                )
        except httpx.TimeoutException as exc:
            logger.error("[LLM] chat_with_tools TIMEOUT after %ss", self._timeout)
            raise LLMClientError(f"LLM request timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500]
            logger.error("[LLM] chat_with_tools HTTP_ERROR status=%s body=%s", exc.response.status_code, body)
            raise LLMClientError(f"LLM HTTP {exc.response.status_code}: {body}") from exc
        except Exception as exc:
            logger.error("[LLM] chat_with_tools UNEXPECTED_ERROR type=%s msg=%s", type(exc).__name__, exc)
            raise LLMClientError(f"LLM call failed: {exc}") from exc

    @staticmethod
    def _parse_native_tool_calls(raw: Any) -> list[ToolCallItem]:
        """把 OpenAI 原生 tool_calls 列表解析为 ToolCallItem。

        容错：arguments 是 JSON 字符串，解析失败则降级为空 dict。
        """
        if not isinstance(raw, list):
            return []
        items: list[ToolCallItem] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            func = entry.get("function", {})
            if not isinstance(func, dict):
                continue
            name = str(func.get("name", ""))
            if not name:
                continue
            args_raw = func.get("arguments", "{}")
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
            except (json.JSONDecodeError, TypeError):
                args = {}
            items.append(ToolCallItem(id=str(entry.get("id", "")), name=name, arguments=args))
        return items

    @staticmethod
    def _mock_tool_response(messages: list[dict[str, Any]]) -> ToolCallResponse:
        """mock 模式：返回无 tool_calls 的降级响应（视为模型直接给结论）。"""
        last_msg = messages[-1].get("content", "") if messages else ""
        return ToolCallResponse(
            content=f"Mock LLM（无真实工具调用）：{last_msg[:80]}",
            tool_calls=[],
            finish_reason="stop",
        )

    @staticmethod
    def _mock_response(messages: list[dict[str, str]]) -> str:
        last_msg = messages[-1]["content"] if messages else ""
        return json.dumps({
            "summary": "Mock LLM: 分析完成，未发现重大风险。",
            "findings": [],
            "risk_level": "LOW",
            "source": "mock_llm",
            "prompt_preview": last_msg[:100],
        }, ensure_ascii=False)


llm_client = LLMClient()