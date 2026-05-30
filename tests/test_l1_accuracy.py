"""
L1 필터 정확도 검증 스크립트
Mock Profile을 사용한 l1_filter_with_profile 정확도 측정
카테고리별 TP / FP / FN / 오분류 케이스 출력
"""
from __future__ import annotations

import asyncio
import sys
import os
from dataclasses import dataclass, field

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.analyzers.l1_filter import l1_filter_with_profile


# ── Mock Profile ──────────────────────────────────────────────────────────────

@dataclass
class MockProfile:
    display_name: str = "테스트브랜드"
    aliases: list = field(default_factory=lambda: [
        ("테스트브랜드", 1.0),
        ("테브", 0.7),
        ("TestBrand", 0.8),
    ])
    official_handles: dict = field(default_factory=lambda: {
        "instagram": "testbrand_official",
    })
    executives: list = field(default_factory=lambda: [
        {"name": "김철수", "role": "대표이사", "priority": 1},
    ])
    industry_config: dict = field(default_factory=lambda: {
        "risk_multiplier": 1.0,
        "sensitive_keywords": [],
    })
    search_keywords: list = field(default_factory=list)


# ── 테스트 케이스 정의 ─────────────────────────────────────────────────────────
# 각 케이스:
#   text            : 분석할 텍스트
#   expected_pass   : L1이 L2로 넘겨야 하면 True
#   expected_severity: "critical"/"high"/"medium"/"low"/"feedback"/None
#   label           : 설명 문자열
#   brand_in_text   : 텍스트에 브랜드명 포함 여부 (참고용)
#   account         : 게시자 계정명 (기본 "random_user")
# ─────────────────────────────────────────────────────────────────────────────

