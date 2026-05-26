"""공통 Gemini 클라이언트 — 자동 캐싱, 429 재시도, API 키 없으면 None 반환"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re

logger = logging.getLogger(__name__)


def get_gemini_model(model_name: str = "gemini-2.0-flash"):
    try:
        import google.generativeai as genai
        from backend.config import settings
        genai.configure(api_key=settings.gemini_api_key)
        return genai.GenerativeModel(model_name)
    except Exception as e:
        logger.warning("Gemini 모델 초기화 실패: %s", e)
        return None


async def gemini_call(
    prompt: str,
    model_name: str = "gemini-2.0-flash",
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
            import google.generativeai as genai
            genai.configure(api_key=settings.gemini_api_key)
            kwargs: dict = {}
            if system_instruction:
                kwargs["system_instruction"] = system_instruction
            model = genai.GenerativeModel(model_name, **kwargs)
            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config={"max_output_tokens": max_output_tokens},
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
            err = f"{type(e).__name__}{e}"
            if "ResourceExhausted" in err or "429" in str(e) or "quota" in str(e).lower():
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
