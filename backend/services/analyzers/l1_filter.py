"""L1 규칙 기반 위협 필터 — 비용 $0, 즉시 처리"""
from __future__ import annotations

import re

from backend.services.analyzers.keyword_database import (
    KEYWORD_DATABASE,
    NEGATIVE_KEYWORD_LIST,
    CRITICAL_BYPASS,
)

_PASS_THRESHOLD = 0.05  # 이 점수 이상이면 L2로 전달


def _has_brand(text_lower: str, brand_keywords: list[str]) -> bool:
    return any(kw.lower() in text_lower for kw in brand_keywords if kw)


def _any_match(text_lower: str, keywords: list[str]) -> bool:
    return any(kw.lower() in text_lower for kw in keywords)


def l1_filter(
    text: str,
    brand_keywords: list[str] | None = None,
) -> dict:
    """
    텍스트를 L1 규칙 기반으로 분석한다.

    Args:
        text: 분석할 콘텐츠 텍스트
        brand_keywords: 브랜드명 + 별칭 목록 (requires_brand 카테고리에 사용)

    Returns:
        pass: bool — True 이면 L2로 전달
        score: float — 0.0~1.0 위협 점수
        severity: str | None — "critical"|"high"|"medium"|"low"|None
        auto_critical: bool — CRITICAL_BYPASS 히트
        matched_categories: list[str]
        negative_filter_applied: bool
    """
    text_lower = text.lower()
    brand_ok = bool(brand_keywords and _has_brand(text_lower, brand_keywords))

    # ── 1. CRITICAL_BYPASS 체크 ─────────────────────────────────────
    if not CRITICAL_BYPASS.get("requires_brand", False) or brand_ok:
        if _any_match(text_lower, CRITICAL_BYPASS["keywords"]):
            return {
                "pass": True,
                "score": 1.0,
                "severity": "critical",
                "auto_critical": True,
                "matched_categories": ["CRITICAL_BYPASS"],
                "negative_filter_applied": False,
            }

    # ── 2. KEYWORD_DATABASE 스캔 ────────────────────────────────────
    raw_score = 0.0
    matched: list[str] = []

    for cat_name, cat_data in KEYWORD_DATABASE.items():
        if cat_name == "CRITICAL_BYPASS":
            continue
        if cat_data.get("requires_brand", False) and not brand_ok:
            continue
        if _any_match(text_lower, cat_data["keywords"]):
            raw_score += cat_data["weight"]
            matched.append(cat_name)

    # ── 3. 음성 필터 (40% 감소) ─────────────────────────────────────
    neg_applied = False
    if raw_score > 0 and _any_match(text_lower, NEGATIVE_KEYWORD_LIST):
        raw_score *= 0.60
        neg_applied = True

    # ── 4. 정규화 (0.0~1.0 클램프) ─────────────────────────────────
    score = round(min(1.0, raw_score), 4)

    # ── 5. 심각도 분류 ──────────────────────────────────────────────
    if score >= 0.70:
        severity: str | None = "critical"
    elif score >= 0.45:
        severity = "high"
    elif score >= 0.25:
        severity = "medium"
    elif score >= _PASS_THRESHOLD:
        severity = "low"
    else:
        severity = None

    return {
        "pass": score >= _PASS_THRESHOLD,
        "score": score,
        "severity": severity,
        "auto_critical": False,
        "matched_categories": matched,
        "negative_filter_applied": neg_applied,
    }


# ── 내부 헬퍼 (l1_filter_with_profile에서 재사용) ─────────────────────────────

def _check_keyword_database(
    content: str,
    account_name: str,
    brand_mentioned: bool,
) -> dict:
    """기존 KEYWORD_DATABASE 스캔 로직을 dict로 반환한다."""
    text_lower = content.lower()
    raw_score = 0.0
    matched: list[str] = []

    for cat_name, cat_data in KEYWORD_DATABASE.items():
        if cat_name == "CRITICAL_BYPASS":
            continue
        if cat_data.get("requires_brand", False) and not brand_mentioned:
            continue
        if _any_match(text_lower, cat_data["keywords"]):
            raw_score += cat_data["weight"]
            matched.append(cat_name)

    neg_applied = False
    if raw_score > 0 and _any_match(text_lower, NEGATIVE_KEYWORD_LIST):
        raw_score *= 0.60
        neg_applied = True

    score = round(min(1.0, raw_score), 4)
    category = matched[0][0] if matched and matched[0][0] in ("A", "B", "C") else "B"

    return {
        "score": score,
        "category": category,
        "flags": matched,
        "auto_critical": False,
        "negative_filter_applied": neg_applied,
    }


