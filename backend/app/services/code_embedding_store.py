"""CodeEmbedding 向量存储与语义检索服务。"""

from __future__ import annotations

import json
import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session
from app.core.embedding import embedding_client
from app.models.db_models import CodeEmbeddingModel

logger = logging.getLogger(__name__)

# 单次 embedding 最大文本长度（字符）
_MAX_CHUNK_CHARS = 8000


class CodeEmbeddingStore:
    """代码片段向量存储，支持写入与余弦相似度检索。"""

    async def upsert_chunks(
        self,
        repo_url: str,
        chunks: list[dict],
    ) -> int:
        """将代码分块生成 embedding 并写入数据库。

        chunks 结构: [{"file_path": str, "symbol": str|None, "language": str, "code": str, "chunk_index": int}]
        返回写入条数。
        """
        if not chunks:
            return 0

        # 批量生成 embedding（每批最多 20 条避免超时）
        batch_size = 20
        texts = [c["code"][:_MAX_CHUNK_CHARS] for c in chunks]
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = await embedding_client.embed(batch)
            all_embeddings.extend(embeddings)

        async with async_session() as session:
            for chunk, embedding_vec in zip(chunks, all_embeddings):
                model = CodeEmbeddingModel(
                    repo_url=repo_url,
                    file_path=chunk["file_path"],
                    symbol=chunk.get("symbol"),
                    language=chunk.get("language"),
                    code=chunk["code"][:_MAX_CHUNK_CHARS],
                    chunk_index=chunk.get("chunk_index", 0),
                    embedding=self._store_embedding(session, embedding_vec),
                )
                session.add(model)
            await session.commit()

        logger.info("[EmbeddingStore] Upserted %d chunks for %s", len(chunks), repo_url)
        return len(chunks)

    async def search_similar(
        self,
        repo_url: str,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[dict]:
        """语义检索与 query 最相似的代码片段。

        返回: [{"file_path", "symbol", "language", "code", "similarity"}]
        """
        if "postgresql" not in settings.database_url:
            logger.warning("[EmbeddingStore] Similarity search requires PostgreSQL + pgvector")
            return []

        query_embedding = await embedding_client.embed_single(query)

        async with async_session() as session:
            # pgvector 余弦距离操作符 <=>
            sql = text("""
                SELECT file_path, symbol, language, code,
                       1 - (embedding <=> :query_vec) AS similarity
                FROM code_embeddings
                WHERE repo_url = :repo_url
                ORDER BY embedding <=> :query_vec
                LIMIT :top_k
            """)
            result = await session.execute(
                sql,
                {
                    "repo_url": repo_url,
                    "query_vec": str(query_embedding),
                    "top_k": top_k,
                },
            )
            rows = result.fetchall()

        return [
            {
                "file_path": row.file_path,
                "symbol": row.symbol,
                "language": row.language,
                "code": row.code,
                "similarity": float(row.similarity),
            }
            for row in rows
        ]

    async def delete_by_repo(self, repo_url: str) -> int:
        """删除指定仓库的所有嵌入记录。"""
        async with async_session() as session:
            result = await session.execute(
                select(CodeEmbeddingModel).where(CodeEmbeddingModel.repo_url == repo_url)
            )
            models = result.scalars().all()
            for m in models:
                await session.delete(m)
            await session.commit()
        logger.info("[EmbeddingStore] Deleted %d chunks for %s", len(models), repo_url)
        return len(models)

    @staticmethod
    def _store_embedding(session: AsyncSession, embedding: list[float]):
        """根据数据库类型返回合适的 embedding 值。"""
        if "postgresql" in settings.database_url:
            return embedding
        # SQLite 降级：以 JSON 字符串存储
        return json.dumps(embedding)


code_embedding_store = CodeEmbeddingStore()