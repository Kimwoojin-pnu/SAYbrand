"""L3 심층 분석 — Gemini 2.5 Flash 우선, Claude Haiku 폴백"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.orm import CustomerAlias, CustomerProfile, CustomerSocialAccount, Threat
from backend.services.cache import cache

logger = logging.getLogger(__name__)

_L3_CACHE_TTL = 43200  # 12시간

# ── 단건 분석 프롬프트 (Gemini/Claude 공용, 경량화) ──────────────────────
_L3_ANALYSIS_PROMPT_TEMPLATE = """브랜드 위협 분석 전문가. 고위협 콘텐츠 심층 분석.

{customer_context}
{account_history}

JSON만 출력(설명·마크다운 없음):
{{"threat_assessment":"위협평가한줄","is_organized_attack":false,"legal_action_required":false,"analysis":"100자이내분석","response_suggestion":["대응1(50자이내)","대응2(50자이내)","대응3(50자이내)"]}}"""

# ── 클러스터 분석 프롬프트 ─────────────────────────────────────────
_CLUSTER_SYSTEM_PROMPT = """당신은 브랜드 리스크 분석 전문가입니다.
여러 게시물을 동시에 분석합니다.
텍스트 유사성, 계정 패턴, 시간 간격을 종합해
동일 캠페인 여부를 판단하세요.

{customer_context}