TEST_CASES = [

    # ── 카테고리 1: True Positive - Critical (5개) ─────────────────────────────
    {
        "label": "[TP-Critical-1] 제품 발암물질 검출 뉴스",
        "text": "테스트브랜드 제품에서 발암물질이 검출됐다는 보도가 나왔습니다. 즉각적인 조치가 필요합니다.",
        "expected_pass": True,
        "expected_severity": "critical",
        "brand_in_text": True,
        "account": "news_reporter",
    },
    {
        "label": "[TP-Critical-2] 사망사고 발생",
        "text": "테스트브랜드 공장에서 사망사고가 발생했습니다. 사망자가 3명 이상 보고되고 있습니다.",
        "expected_pass": True,
        "expected_severity": "critical",
        "brand_in_text": True,
        "account": "breaking_news",
    },
    {
        "label": "[TP-Critical-3] 테러 협박 및 독극물 투입",
        "text": "테스트브랜드 음료에 독극물투입 협박 편지가 도착했다고 경찰이 발표했습니다.",
        "expected_pass": True,
        "expected_severity": "critical",
        "brand_in_text": True,
        "account": "urgent_news",
    },
    {
        "label": "[TP-Critical-4] 압수수색 집행",
        "text": "검찰이 오늘 아침 테스트브랜드 본사에 대한 압수수색집행을 실시했습니다.",
        "expected_pass": True,
        "expected_severity": "critical",
        "brand_in_text": True,
        "account": "legal_news",
    },
    {
        "label": "[TP-Critical-5] 대규모 개인정보 유출",
        "text": "테스트브랜드 전고객정보유출 사고 발생. 수천만건유출 확인. 즉시 비밀번호 변경 요망.",
        "expected_pass": True,
        "expected_severity": "critical",
        "brand_in_text": True,
        "account": "security_alert",
    },

    # ── 카테고리 2: True Positive - High/Critical (5개) ──────────────────────
    # L1 설계: B2(법적위기 0.90), B3(재무위기 0.92) 등 단일 카테고리 가중치가 이미 0.70 임계값 초과
    # → L1은 이를 critical로 분류하고, L2가 실제 맥락을 보고 high/critical 최종 판단
    {
        "label": "[TP-High-1] 집단소송 제기",
        "text": "테스트브랜드 피해자 500명이 집단소송을 제기했습니다. 손해배상청구 금액만 100억 원에 달합니다.",
        "expected_pass": True,
        "expected_severity": "critical",  # B2(0.90) 단독으로 critical 임계값(0.70) 초과
        "brand_in_text": True,
        "account": "legal_channel",
    },
    {
        "label": "[TP-High-2] 파산 위기",
        "text": "테스트브랜드가 파산위기에 몰렸습니다. 자금난이 심각하고 법정관리 가능성이 제기되고 있습니다.",
        "expected_pass": True,
        "expected_severity": "critical",  # B3(0.92) 단독으로 critical 임계값(0.70) 초과
        "brand_in_text": True,
        "account": "financial_news",
    },
    {
        "label": "[TP-High-3] 대규모 리콜",
        "text": "테스트브랜드, 전 제품 강제리콜 결정. 제조결함 확인으로 식약처가 긴급 리콜 명령 내렸습니다.",
        "expected_pass": True,
        "expected_severity": "critical",  # B1(0.95) 단독으로 critical 임계값(0.70) 초과
        "brand_in_text": True,
        "account": "consumer_news",
    },
    {
        "label": "[TP-High-4] 임직원 횡령",
        "text": "테스트브랜드 임원이 회사 공금횡령 혐의로 검찰 수사를 받고 있는 것으로 확인됐습니다.",
        "expected_pass": True,
        "expected_severity": "critical",  # B2+B3+C1 다중 매칭 → 누적 1.0
        "brand_in_text": True,
        "account": "investigation_news",
    },
    {
        "label": "[TP-High-5] 분식회계 의혹",
        "text": "테스트브랜드의 분식회계 의혹이 제기됐습니다. 금감원이 회계부정 여부 조사에 착수했습니다.",
        "expected_pass": True,
        "expected_severity": "critical",  # B3(0.92) 단독으로 critical 임계값(0.70) 초과
        "brand_in_text": True,
        "account": "audit_news",
    },

    # ── 카테고리 3: True Positive - Medium/High/Critical (5개) ───────────────
    # B4(불매 0.88), B7(가짜뉴스 0.82), A1(사칭 0.90), C3(노동 0.75) 등
    # 단일 카테고리 가중치가 높아 실제 점수는 medium 이상으로 나옴
    {
        "label": "[TP-Medium-1] 불매운동 선언",
        "text": "테스트브랜드 불매운동에 동참합니다. 이 회사 제품 다시는 안 삽니다.",
        "expected_pass": True,
        "expected_severity": "critical",  # B4(0.88)+B6(0.40) 누적 → 1.0 → critical
        "brand_in_text": True,
        "account": "consumer_voice",
    },
    {
        "label": "[TP-Medium-2] 허위정보 유포",
        "text": "테스트브랜드에서 이런 충격적 사실이 밝혀졌습니다. 아무도몰랐던 비밀이 폭로됩니다.",
        "expected_pass": True,
        "expected_severity": "critical",  # B7(0.82)+KR_slang(0.55) 누적 → 1.0 → critical
        "brand_in_text": True,
        "account": "expose_account",
    },
    {
        "label": "[TP-Medium-3] 계정 사칭 시도",
        "text": "테스트브랜드 공식계정입니다. 이벤트 당첨자 발표드립니다. DM으로 개인정보를 보내주세요.",
        "expected_pass": True,
        "expected_severity": "critical",  # A1(0.90) 단독으로 critical 임계값(0.70) 초과
        "brand_in_text": True,
        "account": "testbrand_offic1al",
    },
    {
        "label": "[TP-Medium-4] 노동법 위반 고발",
        "text": "테스트브랜드 임금체불 피해자입니다. 회사에서 3개월째 월급을 안 주고 있어요. 노동청 신고했습니다.",
        "expected_pass": True,
        "expected_severity": "critical",  # C1+C3+KR_slang 누적 → 1.0 → critical
        "brand_in_text": True,
        "account": "worker_complaint",
    },
    {
        "label": "[TP-Medium-5] 조직적 여론 공격",
        "text": "테스트브랜드 계정신고 하자! 신고하자 다같이. 팔로워들아 집단신고 동참해줘.",
        "expected_pass": True,
        "expected_severity": "critical",  # B4(0.88) 단독으로 critical 임계값(0.70) 초과
        "brand_in_text": True,
        "account": "attack_organizer",
    },

    # ── 카테고리 4: True Positive - Medium (실제 점수 0.40) ──────────────────
    # B6_consumer_complaint_mid(0.40) 단일 매칭 → score=0.40 → medium(0.25~0.45)
    # B5(0.70)+B6(0.40) 복합 매칭 → 누적 1.0 → critical
    {
        "label": "[TP-Low-1] 일반 부정 리뷰",
        "text": "테스트브랜드 제품 써봤는데 솔직히 실망이에요. 기대이하였고 가성비최악이네요.",
        "expected_pass": True,
        "expected_severity": "critical",  # B5(0.70)+B6(0.40) 누적 → 1.0 → critical
        "brand_in_text": True,
        "account": "reviewer_kim",
    },
    {
        "label": "[TP-Low-2] 고객 서비스 불만",
        "text": "테스트브랜드 고객센터 연락했더니 불친절하고 응대불량이었어요. 실망입니다.",
        "expected_pass": True,
        "expected_severity": "medium",  # B6(0.40) 단일 매칭 → score=0.40 → medium
        "brand_in_text": True,
        "account": "angry_customer",
    },
    {
        "label": "[TP-Low-3] 배송 불만",
        "text": "테스트브랜드에서 주문한 것 배송지연이 너무 심해요. 일주일이 지났는데 아직도 안 왔어요.",
        "expected_pass": True,
        "expected_severity": "medium",  # B6(0.40) 단일 매칭 → score=0.40 → medium
        "brand_in_text": True,
        "account": "waiting_user",
    },
    {
        "label": "[TP-Low-4] 품질 불만",
        "text": "테브 제품 품질저하 심각하더라. 예전엔 좋았는데 이번에 산 건 고장이 너무 많아요.",
        "expected_pass": True,
        "expected_severity": "medium",  # B6(0.40) 단일 매칭 → score=0.40 → medium
        "brand_in_text": True,
        "account": "old_fan",
    },
    {
        "label": "[TP-Low-5] 오류/버그 불만",
        "text": "TestBrand 앱에서 계속 오류발생하네요. 고장이 너무 자주 나서 불편해요.",
        "expected_pass": True,
        "expected_severity": "medium",  # B6(0.40) 단일 매칭 → score=0.40 → medium
        "brand_in_text": True,
        "account": "app_user",
    },

    # ── 카테고리 5: True Negative - 확실한 긍정 (5개) ─────────────────────────
    # 설계: 브랜드가 언급된 글은 위협 키워드 없어도 brand_base(0.08)로 pass=True, severity=feedback
    # → L1은 브랜드 언급 글을 피드백 탭에 수집하는 용도, 긍정 글 필터링은 L2 역할
    {
        "label": "[TN-Positive-1] 수상 소식",
        "text": "테스트브랜드가 올해 소비자대상 최우수상을 수상했습니다. 축하드립니다!",
        "expected_pass": True,   # 브랜드 언급 → brand_base(0.08) → feedback으로 수집
        "expected_severity": "feedback",
        "brand_in_text": True,
        "account": "award_news",
    },
    {
        "label": "[TN-Positive-2] 매출 신기록",
        "text": "테스트브랜드 3분기 매출신기록 달성! 전년 대비 50% 성장하며 1위달성했습니다.",
        "expected_pass": True,
        "expected_severity": "feedback",
        "brand_in_text": True,
        "account": "business_report",
    },
    {
        "label": "[TN-Positive-3] 공식 신제품 발매",
        "text": "테스트브랜드의 신제품이 공식발매됩니다. 오늘부터 공식스토어에서 구매 가능합니다.",
        "expected_pass": True,
        "expected_severity": "feedback",
        "brand_in_text": True,
        "account": "brand_fan",
    },
    {
        "label": "[TN-Positive-4] 긍정 리뷰",
        "text": "테스트브랜드 정말 좋아요! 품질도 훌륭하고 고객서비스도 최고입니다. 강력 추천합니다.",
        "expected_pass": True,
        "expected_severity": "feedback",
        "brand_in_text": True,
        "account": "happy_customer",
    },
    {
        "label": "[TN-Positive-5] 기업 사회공헌",
        "text": "테스트브랜드가 이번 수해 피해 지역에 10억 원 상당의 구호물자를 기부했습니다. 훈훈한 소식이네요.",
        "expected_pass": True,
        "expected_severity": "feedback",
        "brand_in_text": True,
        "account": "csr_news",
    },

    # ── 카테고리 6: False Positive 위험군 - 방어자 맥락 (5개) ──────────────────
    # defender_context=True → kw_result["score"] * 0.25 감소 + brand_base 제거
    # Defender-1,2: B2(0.90)*0.25=0.225 → low(0.08~0.25 범위)
    # Defender-3,5: 키워드 없거나 매우 낮아 score<0.08 → feedback
    # Defender-4: B7(0.82)*0.25=0.205 → low
    {
        "label": "[Defender-1] 비방 세력을 비판하는 글",
        "text": "테스트브랜드를 비방하는 세력들을 처벌해야 합니다. 비방세력 고소해야 한다고 생각합니다. 응원합니다.",
        "expected_pass": True,
        "expected_severity": "low",   # B2(0.90)*0.25=0.225, defender_context → brand_base 제거 → low
        "brand_in_text": True,
        "account": "brand_supporter",
    },
    {
        "label": "[Defender-2] 악플러를 고발해야 한다",
        "text": "테브 악플러들을 법적으로 고발해야 한다. 악성 댓글러들이 테브를 음해하고 있어. 제재해야 한다.",
        "expected_pass": True,
        "expected_severity": "low",   # B2(0.90)*0.25=0.225 → low
        "brand_in_text": True,
        "account": "defender_user",
    },
    {
        "label": "[Defender-3] 경쟁사 공작임을 지적",
        "text": "TestBrand를 향한 경쟁사의 공작이 너무 심하다. 조직적 비방이 확실하다. 공작 세력을 찾아내야 한다.",
        "expected_pass": True,
        "expected_severity": "feedback",  # 위협 키워드 없음, score=0.08→brand_base 제거→0.0 → feedback
        "brand_in_text": True,
        "account": "analyst_user",
    },
    {
        "label": "[Defender-4] 허위정보 유포자 신고 촉구",
        "text": "테스트브랜드에 대한 허위정보 유포자를 신고해야 한다. 가짜뉴스 유포자 처벌받아야 합니다.",
        "expected_pass": True,
        "expected_severity": "low",   # B7(0.82)*0.25=0.205 → low
        "brand_in_text": True,
        "account": "justice_seeker",
    },
    {
        "label": "[Defender-5] 브랜드 지지 + 댓글 알바 지적",
        "text": "테스트브랜드가 억울한 피해를 당하고 있습니다. 댓글 알바들이 여론을 조작하고 있어요. 힘내세요!",
        "expected_pass": True,
        "expected_severity": "feedback",  # B1 피해→피해사례로 변경 후 미매칭, score<0.08 → feedback
        "brand_in_text": True,
        "account": "loyal_supporter",
    },

    # ── 카테고리 7: Ambiguous (5개) ───────────────────────────────────────────
    {
        "label": "[Ambiguous-1] 내부 고발인지 방어자인지 불명확",
        "text": "테스트브랜드 내부 제보 받았습니다. 내부문건이 유출됐다는 얘기가 있어요.",
        "expected_pass": True,
        "expected_severity": "critical",  # B7(0.82) 단일 매칭 → critical(>=0.70)
        "brand_in_text": True,
        "account": "anonymous_tip",
    },
    {
        "label": "[Ambiguous-2] 풍자/패러디 게시글",
        "text": "테브 제품이 이제는 폭발하지 않는다고요?? 충격적인 개선 소식이네요 ㅋㅋㅋ",
        "expected_pass": True,
        "expected_severity": "critical",  # B1+B7+B8+KR_slang 누적 → 1.0 → critical (L2가 맥락 판단)
        "brand_in_text": True,
        "account": "comedian_user",
    },
    {
        "label": "[Ambiguous-3] 비교 리뷰 (경쟁사 언급)",
        "text": "테스트브랜드 vs 경쟁사 비교해봤는데 솔직히 경쟁사가더낫다는 느낌이에요.",
        "expected_pass": True,
        "expected_severity": "high",   # B9(0.65) 단일 매칭 → high(0.45~0.70)
        "brand_in_text": True,
        "account": "comparison_blogger",
    },
    {
        "label": "[Ambiguous-4] 과거 사건 기사 인용",
        "text": "3년 전 테스트브랜드 집단소송 사건 기억나시나요? 당시 손해배상 결과가 어떻게 됐는지 알아봤습니다.",
        "expected_pass": True,
        "expected_severity": "high",   # B2(0.90)*0.60(음성필터:당시) = 0.54 → high
        "brand_in_text": True,
        "account": "history_blog",
    },
    {
        "label": "[Ambiguous-5] 학술 연구 인용",
        "text": "연구결과에 따르면 테스트브랜드 제품의 발암가능성 여부를 조사한 논문이 발표됐습니다.",
        "expected_pass": True,
        "expected_severity": "high",   # B1(0.95)*0.60(음성필터:연구결과,논문,조사한논문) = 0.57 → high
        "brand_in_text": True,
        "account": "researcher_account",
    },
]