async def l1_filter_with_profile(
    content: str,
    account_name: str,
    profile,  # ProfileLoader.LoadedProfile
    search_keyword: str = "",
) -> dict:
    """
    프로파일 정보를 완전 주입한 강화 L1 필터.

    기존 l1_filter()와 호환: pass/score/severity/auto_critical/matched_categories/negative_filter_applied
    추가 반환: brand_mentioned, matched_aliases, executive_mentioned, impersonation_score, industry_flags, category
    """
    text_lower = content.lower()

    # 1. 공식 계정 화이트리스트 — 자기 계정이면 즉시 제외
    for handle in profile.official_handles.values():
        clean_handle = handle.lower().lstrip("@")
        clean_account = account_name.lower().lstrip("@")
        if clean_handle and clean_handle == clean_account:
            return {
                "pass": False,
                "score": 0.0,
                "severity": None,
                "auto_critical": False,
                "matched_categories": [],
                "negative_filter_applied": False,
                "reason": "official_account_whitelist",
                "brand_mentioned": False,
                "matched_aliases": [],
                "executive_mentioned": [],
                "impersonation_score": 0.0,
                "industry_flags": [],
                "category": "B",
            }

    # 2. CRITICAL_BYPASS
    brand_kws = [alias for alias, _ in profile.aliases] + [profile.display_name]
    brand_ok = _has_brand(text_lower, brand_kws)
    if not CRITICAL_BYPASS.get("requires_brand", False) or brand_ok:
        if _any_match(text_lower, CRITICAL_BYPASS["keywords"]):
            return {
                "pass": True,
                "score": 1.0,
                "severity": "critical",
                "auto_critical": True,
                "matched_categories": ["CRITICAL_BYPASS"],
                "negative_filter_applied": False,
                "brand_mentioned": brand_ok,
                "matched_aliases": [],
                "executive_mentioned": [],
                "impersonation_score": 0.0,
                "industry_flags": [],
                "category": "B",
            }

    # 3. alias 가중치 매칭 (display_name이 aliases에 없으면 weight=1.0으로 추가)
    brand_score = 0.0
    matched_aliases: list[str] = []
    all_names: list[tuple[str, float]] = list(profile.aliases)
    if profile.display_name and not any(
        a.lower() == profile.display_name.lower() for a, _ in profile.aliases
    ):
        all_names = [(profile.display_name, 1.0)] + all_names
    for alias, weight in all_names:
        if alias.lower() in text_lower:
            brand_score += weight
            matched_aliases.append(alias)
    brand_mentioned = brand_score >= 0.1  # 0.3→0.1: 민감도 향상

    # 검색 키워드와 alias 간 양방향 포함 관계 확인
    # "삼성전자 불만" 검색 → alias "삼성전자" 포함 OR
    # "갤럭시" 검색 → alias "갤럭시S24" 에 포함
    if not brand_mentioned and search_keyword:
        sk_lower = search_keyword.lower()
        for alias, _ in all_names:
            a_lower = alias.lower()
            if a_lower in sk_lower or sk_lower in a_lower:
                brand_mentioned = True
                matched_aliases.append(alias)
                break
        # 프로파일에 등록된 search_keywords 중 하나와 일치하면 brand_mentioned 강제 활성화
        if not brand_mentioned and hasattr(profile, "search_keywords"):
            for pk in profile.search_keywords:
                if pk and (pk.lower() in sk_lower or sk_lower in pk.lower()):
                    brand_mentioned = True
                    break

    # 4. 임직원 이름 언급 (Module C)
    executive_mentioned: list[dict] = []
    for exec_info in profile.executives:
        if exec_info["name"] in content:
            executive_mentioned.append(exec_info)

    # 5. 업종 민감 키워드
    industry_flags: list[str] = []
    for kw in profile.industry_config.get("sensitive_keywords", []):
        if kw in content:
            industry_flags.append(kw)

    # 6. 사칭 계정명 탐지
    impersonation_score = 0.0
    for handle in profile.official_handles.values():
        official_clean = handle.lower().lstrip("@")
        account_clean = account_name.lower().lstrip("@")
        if not official_clean:
            continue
        if official_clean in account_clean or account_clean in official_clean:
            if official_clean != account_clean:
                impersonation_score += 0.8
        if re.search(rf"{re.escape(official_clean)}[\._\-]?\d+$", account_clean):
            impersonation_score = max(impersonation_score, 0.9)
    impersonation_score = min(impersonation_score, 1.0)

    # 7. 기존 KEYWORD_DATABASE 체크
    kw_result = _check_keyword_database(content, account_name, brand_mentioned)

    # 8. 업종 임계값 (기본 0.15, 업종 multiplier로 낮아짐)
    industry_threshold = 0.08 / profile.industry_config["risk_multiplier"]

    # 9. 최종 스코어 종합
    # brand_mentioned=True 포스트는 최소 industry_threshold 보장 → L2에서 실제 판단
    brand_base = industry_threshold if brand_mentioned else 0.0
    total_score = max(
        kw_result["score"],
        impersonation_score,
        0.6 if executive_mentioned and brand_mentioned else 0.0,
        0.5 if industry_flags and brand_mentioned else 0.0,
        brand_base,
    )
    total_score = round(min(total_score, 1.0), 4)

    # 10. 모듈 분류
    if impersonation_score >= 0.7:
        category = "A"
    elif executive_mentioned:
        category = "C"
    else:
        category = kw_result.get("category", "B")

    # 11. 심각도
    if total_score >= 0.70:
        severity: str | None = "critical"
    elif total_score >= 0.45:
        severity = "high"
    elif total_score >= 0.25:
        severity = "medium"
    elif total_score >= industry_threshold:
        severity = "low"
    else:
        severity = None

    return {
        "pass": total_score >= industry_threshold,
        "score": total_score,
        "severity": severity,
        "auto_critical": False,
        "matched_categories": kw_result["flags"],
        "negative_filter_applied": kw_result["negative_filter_applied"],
        "brand_mentioned": brand_mentioned,
        "matched_aliases": matched_aliases,
        "executive_mentioned": executive_mentioned,
        "impersonation_score": impersonation_score,
        "industry_flags": industry_flags,
        "category": category,
    }
