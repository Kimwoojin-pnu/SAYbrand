"""캐시 서비스 — Redis 우선, 불가 시 인메모리 폴백"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self) -> None:
        self._redis = None
        self._use_redis = False
        self._init_done = False
        self._memory: dict[str, tuple[str, float | None]] = {}

    async def _init(self) -> None:
        if self._init_done:
            return
        self._init_done = True
        try:
            import redis.asyncio as aioredis
            from backend.config import settings
            client = aioredis.from_url(
                settings.redis_url,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            await client.ping()
            self._redis = client
            self._use_redis = True
            logger.info("Cache: Redis 연결 성공 (%s)", settings.redis_url)
        except Exception as e:
            logger.info("Cache: Redis 사용 불가, 인메모리 폴백 (%s)", e)

    # ── public interface ────────────────────────────────────────────

    async def get(self, key: str) -> str | None:
        await self._init()
        if self._use_redis:
            try:
                val = await self._redis.get(key)
                return val.decode() if val else None
            except Exception as e:
                logger.warning("Cache.get Redis 오류: %s", e)
        return self._mem_get(key)

    async def set(self, key: str, value: str) -> None:
        await self._init()
        if self._use_redis:
            try:
                await self._redis.set(key, value)
                return
            except Exception as e:
                logger.warning("Cache.set Redis 오류: %s", e)
        self._mem_set(key, value, None)

    async def setex(self, key: str, seconds: int, value: str) -> None:
        await self._init()
        if self._use_redis:
            try:
                await self._redis.setex(key, seconds, value)
                return
            except Exception as e:
                logger.warning("Cache.setex Redis 오류: %s", e)
        self._mem_set(key, value, time.time() + seconds)

    # ── in-memory helpers ───────────────────────────────────────────

    def _mem_get(self, key: str) -> str | None:
        entry = self._memory.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and time.time() > expires_at:
            del self._memory[key]
            return None
        return value

    def _mem_set(self, key: str, value: str, expires_at: float | None) -> None:
        self._memory[key] = (value, expires_at)


cache = CacheService()