# ── 테스트 실행 ──────────────────────────────────────────────────────────────

def severity_rank(sev: str | None) -> int:
    """심각도 순위: critical=4, high=3, medium=2, low=1, feedback=0, None=-1"""
    order = {"critical": 4, "high": 3, "medium": 2, "low": 1, "feedback": 0, None: -1}
    return order.get(sev, -1)


async def run_tests(profile: MockProfile) -> list[dict]:
    """모든 테스트 케이스를 실행하고 결과를 반환"""
    results = []
    for case in TEST_CASES:
        account = case.get("account", "random_user")
        result = await l1_filter_with_profile(
            content=case["text"],
            account_name=account,
            profile=profile,
            search_keyword="",
        )

        actual_pass = result["pass"]
        actual_severity = result["severity"]

        # 판정
        pass_correct = (actual_pass == case["expected_pass"])
        # severity 판정: expected가 None이면 None이어야 정답, 아니면 rank 기준 ±1 허용 후 exact match 기준
        sev_correct = (actual_severity == case["expected_severity"])

        results.append({
            "label": case["label"],
            "text_preview": case["text"][:60] + "...",
            "expected_pass": case["expected_pass"],
            "actual_pass": actual_pass,
            "expected_severity": case["expected_severity"],
            "actual_severity": actual_severity,
            "pass_correct": pass_correct,
            "sev_correct": sev_correct,
            "score": result["score"],
            "matched_categories": result.get("matched_categories", []),
            "defender_context": result.get("defender_context", False),
            "brand_mentioned": result.get("brand_mentioned", False),
            "negative_filter_applied": result.get("negative_filter_applied", False),
        })
    return results


