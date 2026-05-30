"""L2 텍스트 분석 — HyperCLOVA X → Gemini 2.0 Flash → Mock 폴백 (10-field sentiment)"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re

import httpx

from backend.config import settings
from backend.services.cache import cache

logger = logging.getLogger(__name__)

_CACHE_TTL = 86400  # 24시간

# ── HyperCLOVA용 상세 프롬프트 (유지) ──────────────────────────────────
KR_SNS_ANALYSIS_PROMPT = """당신은 한국 SNS 브랜드 위협 분석 전문가입니다.
주어진 텍스트가 특정 브랜드에 대한 위협인지 분석하세요.

## 한국어 특성 반드시 고려

1. **반어법**: "ㄹㅇ 대박이네", "쩐다", "레전드다" 등은 문맥에 따라 극도의 부정을 의미할 수 있음.
   긍정 단어 + 부정 상황 조합 시 반어법으로 판단.

2. **줄임말·초성**:
   - ㄷㄷ / ㄷㄷㄷ = 두려움·충격
   - ㅂㄷ / ㅂㄷㄷ = 분노
   - 개+단어 = 강도 강조 (개최악, 개짜증)
   - ㄱㄱ / 올ㄱㄱ = 공유 권유 (봇 신호)

3. **커뮤니티어**:
   - "각" = ~할 것 같다·예상됨 (환불각, 고소각, 탈출각)
   - "레전드" = 극단적 사건 (역레전드 = 최악)
   - "박제" = 캡처 보존·증거 수집 의도
   - "탈주·런" = 회사/브랜드 이탈 권고
   - "어그로" = 허위 과장 가능성

4. **봇·조직적 공격 패턴**:
   - 동일·유사 문체 반복
   - "공유하면~", "rt하면~" 등 행동 유도 문구
   - "긴급·속보" 위장
   - 제보·내부고발 형식 위장

5. **플랫폼 특화 표현**:
   - 블라인드·디시·에펨: 직장인 내부 제보 성격
   - X(트위터): 실검 올리기·트렌딩 시도
   - 유튜브 댓글: 조직적 평점 테러

## 응답 형식 (반드시 순수 JSON만 출력, 설명 없음)

{
  "threat_detected": true,
  "severity": "critical",
  "threat_type": "위협 유형 한 줄 설명",
  "confidence": 0.85,
  "summary": "위협 요약 한 줄 (한국어)",
  "bot_indicators": ["패턴1", "패턴2"],
  "irony_detected": false,
  "is_organized": false,
  "sentiment": "negative",
  "emotion": "분노",
  "sentiment_score": -0.8
}

