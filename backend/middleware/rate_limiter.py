"""Rate Limiter — 인메모리 슬라이딩 윈도우 (Redis 없을 때도 동작)"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from backend.config import settings


class InMemoryRateLimiter:
    def __init__(self) -> None:
        # {key: deque of timestamps}
        self._windows: dict[str, deque] = defaultdict(deque)

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        dq = self._windows[key]
        cutoff = now - window_seconds
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True


_limiter = InMemoryRateLimiter()


def _client_key(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown")
    return ip


async def rate_limit_middleware(request: Request, call_next: Callable):
    path = request.url.path
    key = _client_key(request)

    # /api/dashboard/scan (POST) — 시간당 10회
    if path == "/api/dashboard/scan" and request.method == "POST":
        if not _limiter.is_allowed(f"scan:{key}", limit=10, window_seconds=3600):
            return JSONResponse(
                status_code=429,
                content={"error": "스캔 요청이 너무 많습니다. 1시간 후 다시 시도해 주세요."},
                headers={"Retry-After": "3600"},
            )

    # API 전체 — 분당 60회
    if path.startswith("/api/"):
        if not _limiter.is_allowed(f"api:{key}", limit=settings.rate_limit_per_minute, window_seconds=60):
            return JSONResponse(
                status_code=429,
                content={"error": "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요."},
                headers={"Retry-After": "60"},
            )

    return await call_next(request)