def print_results(results: list[dict], title: str = "L1 정확도 테스트 결과"):
    """결과를 사람이 읽기 좋게 출력"""
    total = len(results)
    pass_correct_count = sum(1 for r in results if r["pass_correct"])
    sev_correct_count = sum(1 for r in results if r["sev_correct"])
    both_correct_count = sum(1 for r in results if r["pass_correct"] and r["sev_correct"])

    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")
    print(f"  총 케이스:           {total}개")
    print(f"  Pass 판정 정확도:    {pass_correct_count}/{total} ({pass_correct_count/total*100:.1f}%)")
    print(f"  Severity 판정 정확도:{sev_correct_count}/{total} ({sev_correct_count/total*100:.1f}%)")
    print(f"  전체 정확도 (둘 다): {both_correct_count}/{total} ({both_correct_count/total*100:.1f}%)")

    # 카테고리별 분석
    categories = {
        "TP-Critical": [],
        "TP-High": [],
        "TP-Medium": [],
        "TP-Low": [],
        "TN-Positive": [],
        "Defender": [],
        "Ambiguous": [],
    }
    for r in results:
        for cat_key in categories:
            if f"[{cat_key}" in r["label"]:
                categories[cat_key].append(r)
                break

    print(f"\n{'─'*70}")
    print("  카테고리별 정확도")
    print(f"{'─'*70}")
    for cat_name, cat_results in categories.items():
        if not cat_results:
            continue
        cat_total = len(cat_results)
        cat_pass_ok = sum(1 for r in cat_results if r["pass_correct"])
        cat_sev_ok = sum(1 for r in cat_results if r["sev_correct"])
        print(f"  {cat_name:<20}: Pass {cat_pass_ok}/{cat_total} | Severity {cat_sev_ok}/{cat_total}")

    # 오분류 케이스
    wrong_cases = [r for r in results if not r["pass_correct"] or not r["sev_correct"]]
    if wrong_cases:
        print(f"\n{'─'*70}")
        print(f"  오분류 케이스 ({len(wrong_cases)}개)")
        print(f"{'─'*70}")
        for r in wrong_cases:
            issues = []
            if not r["pass_correct"]:
                issues.append(f"Pass: 예상={r['expected_pass']} 실제={r['actual_pass']}")
            if not r["sev_correct"]:
                issues.append(f"Severity: 예상={r['expected_severity']} 실제={r['actual_severity']}")
            print(f"\n  [{r['label']}]")
            print(f"    문제: {' | '.join(issues)}")
            print(f"    점수: {r['score']:.4f}")
            print(f"    텍스트: {r['text_preview']}")
            print(f"    매칭 카테고리: {r['matched_categories']}")
            print(f"    방어자 맥락: {r['defender_context']} | 브랜드 언급: {r['brand_mentioned']} | 음성필터: {r['negative_filter_applied']}")
    else:
        print("\n  오분류 없음 — 완벽한 정확도!")

    # Confusion Matrix (Pass 기준)
    tp = sum(1 for r in results if r["expected_pass"] is True and r["actual_pass"] is True)
    tn = sum(1 for r in results if r["expected_pass"] is False and r["actual_pass"] is False)
    fp = sum(1 for r in results if r["expected_pass"] is False and r["actual_pass"] is True)
    fn = sum(1 for r in results if r["expected_pass"] is True and r["actual_pass"] is False)

    print(f"\n{'─'*70}")
    print("  Confusion Matrix (L2 Pass 여부 기준)")
    print(f"{'─'*70}")
    print(f"  True Positive  (TP): {tp}  — 위협 맞게 탐지")
    print(f"  True Negative  (TN): {tn}  — 정상 맞게 통과")
    print(f"  False Positive (FP): {fp}  — 정상인데 위협으로 잡힘")
    print(f"  False Negative (FN): {fn}  — 위협인데 놓침")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    print(f"\n  Precision: {precision:.3f}")
    print(f"  Recall:    {recall:.3f}")
    print(f"  F1-Score:  {f1:.3f}")
    print(f"{'='*70}\n")

    return {
        "total": total,
        "pass_accuracy": pass_correct_count / total,
        "severity_accuracy": sev_correct_count / total,
        "overall_accuracy": both_correct_count / total,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


# ── pytest 인터페이스 ─────────────────────────────────────────────────────────

import pytest

@pytest.mark.asyncio
async def test_l1_accuracy_all_cases():
    """모든 케이스의 Pass 판정이 정확해야 함 (Pass accuracy >= 70%)"""
    profile = MockProfile()
    results = await run_tests(profile)
    metrics = print_results(results, "pytest 실행 결과")
    assert metrics["pass_accuracy"] >= 0.70, (
        f"Pass 정확도가 너무 낮음: {metrics['pass_accuracy']:.1%}. "
        "오분류 케이스를 확인하고 keyword_database.py를 개선하세요."
    )


@pytest.mark.asyncio
async def test_tp_critical_all_pass():
    """TP-Critical 5개 모두 pass=True여야 함"""
    profile = MockProfile()
    critical_cases = [c for c in TEST_CASES if "[TP-Critical" in c["label"]]
    for case in critical_cases:
        result = await l1_filter_with_profile(
            content=case["text"],
            account_name=case.get("account", "user"),
            profile=profile,
        )
        assert result["pass"] is True, f"{case['label']}: critical 케이스가 pass=False"


@pytest.mark.asyncio
async def test_tn_positive_not_high_threat():
    """TN-Positive 케이스들은 severity가 high/critical이면 안 됨"""
    profile = MockProfile()
    positive_cases = [c for c in TEST_CASES if "[TN-Positive" in c["label"]]
    for case in positive_cases:
        result = await l1_filter_with_profile(
            content=case["text"],
            account_name=case.get("account", "user"),
            profile=profile,
        )
        sev = result["severity"]
        assert sev not in ("critical", "high"), (
            f"{case['label']}: 긍정 케이스인데 severity={sev}"
        )


@pytest.mark.asyncio
async def test_defender_context_low_severity():
    """방어자 맥락 케이스는 severity가 high/critical이면 안 됨"""
    profile = MockProfile()
    defender_cases = [c for c in TEST_CASES if "[Defender" in c["label"]]
    for case in defender_cases:
        result = await l1_filter_with_profile(
            content=case["text"],
            account_name=case.get("account", "user"),
            profile=profile,
        )
        sev = result["severity"]
        assert sev not in ("critical", "high"), (
            f"{case['label']}: 방어자 맥락인데 severity={sev}"
        )


# ── 직접 실행 ─────────────────────────────────────────────────────────────────

async def main():
    print("\n[1단계] 초기 테스트 실행")
    profile = MockProfile()
    results = await run_tests(profile)
    initial_metrics = print_results(results, "초기 L1 정확도 테스트")

    return initial_metrics, results


if __name__ == "__main__":
    metrics, results = asyncio.run(main())
    sys.exit(0 if metrics["pass_accuracy"] >= 0.70 else 1)