severity 값: "critical" | "high" | "medium" | "low" | "none"
sentiment 값: "negative" | "positive" | "neutral"
emotion 값: "분노" | "공포" | "혐오" | "슬픔" | "놀람" | "기쁨" | "중립"
sentiment_score: -1.0 (극부정) ~ 1.0 (극긍정)
"""

# ── Gemini용 10-field 프롬프트 ────────────────────────────────────────
_GEMINI_L2_PROMPT = """한국 SNS 브랜드 위협 분석기. 반어법·초성·커뮤니티어 해석 필수.
JSON만 출력(설명 없음):
{"sentiment":"negative|positive|neutral","emotion":"분노|공포|혐오|슬픔|놀람|기쁨|중립","sentiment_score":0.0,"threat_detected":false,"severity":"none|low|medium|high|critical","threat_type":"유형15자이내","confidence":0.0,"summary":"한줄요약","is_organized":false,"bot_indicators":[]}"""

# ── 배치 분석용 프롬프트 ────────────────────────────────────────────────
_GEMINI_BATCH_PROMPT = """한국 SNS 위협 분석기. 각 번호 게시물 분석. 반어법·초성·커뮤니티어 해석.
JSON 배열만 출력(설명 없음):
[{"sentiment":"negative|positive|neutral","emotion":"분노|공포|혐오|슬픔|놀람|기쁨|중립","sentiment_score":0.0,"threat_detected":false,"severity":"none|low|medium|high|critical","threat_type":"유형15자","confidence":0.0,"summary":"한줄요약","is_organized":false,"bot_indicators":[]},...]"""

# urgency/severity → confidence 매핑
_URGENCY_CONF: dict[str, float] = {
    "critical": 0.9, "high": 0.7, "medium": 0.5, "low": 0.3, "none": 0.1,
}


# ── HyperCLOVA X ───────────────────────────────────────────────────

async def _call_hyperclova(text: str) -> dict | None:
    if not settings.hyperclova_api_key or not settings.hyperclova_gateway_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://clovastudio.stream.naver.com/testapp/v1/chat-completions/HCX-003",
                headers={
                    "X-NCP-CLOVASTUDIO-API-KEY": settings.hyperclova_api_key,
                    "X-NCP-APIGW-API-KEY": settings.hyperclova_gateway_key,
                    "Content-Type": "application/json",
                },
                json={
                    "messages": [
                        {"role": "system", "content": KR_SNS_ANALYSIS_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    "maxTokens": 512,
                    "temperature": 0.3,
                    "topP": 0.8,
                    "repeatPenalty": 5.0,
                    "includeAiFilters": False,
                },
            )
        if resp.status_code != 200:
            logger.warning("HyperCLOVA 응답 오류: %s", resp.status_code)
            return None
        data = resp.json()
        content = data["result"]["message"]["content"]
        tokens_in = data["result"].get("inputLength", 0)
        tokens_out = data["result"].get("outputLength", 0)
        result = _parse_llm_response(content)
        result["_meta"] = {"model": "hyperclova", "tokens_in": tokens_in, "tokens_out": tokens_out}
        return result
    except Exception as e:
        logger.warning("HyperCLOVA 호출 실패: %s", e)
        return None


# ── Gemini 2.0 Flash ────────────────────────────────────────────────

async def _call_gemini(text: str) -> dict | None:
    if not settings.gemini_api_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.5-flash-lite")
        prompt = f"{_GEMINI_L2_PROMPT}\n\n분석 텍스트:\n{text[:500]}"

        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
            generation_config={"max_output_tokens": 200},
        )
        tokens_in = getattr(response.usage_metadata, "prompt_token_count", 0)
        tokens_out = getattr(response.usage_metadata, "candidates_token_count", 0)
        result = _parse_l2_response(response.text)
        result["_meta"] = {"model": "gemini-2.5-flash-lite", "tokens_in": tokens_in, "tokens_out": tokens_out}
        return result
    except Exception as e:
        err_str = f"{type(e).__name__}{e}"
        if "ResourceExhausted" in err_str or "429" in str(e) or "quota" in str(e).lower():
            logger.warning("Gemini 무료 티어 한도 초과 — Mock 반환")
            return _mock_analysis()
        logger.warning("Gemini 호출 실패: %s", e)
        return None


# ── 응답 파싱 ───────────────────────────────────────────────────────

def _parse_l2_response(raw: str) -> dict:
    """Gemini 10-field 응답 파싱."""
    json_match = re.search(r"\{.*?\}", raw, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            severity = data.get("severity", "none")
            confidence = float(data.get("confidence", 0.0)) or _URGENCY_CONF.get(severity, 0.1)
            return {
                "threat_detected": bool(data.get("threat_detected", False)),
                "severity": severity,
                "threat_type": data.get("threat_type", ""),
                "confidence": confidence,
                "summary": data.get("summary", ""),
                "bot_indicators": data.get("bot_indicators", []),
                "irony_detected": False,
                "is_organized": bool(data.get("is_organized", False)),
                "sentiment": data.get("sentiment", "neutral"),
                "emotion": data.get("emotion", "중립"),
                "sentiment_score": float(data.get("sentiment_score", 0.0)),
                "is_mock": False,
            }
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    return _mock_analysis()


def _parse_llm_response(raw: str) -> dict:
    """HyperCLOVA 전체 필드 응답 파싱."""
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return {
                "threat_detected": bool(data.get("threat_detected", False)),
                "severity": data.get("severity", "none"),
                "threat_type": data.get("threat_type", ""),
                "confidence": float(data.get("confidence", 0.0)),
                "summary": data.get("summary", ""),
                "bot_indicators": data.get("bot_indicators", []),
                "irony_detected": bool(data.get("irony_detected", False)),
                "is_organized": bool(data.get("is_organized", False)),
                "sentiment": data.get("sentiment", "neutral"),
                "emotion": data.get("emotion", "중립"),
                "sentiment_score": float(data.get("sentiment_score", 0.0)),
                "is_mock": False,
            }
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    return _mock_analysis()


def _mock_analysis() -> dict:
    return {
        "threat_detected": False,
        "severity": "none",
        "threat_type": "mock",
        "confidence": 0.0,
        "summary": "[Mock] GEMINI_API_KEY 또는 HYPERCLOVA_API_KEY 설정 시 실제 분석이 실행됩니다.",
        "bot_indicators": [],
        "irony_detected": False,
        "is_organized": False,
        "sentiment": "neutral",
        "emotion": "중립",
        "sentiment_score": 0.0,
        "is_mock": True,
        "_meta": {"model": "mock", "tokens_in": 0, "tokens_out": 0},
    }


# ── 공개 API ────────────────────────────────────────────────────────

async def call_l2_with_fallback(text: str) -> dict:
    """HyperCLOVA → Gemini 2.0 Flash → Mock 순서로 폴백 호출."""
    result = await _call_hyperclova(text)
    if result:
        return result

    result = await _call_gemini(text)
    if result:
        return result

    return _mock_analysis()


async def analyze_text_with_cache(
    text: str,
    profile_id: int | None = None,
) -> dict:
    """캐시(TTL 24시간) 적용 L2 텍스트 분석."""
    cache_key = "l2t:" + hashlib.sha256(
        f"{profile_id}:{text}".encode()
    ).hexdigest()[:32]

    cached = await cache.get(cache_key)
    if cached:
        try:
            result = json.loads(cached)
            result["_cached"] = True
            return result
        except json.JSONDecodeError:
            pass

    result = await call_l2_with_fallback(text)
    await cache.setex(cache_key, _CACHE_TTL, json.dumps(result))
    result["_cached"] = False
    return result


async def analyze_batch(posts: list[str], max_batch: int = 10) -> list[dict]:
    """최대 10건을 1 API 호출로 배치 분석 (Gemini 2.0 Flash)."""
    if not posts:
        return []

    batch = posts[:max_batch]

    if not settings.gemini_api_key:
        return [_mock_analysis() for _ in batch]

    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.5-flash-lite")

        items = "\n---\n".join(
            f"[{i + 1}] {p[:500]}" for i, p in enumerate(batch)
        )
        prompt = f"{_GEMINI_BATCH_PROMPT}\n\n{items}"

        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
            generation_config={"max_output_tokens": 600},
        )

        arr_match = re.search(r"\[.*\]", response.text, re.DOTALL)
        if arr_match:
            parsed_list = json.loads(arr_match.group())
            results: list[dict] = []
            for data in parsed_list[:len(batch)]:
                severity = data.get("severity", "none")
                confidence = float(data.get("confidence", 0.0)) or _URGENCY_CONF.get(severity, 0.1)
                results.append({
                    "threat_detected": bool(data.get("threat_detected", False)),
                    "severity": severity,
                    "threat_type": data.get("threat_type", ""),
                    "confidence": confidence,
                    "summary": data.get("summary", ""),
                    "bot_indicators": data.get("bot_indicators", []),
                    "irony_detected": False,
                    "is_organized": bool(data.get("is_organized", False)),
                    "sentiment": data.get("sentiment", "neutral"),
                    "emotion": data.get("emotion", "중립"),
                    "sentiment_score": float(data.get("sentiment_score", 0.0)),
                    "is_mock": False,
                    "_meta": {"model": "gemini-2.5-flash-lite-batch", "tokens_in": 0, "tokens_out": 0},
                })
            while len(results) < len(batch):
                results.append(_mock_analysis())
            return results
    except Exception as e:
        err_str = f"{type(e).__name__}{e}"
        if "ResourceExhausted" in err_str or "429" in str(e) or "quota" in str(e).lower():
            logger.warning("Gemini 배치 429 — Mock 반환")
        else:
            logger.warning("L2 배치 분석 실패: %s", e)

    return [_mock_analysis() for _ in batch]
