"""Redis 缓存封装。

提供统一的 get/set/delete 接口，Redis 不可用时静默降级为无缓存。
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis 缓存客户端，不可用时自动降级。"""

    def __init__(self) -> None:
        self._client: aioredis.Redis | None = None
        self._available: bool | None = None  # 未检测

    async def _ensure_client(self) -> aioredis.Redis | None:
        if self._client is not None:
            return self._client
        if self._available is False:
            return None
        try:
            self._client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
            )
            await self._client.ping()
            self._available = True
            logger.info("[CACHE] Redis connected: %s", settings.redis_url)
            return self._client
        except Exception as exc:
            self._available = False
            logger.warning("[CACHE] Redis unavailable, degraded to no-cache: %s", exc)
            return None

    async def get(self, key: str) -> Any | None:
        client = await self._ensure_client()
        if client is None:
            return None
        try:
            raw = await client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        client = await self._ensure_client()
        if client is None:
            return
        try:
            await client.set(key, json.dumps(value, ensure_ascii=False, default=str), ex=ttl_seconds)
        except Exception:
            pass

    async def delete(self, key: str) -> None:
        client = await self._ensure_client()
        if client is None:
            return
        try:
            await client.delete(key)
        except Exception:
            pass

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


redis_cache = RedisCache()