반드시 순수 JSON만 출력하세요 (마크다운·설명 없음):
{{
  "is_same_campaign": true,
  "campaign_type": "bot_attack|organic_spread|coordinated_inauthentic|competitor_attack|null",
  "bot_probability": 0.85,
  "coordination_indicators": ["동일 문체 반복", "짧은 시간 내 집중 게시"],
  "risk_level": "critical|high|medium|low",
  "ai_analysis": "종합 분석 요약 (한국어, 200자 이내)",
  "ai_response_suggestion": "즉각 대응 방안 (한국어, 3줄 이내)"
}}"""


# ── 고객 컨텍스트 ────────────────────────────────────────────────────

async def _build_customer_context(profile_id: int | None, db: AsyncSession) -> str:
    if not profile_id:
        return ""

    result = await db.execute(
        select(CustomerProfile).where(CustomerProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return ""

    aliases = (await db.execute(
        select(CustomerAlias).where(CustomerAlias.profile_id == profile_id)
    )).scalars().all()

    handles = (await db.execute(
        select(CustomerSocialAccount).where(CustomerSocialAccount.profile_id == profile_id)
    )).scalars().all()

    lines = ["고객 정보:", f"- 기업명: {profile.display_name}"]
    if profile.industry:
        lines.append(f"- 업종: {profile.industry}")
    if aliases:
        lines.append(f"- 주요 키워드: {', '.join(a.alias for a in aliases)}")
    if handles:
        lines.append(f"- 공식 계정: {', '.join(f'@{a.handle} ({a.platform})' for a in handles)}")

    return "\n".join(lines)


# ── 계정 히스토리 ────────────────────────────────────────────────────

async def _build_account_history(source_account: str | None, db: AsyncSession | None) -> str:
    if not source_account or not db:
        return ""

    result = await db.execute(
        select(Threat)
        .where(Threat.source_account == source_account)
        .order_by(Threat.detected_at.desc())
        .limit(3)
    )
    past = result.scalars().all()
    if not past:
        return ""

    lines = [f"\n이 계정의 과거 위협 기록: {len(past)}건"]
    for t in past:
        date_str = t.detected_at.strftime("%Y-%m-%d") if t.detected_at else "알 수 없음"
        lines.append(f"- [{date_str}] {t.severity} / {t.threat_type}")
    return "\n".join(lines)


# ── JSON 추출 헬퍼 ────────────────────────────────────────────────────

def _extract_json(text: str) -> dict | None:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


# ── Gemini 2.5 Flash — 단건 ──────────────────────────────────────────

async def _call_gemini_l3(
    content: str,
    threat_type: str,
    severity: str,
    system_prompt: str,
) -> dict | None:
    if not settings.gemini_api_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            "gemini-2.5-flash-preview-05-20",
            system_instruction=system_prompt,
        )
        user_msg = f"위협유형:{threat_type}\n심각도:{severity}\n\n{content[:500]}"
        response = await asyncio.to_thread(
            model.generate_content,
            user_msg,
            generation_config={"max_output_tokens": 300},
        )
        parsed = _extract_json(response.text)
        if not parsed:
            return None
        return {
            "ai_analysis": f"[{parsed.get('threat_assessment', '')}] {parsed.get('analysis', '')}",
            "ai_response_suggestion": "\n".join(
                f"{i + 1}. {s}" for i, s in enumerate(parsed.get("response_suggestion", []))
            ),
            "is_organized_attack": parsed.get("is_organized_attack", False),
            "legal_action_required": parsed.get("legal_action_required", False),
        }
    except Exception as e:
        err_str = f"{type(e).__name__}{e}"
        if "ResourceExhausted" in err_str or "429" in str(e) or "quota" in str(e).lower():
            logger.warning("Gemini L3 429 — Claude 폴백 시도")
        else:
            logger.warning("Gemini L3 호출 실패: %s", e)
        return None


# ── Claude Haiku 폴백 — 단건 ─────────────────────────────────────────

async def _call_claude_l3(
    content: str,
    threat_type: str,
    severity: str,
    system_prompt: str,
) -> dict | None:
    if not settings.anthropic_api_key:
        return None
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        message = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": (
                    f"위협 유형: {threat_type}\n"
                    f"심각도: {severity}\n\n"
                    f"콘텐츠:\n{content}"
                ),
            }],
        )
        text = message.content[0].text
        parsed = _extract_json(text)
        if parsed:
            return {
                "ai_analysis": f"[{parsed.get('threat_assessment', '')}] {parsed.get('analysis', '')}",
                "ai_response_suggestion": "\n".join(
                    f"{i + 1}. {s}" for i, s in enumerate(parsed.get("response_suggestion", []))
                ),
            }
        parts = text.split("3. 즉각 대응 방안", 1)
        analysis = parts[0].strip()
        suggestion = ("3. 즉각 대응 방안" + parts[1]).strip() if len(parts) > 1 else text.strip()
        return {"ai_analysis": analysis, "ai_response_suggestion": suggestion}
    except Exception as e:
        logger.warning("Claude L3 호출 실패: %s", e)
        return None


# ── Gemini 2.5 Flash — 클러스터 ──────────────────────────────────────

async def _call_gemini_cluster(
    user_message: str,
    system_prompt: str,
) -> dict | None:
    if not settings.gemini_api_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            "gemini-2.5-flash-preview-05-20",
            system_instruction=system_prompt,
        )
        response = await asyncio.to_thread(
            model.generate_content,
            user_message,
            generation_config={"max_output_tokens": 400},
        )
        tokens_used = (
            getattr(response.usage_metadata, "prompt_token_count", 0)
            + getattr(response.usage_metadata, "candidates_token_count", 0)
        )
        parsed = _extract_json(response.text)
        if parsed:
            parsed["tokens_used"] = tokens_used
            return parsed
        return None
    except Exception as e:
        logger.warning("Gemini 클러스터 분석 실패: %s", e)
        return None


# ── Claude Haiku 폴백 — 클러스터 ─────────────────────────────────────

async def _call_claude_cluster(
    user_message: str,
    system_prompt: str,
) -> dict | None:
    if not settings.anthropic_api_key:
        return None
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        message = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=800,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        tokens_used = message.usage.input_tokens + message.usage.output_tokens
        parsed = _extract_json(message.content[0].text)
        if parsed:
            parsed["tokens_used"] = tokens_used
            return parsed
        return None
    except Exception as e:
        logger.warning("Claude 클러스터 분석 실패: %s", e)
        return None


# ── 단건 분석 ────────────────────────────────────────────────────────

async def analyze(
    content: str,
    threat_type: str,
    severity: str,
    profile_id: int | None = None,
    db: AsyncSession | None = None,
    source_account: str | None = None,
) -> dict:
    """단건 위협 심층 분석. Gemini 2.5 Flash → Claude Haiku → Mock."""
    cache_key = "l3:" + hashlib.sha256(
        f"{profile_id}:{source_account}:{content[:200]}".encode()
    ).hexdigest()[:32]

    cached = await cache.get(cache_key)
    if cached:
        try:
            result = json.loads(cached)
            result["_cached"] = True
            return result
        except json.JSONDecodeError:
            pass

    customer_context = ""
    account_history = ""
    if db:
        if profile_id:
            customer_context = await _build_customer_context(profile_id, db)
        if source_account:
            account_history = await _build_account_history(source_account, db)

    system_prompt = _L3_ANALYSIS_PROMPT_TEMPLATE.format(
        customer_context=customer_context,
        account_history=account_history,
    ).strip()

    result = await _call_gemini_l3(content, threat_type, severity, system_prompt)
    if not result:
        result = await _call_claude_l3(content, threat_type, severity, system_prompt)
    if not result:
        return _mock_analysis(content, severity)

    await cache.setex(cache_key, _L3_CACHE_TTL, json.dumps(result))
    return result


# ── 클러스터 분석 ────────────────────────────────────────────────────

async def deep_analyze_cluster(
    threats: list[dict],
    profile_id: int,
    db: AsyncSession,
) -> dict:
    """연관 위협 묶음(최대 10건) 분석. Gemini 2.5 Flash → Claude Haiku → Mock."""
    if not threats:
        return _mock_cluster([])

    threats = threats[:10]

    cluster_key = "l3c:" + hashlib.sha256(
        json.dumps(
            [t.get("content", "")[:100] for t in threats],
            ensure_ascii=False,
        ).encode()
    ).hexdigest()[:32]

    cached = await cache.get(cluster_key)
    if cached:
        try:
            result = json.loads(cached)
            result["_cached"] = True
            return result
        except json.JSONDecodeError:
            pass

    customer_context = await _build_customer_context(profile_id, db)
    system_prompt = _CLUSTER_SYSTEM_PROMPT.format(customer_context=customer_context).strip()

    lines: list[str] = []
    for i, t in enumerate(threats, 1):
        dt = t.get("detected_at", "")
        if isinstance(dt, datetime):
            dt = dt.strftime("%Y-%m-%d %H:%M")
        lines.append(
            f"[{i}] 계정:{t.get('source_account', '?')} "
            f"플랫폼:{t.get('platform', '?')} "
            f"시간:{dt}\n"
            f"{t.get('content', '')[:200]}"
        )
    user_message = "\n---\n".join(lines)

    result = await _call_gemini_cluster(user_message, system_prompt)
    if not result:
        result = await _call_claude_cluster(user_message, system_prompt)
    if not result:
        return _mock_cluster(threats)

    await cache.setex(cluster_key, _L3_CACHE_TTL, json.dumps(result, default=str))
    return result


# ── 오탐 피드백 ──────────────────────────────────────────────────────

async def record_feedback(
    threat_id: int,
    original_verdict: str,
    actual_verdict: str,
    marked_by: int,
    db: AsyncSession,
) -> None:
    from backend.models.orm import FeedbackLog
    log = FeedbackLog(
        threat_id=threat_id,
        original_verdict=original_verdict,
        actual_verdict=actual_verdict,
        marked_by=marked_by,
        marked_at=datetime.utcnow(),
    )
    db.add(log)
    try:
        await db.commit()
    except Exception as e:
        logger.warning("FeedbackLog 저장 실패: %s", e)
        await db.rollback()


# ── Mock ──────────────────────────────────────────────────────────────

def _mock_analysis(content: str, severity: str) -> dict:
    return {
        "ai_analysis": (
            f"[Mock] 심각도 {severity} 위협이 탐지되었습니다. "
            "실제 분석을 위해 GEMINI_API_KEY 또는 ANTHROPIC_API_KEY를 설정하세요."
        ),
        "ai_response_suggestion": (
            "1. 해당 게시물 모니터링 지속\n"
            "2. 필요 시 플랫폼 신고 절차 진행\n"
            "3. 법무팀 검토 요청"
        ),
    }


def _mock_cluster(threats: list[dict], tokens_used: int = 0) -> dict:
    return {
        "is_same_campaign": False,
        "campaign_type": None,
        "bot_probability": 0.0,
        "coordination_indicators": [],
        "risk_level": "low",
        "ai_analysis": (
            f"[Mock] {len(threats)}건 위협 클러스터 분석. "
            "GEMINI_API_KEY 설정 시 실제 분석이 실행됩니다."
        ),
        "ai_response_suggestion": (
            "1. 추가 모니터링 지속\n"
            "2. 유사 패턴 추적\n"
            "3. 필요 시 전문가 보고"
        ),
        "tokens_used": tokens_used,
    }


# ── 프로파일 컨텍스트 빌더 ────────────────────────────────────────────

def build_profile_context(profile, past_threats: list | None = None) -> str:
    aliases_str = ", ".join(
        f"{alias}(가중치:{weight:.1f})"
        for alias, weight in (profile.aliases or [])[:10]
    ) or "없음"

    handles_str = ", ".join(
        f"{platform}: {handle}"
        for platform, handle in (profile.official_handles or {}).items()
    ) or "없음"

    execs_str = "\n".join(
        f"  - {e['role']} {e['name']} (우선순위:{e.get('priority', 2)})"
        for e in (profile.executives or [])[:5]
    ) or "  등록된 임직원 없음"

    sensitive_kw = ", ".join(
        profile.industry_config.get("sensitive_keywords", [])
    ) or "없음"

    past_str = ""
    if past_threats:
        past_str = (
            f"\n[이 계정의 과거 위협 기록]\n"
            f"총 {len(past_threats)}건"
        )

    return (
        f"[고객 프로파일]\n"
        f"기업명: {profile.display_name}\n"
        f"업종: {profile.industry}\n"
        f"유형: {'기업' if profile.profile_type == 'company' else '개인(인플루언서)'}\n\n"
        f"[이름 변형 목록] (가중치 높은 순)\n{aliases_str}\n\n"
        f"[공식 SNS 계정] (이 계정들은 위협이 아님)\n{handles_str}\n\n"
        f"[모니터링 임직원]\n{execs_str}\n\n"
        f"[업종 민감 키워드]\n{sensitive_kw}\n\n"
        f"[알림 임계값]\n"
        f"이 고객의 임계값: {profile.industry_config.get('alert_threshold', 60)}점 이상 시 즉각 대응"
        f"{past_str}"
    )
