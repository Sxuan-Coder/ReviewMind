from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0


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