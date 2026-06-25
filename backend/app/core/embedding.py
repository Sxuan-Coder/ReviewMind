"""Embedding 客户端：调用 OpenAI 兼容的 embedding API。"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingClientError(Exception):
    """Embedding 调用失败。"""


class EmbeddingClient:
    """OpenAI-compatible Embedding 客户端。"""

    def __init__(self) -> None:
        self._api_key = settings.embedding_api_key or settings.llm_api_key
        self._api_base = settings.embedding_api_base.rstrip("/")
        self._model = settings.embedding_model
        self._dimensions = settings.embedding_dimensions
        # 部分供应商（如 Gitee Serverless）需要额外 header 启用容灾切换。
        # 通过 embedding_extra_headers 配置，格式为 JSON 字符串，未配置则为空。
        self._extra_headers: dict[str, str] = settings.embedding_extra_headers

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量生成文本向量，返回与 texts 等长的向量列表。"""
        if not self.is_configured:
            raise EmbeddingClientError("No embedding API key configured")

        api_url = f"{self._api_base}/embeddings"
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        # 合并供应商专属 header（如 Gitee 的 X-Failover-Enabled）
        headers.update(self._extra_headers)
        payload: dict[str, Any] = {
            "model": self._model,
            "input": texts,
        }
        # dimensions 仅在配置非零时携带（部分模型固定维度，传错会报错）
        if self._dimensions:
            payload["dimensions"] = self._dimensions

        logger.info(
            "[Embedding] Calling API | url=%s model=%s texts=%d dims=%s",
            api_url, self._model, len(texts), self._dimensions or "default",
        )

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(api_url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            # OpenAI embeddings API 返回按 input 顺序排列
            embeddings = [item["embedding"] for item in data["data"]]
            logger.info("[Embedding] Success | count=%d", len(embeddings))
            return embeddings

        except httpx.TimeoutException as exc:
            logger.error("[Embedding] TIMEOUT | url=%s", api_url)
            raise EmbeddingClientError(f"Embedding request timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500]
            logger.error("[Embedding] HTTP_ERROR status=%s body=%s", exc.response.status_code, body)
            raise EmbeddingClientError(f"Embedding HTTP {exc.response.status_code}: {body}") from exc
        except Exception as exc:
            logger.error("[Embedding] UNEXPECTED_ERROR type=%s msg=%s", type(exc).__name__, exc)
            raise EmbeddingClientError(f"Embedding call failed: {exc}") from exc

    async def embed_single(self, text: str) -> list[float]:
        """生成单条文本向量。"""
        results = await self.embed([text])
        return results[0]


embedding_client = EmbeddingClient()