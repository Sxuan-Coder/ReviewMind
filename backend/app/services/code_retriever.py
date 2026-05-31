"""LangChain BaseRetriever 适配器。

将 CodeEmbeddingStore 包装为 LangChain 标准 Retriever 接口，
支持 Top-K 限制、上下文截断、Redis 缓存。
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, Field

from app.core.cache import redis_cache
from app.core.config import settings
from app.services.code_embedding_store import code_embedding_store

logger = logging.getLogger(__name__)


class CodeRetriever(BaseRetriever):
    """LangChain 兼容的代码检索器，委托给 CodeEmbeddingStore。

    支持：
    - Top-K 限制
    - 上下文截断（max_snippet_chars）
    - Redis 缓存（对 repo_url + query 做 key 缓存）
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    repo_url: str = Field(default="")
    top_k: int = Field(default=5)
    max_snippet_chars: int = Field(default=2000)
    cache_ttl_seconds: int = Field(default=3600)

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun | None = None,
    ) -> list[Document]:
        """同步检索接口（BaseRetriever 要求实现）。

        注意：BaseRetriever 的 _get_relevant_documents 是同步的，
        但我们底层使用异步的 CodeEmbeddingStore。
        这里返回空列表作为降级，真正的检索通过 aretrieve 调用。
        """
        logger.warning("[CodeRetriever] Sync _get_relevant_documents called - returning empty (use async path)")
        return []

    async def aretrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
    ) -> list[Document]:
        """异步检索：调用 CodeEmbeddingStore + 缓存 + 截断。

        Args:
            query: 检索查询文本
            top_k: 覆盖默认 top_k 值

        Returns:
            LangChain Document 列表，包含相似代码片段
        """
        resolved_top_k = top_k or self.top_k

        # 1. 尝试从 Redis 缓存读取
        cache_key = self._cache_key(query, resolved_top_k)
        if cache_key:
            cached = await redis_cache.get(cache_key)
            if cached is not None:
                logger.info("[CodeRetriever] Cache HIT | key=%s count=%d", cache_key, len(cached))
                return [Document(page_content=item["page_content"], metadata=item["metadata"]) for item in cached]

        # 2. 调用 CodeEmbeddingStore 检索
        results = await code_embedding_store.search_similar(
            repo_url=self.repo_url,
            query=query,
            top_k=resolved_top_k,
        )
        if not results:
            return []

        # 3. 截断并构造 Document
        documents: list[Document] = []
        for item in results:
            code = item.get("code", "")
            # 上下文截断
            if len(code) > self.max_snippet_chars:
                code = code[:self.max_snippet_chars] + "\n... (truncated)"

            metadata: dict[str, Any] = {
                "file_path": item.get("file_path", ""),
                "symbol": item.get("symbol"),
                "language": item.get("language", ""),
                "similarity": item.get("similarity", 0),
            }
            documents.append(Document(page_content=code, metadata=metadata))

        # 4. 写入缓存
        if cache_key and documents:
            cache_data = [
                {"page_content": d.page_content, "metadata": d.metadata}
                for d in documents
            ]
            await redis_cache.set(cache_key, cache_data, ttl_seconds=self.cache_ttl_seconds)

        logger.info("[CodeRetriever] Retrieved %d docs | repo=%s top_k=%d", len(documents), self.repo_url, resolved_top_k)
        return documents

    def _cache_key(self, query: str, top_k: int) -> str:
        """生成缓存 key：rag:retrieve:{sha256(repo_url:query:top_k)}。"""
        raw = f"{self.repo_url}:{query}:{top_k}"
        digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"rag:retrieve:{digest}"
