"""공통 Gemini 클라이언트 — 자동 캐싱, 429 재시도, API 키 없으면 None 반환"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re

logger = logging.getLogger(__name__)


async def gemini_call(
    prompt: str,
    model_name: str = "gemini-2.5-flash-lite",
    cache_ttl: int = 86400,
    expect_json: bool = True,
    max_output_tokens: int = 300,
    system_instruction: str | None = None,
) -> dict | str | None:
    from backend.config import settings
    from backend.services.cache import cache

    if not settings.gemini_api_key:
        return None

    cache_key = "gc:" + hashlib.sha256(
        f"{model_name}:{prompt[:300]}".encode()
    ).hexdigest()[:32]

    cached = await cache.get(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            return cached

    async def _call() -> dict | str | None:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=settings.gemini_api_key)
            config_kwargs: dict = {"max_output_tokens": max_output_tokens}
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            raw = response.text
            if expect_json:
                json_match = re.search(r"\{.*\}", raw, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                arr_match = re.search(r"\[.*\]", raw, re.DOTALL)
                if arr_match:
                    return json.loads(arr_match.group())
                return None
            return raw
        except Exception as e:
            err = str(e)
            if "ResourceExhausted" in err or "429" in err or "quota" in err.lower():
                raise _RateLimitError()
            raise

    try:
        result = await _call()
    except _RateLimitError:
        logger.warning("Gemini 429 — 30초 후 재시도")
        await asyncio.sleep(30)
        try:
            result = await _call()
        except Exception as e:
            logger.warning("Gemini 재시도 실패: %s", e)
            return None
    except Exception as e:
        logger.warning("Gemini 호출 실패: %s", e)
        return None

    if result is not None:
        payload = json.dumps(result) if isinstance(result, (dict, list)) else result
        await cache.setex(cache_key, cache_ttl, payload)

    return result


class _RateLimitError(Exception):
    pass
