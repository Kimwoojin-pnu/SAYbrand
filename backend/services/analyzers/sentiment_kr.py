"""
KNU 한국어 감성 사전 + 커스텀 SNS 사전 기반 감성 분류기 (API 불필요)

알고리즘:
1. KNU 감성 사전 14,854개 단어 (-2~+2 → 정규화 -1~+1)
2. 커스텀 SNS/브랜드 위기 어휘 450+ 항목
3. 구문(phrase) 스캔 → 단어(token) 스캔 순으로 처리 (이중 계산 방지)
4. 포괄적 어미 제거 (해요/합니다/이고/하고 등 30+ 패턴)
5. 부정어 순방향 + 역방향("X 없다") 처리
6. 강조어 배율 적용
7. 감정 카테고리 분류
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

_DICT_PATH = Path(__file__).parent.parent.parent / "data" / "knu_senti_dict.txt"


# ── 커스텀 SNS/브랜드 사전 ─────────────────────────────────────────────
_CUSTOM_LEXICON: dict[str, float] = {
    # ── 강한 부정 ─────────────────────────────────────────────────────
    "쓰레기": -0.95, "최악": -0.9, "최저": -0.8, "최하": -0.8,
    "빡침": -0.85, "빡쳐": -0.85, "빡친다": -0.85,
    "거지같다": -0.9, "거지같아": -0.9,
    "구리다": -0.7, "구려": -0.7, "구림": -0.7,
    "별로야": -0.6, "별론데": -0.6, "별로임": -0.6, "별로": -0.5,
    "실망이야": -0.75, "실망스러워": -0.75, "실망스럽다": -0.75,
    "당황스러워": -0.5, "당황스럽다": -0.5, "황당하다": -0.6, "황당해": -0.6,
    "어이없어": -0.7, "어이없다": -0.7, "어이없네": -0.7,
    "답답해": -0.6, "답답하다": -0.6, "답답함": -0.6,
    "기분나빠": -0.7, "기분나쁘다": -0.7,
    "짜증나": -0.8, "짜증남": -0.8, "짜증임": -0.8, "짜증": -0.7,
    "열받아": -0.8, "열받음": -0.8,
    "불쾌해": -0.7, "불쾌함": -0.7, "불쾌한": -0.7, "불쾌": -0.65,
    "화남": -0.8, "화가나": -0.8,
    "욕설": -0.7, "막말": -0.7,
    "불친절": -0.75, "불친절해": -0.75, "불친절함": -0.75,
    "무성의": -0.65, "성의없다": -0.7, "성의없어": -0.7,
    # ── 소비자 불만/제품 결함 ─────────────────────────────────────────
    "불량": -0.85, "불량품": -0.9, "파손": -0.8, "파손됨": -0.8,
    "하자": -0.8, "하자품": -0.9, "불량이에요": -0.9,
    "먹통": -0.75, "버벅": -0.65, "버벅임": -0.65, "렉": -0.65,
    "오류": -0.65, "에러": -0.65, "고장": -0.75, "고장남": -0.75,
    "환불거부": -0.95, "환불거절": -0.9,
    "환불안됨": -0.9, "환불각": -0.85,
    "사기": -0.95, "사기꾼": -1.0, "사기업체": -1.0, "먹튀": -1.0,
    "허위광고": -0.95, "과대광고": -0.8, "거짓광고": -0.95,
    "가품": -0.9, "짝퉁": -0.9,
    "불매": -0.9, "불매운동": -1.0, "보이콧": -0.9,
    "고소": -0.7, "소송": -0.65, "고발": -0.75,
    "집단소송": -0.9, "소비자고발": -0.85,
    "박제": -0.65, "별점테러": -0.9, "악플": -0.8, "댓글테러": -0.85,
    "탈주": -0.7, "탈퇴": -0.5, "탈주각": -0.8, "탈출각": -0.75,
    # ── 초성/SNS 부정어 ──────────────────────────────────────────────
    "ㅂㄷ": -0.9, "ㅂㄷㄷ": -0.95, "ㅂㄷㄷㄷ": -1.0,
    "ㄷㅊ": -0.8, "ㅈㄴ": -0.7, "ㅅㅂ": -1.0, "ㅄ": -1.0, "ㅆㅂ": -1.0,
    "ㄷㄷ": -0.55, "ㄷㄷㄷ": -0.7, "덜덜": -0.5,
    "ㅠㅠ": -0.6, "ㅜㅜ": -0.6, "ㅜ": -0.3,
    "개최악": -1.0, "개짜증": -0.95, "개별로": -0.85, "개구림": -0.9,
    "씹최악": -1.0, "씹짜증": -1.0,
    "역레전드": -0.9,
    "어그로": -0.55,
    # ── 강한 긍정 ────────────────────────────────────────────────────
    "만족": 0.7, "만족스러워": 0.75, "만족스럽다": 0.75, "만족합니다": 0.8,
    "강추": 0.9, "강력추천": 0.95,
    "추천": 0.7, "추천합니다": 0.75, "추천해요": 0.75,
    "재구매": 0.8, "또삼": 0.8, "또구매": 0.8, "재주문": 0.75,
    "혜자": 0.8, "갓성비": 0.9,
    "최고야": 0.9, "최고에요": 0.9, "최고입니다": 0.9, "최고": 0.8,
    "완벽해": 0.9, "완벽합니다": 0.9,
    "존맛": 0.85, "존예": 0.8, "존잘": 0.8,
    "대박이에요": 0.75, "완전대박": 0.85,
    "인정": 0.65, "ㄱㅅ": 0.65, "감사합니다": 0.6, "감사해요": 0.6,
    "ㅋㅋ": 0.35, "ㅋㅋㅋ": 0.45, "ㅎㅎ": 0.35, "ㅎㅎㅎ": 0.45,
    "찐": 0.55, "찐팬": 0.8, "갓": 0.7,
    "좋아요": 0.7, "좋네요": 0.65, "좋음": 0.6, "좋았어요": 0.7,
    "훌륭해요": 0.85, "훌륭합니다": 0.85,
    "깔끔해요": 0.6, "깔끔합니다": 0.6,
    "친절해요": 0.75, "친절합니다": 0.75, "친절하다": 0.7, "친절": 0.65,
    "친절하고": 0.7, "친절했어요": 0.75,
    "빠른배송": 0.6, "배송빨라요": 0.65, "빠른 배송": 0.6,
    "품질좋아요": 0.8, "품질이 좋아요": 0.8,
    "진심 추천": 0.85, "진심으로 추천": 0.9,
    "만족이에요": 0.75, "만족해요": 0.75, "만족했어요": 0.75,
    "구매했어요": 0.3, "또살거에요": 0.7, "또구입": 0.7,
    "잘받았어요": 0.5, "잘 받았어요": 0.5,
}

# 구문형 항목 (공백 포함, 멀티워드 매칭용)
_PHRASE_LEXICON: dict[str, float] = {
    k: v for k, v in _CUSTOM_LEXICON.items() if " " in k
}
# 구문형 항목을 추가로 확장
_PHRASE_LEXICON.update({
    "환불 거부": -0.95, "환불 안": -0.85, "교환 거부": -0.9,
    "AS 거부": -0.85, "서비스 최악": -0.95, "서비스가 최악": -0.95,
    "직원이 불친절": -0.85, "응대가 최악": -0.9,
    "가격 대비": 0.3, "가성비 최고": 0.9, "가성비가 좋": 0.8,
    "강추 합니다": 0.9, "강력 추천": 0.95,
    "다시 구매": 0.75, "재구매 의사": 0.8,
    "소비자 고발": -0.85, "집단 소송": -0.9,
    "역대급 실망": -0.9, "역대급 최악": -1.0,
})

# ── 부정어 목록 ──────────────────────────────────────────────────────
_NEGATION_WORDS = frozenset({
    "안", "못", "전혀", "결코", "별로", "절대", "아니", "아닌",
    "없다", "없어", "없음", "없고", "없는", "없네", "없어요",
    "아니다", "아닙니다", "아니에요", "아니야",
    "않다", "않아", "않고", "않은", "않음", "않아요", "않습니다",
})

# "부정 명사 + 없다" 패턴 → 긍정 전환
_NEG_NOUN_ABSENT = re.compile(
    r"(불만|불편|문제|결함|하자|오류|에러|고장|불량|불평|단점|흠|이상)"
    r"[\s\S]{0,8}(없|없어|없음|없다|없고|없어요|없습니다)"
)
# "긍정 명사 + 없다" 패턴 → 부정 전환
_POS_NOUN_ABSENT = re.compile(
    r"(만족|장점|좋은점|강점|칭찬)"
    r"[\s\S]{0,8}(없|없어|없음|없다|없고)"
)

# ── 강조어 배율 ──────────────────────────────────────────────────────
_INTENSIFIERS: dict[str, float] = {
    "매우": 1.5, "너무": 1.4, "엄청": 1.5, "완전": 1.4, "진짜": 1.35,
    "정말": 1.35, "아주": 1.3, "굉장히": 1.5, "극도로": 1.8,
    "개": 1.6, "씹": 1.9, "존": 1.5, "겁나": 1.4, "되게": 1.25,
    "무지": 1.3, "지나치게": 1.4, "심하게": 1.4, "몹시": 1.5,
}

# ── 어미 제거 패턴 (긴 것부터 먼저 시도) ──────────────────────────────
_SUFFIXES = [
    # 합쇼체/합니다체
    "했습니다", "합니다", "입니다", "습니다", "ㅂ니다",
    # 해요체
    "했어요", "해요", "이에요", "해서요", "해서",
    # 과거
    "았어요", "었어요", "았습니다", "었습니다",
    "았어", "었어", "았다", "었다",
    # 현재형
    "아요", "어요",
    "이다", "아서", "어서",
    # 연결
    "하고", "이고", "이며", "하며", "하면", "하고는",
    "하여", "하여서",
    # 기타
    "는다", "는데", "군요", "네요", "인데",
    # 단순
    "해", "함", "하다", "네",
]

# ── 감정 카테고리 키워드 ──────────────────────────────────────────────
_EMOTION_KEYWORDS: dict[str, list[str]] = {
    "분노": [
        "화나", "화남", "짜증", "열받", "ㅂㄷ", "ㅂㄷㄷ", "분노", "격분",
        "불쾌", "기분나쁘", "빡쳐", "빡침", "욕설",
        "부글부글", "열통", "열받아", "씩씩", "노여움",
    ],
    "공포": [
        "무서", "두렵", "ㄷㄷ", "덜덜", "공포", "소름", "무섭",
        "오싹", "섬뜩", "겁나", "떨려", "두려움",
    ],
    "혐오": [
        "역겹", "혐오", "구역질", "역하", "더러", "메스껍",
        "불결", "극혐", "혐오스러",
    ],
    "슬픔": [
        "슬프", "슬픔", "눈물", "우울", "실망", "속상", "마음아프",
        "가슴아프", "눈물나", "ㅜㅜ", "ㅠㅠ",
        "서럽", "안타깝", "애석", "비통", "상심",
    ],
    "놀람": [
        "놀라", "헉", "충격", "경악", "어이없", "당황", "황당",
        "믿기지 않", "설마",
    ],
    "기쁨": [
        "기쁘", "행복", "즐거", "신나", "좋아", "감사", "최고",
        "만족", "뿌듯", "흐뭇", "기분좋", "ㅋㅋ", "ㅎㅎ",
    ],
}


def _load_knu_lexicon() -> dict[str, float]:
    lex: dict[str, float] = {}
    if not _DICT_PATH.exists():
        return lex
    with open(_DICT_PATH, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                word = parts[0].strip()
                try:
                    lex[word] = float(parts[1]) / 2.0
                except ValueError:
                    pass
    return lex


_KNU: dict[str, float] = _load_knu_lexicon()
_CUSTOM_SINGLE: dict[str, float] = {
    k: v for k, v in _CUSTOM_LEXICON.items() if " " not in k
}
# KNU + 단어형 커스텀 병합 (커스텀 우선)
_MERGED: dict[str, float] = {**_KNU, **_CUSTOM_SINGLE}


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _tokenize(text: str) -> list[str]:
    return re.split(r"\s+", text.strip())


def _look_up_token(token: str) -> float | None:
    """단어 사전 조회. 어미 제거 후 재시도 포함."""
    if token in _MERGED:
        return _MERGED[token]
    # 어미 순차 제거 (긴 것 우선)
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) > len(suffix):
            stem = token[:-len(suffix)]
            if stem in _MERGED:
                return _MERGED[stem]
            if stem + "다" in _MERGED:
                return _MERGED[stem + "다"]
            if stem + "하다" in _MERGED:
                return _MERGED[stem + "하다"]
    return None


def _scan_phrases(text: str) -> tuple[float, float]:
    """
    구문형(공백 포함) 항목을 텍스트에서 서브스트링 검색.
    Returns: (score_sum, weight_sum)
    """
    score_sum = 0.0
    weight_sum = 0.0
    for phrase, score in _PHRASE_LEXICON.items():
        if phrase in text:
            score_sum += score * abs(score)
            weight_sum += abs(score)
    return score_sum, weight_sum


def _scan_tokens(text: str) -> tuple[float, float]:
    """
    어절 단위 사전 매칭 (부정어·강조어 처리 포함).

    "없-" 역방향 부정: "없어요/없다" 직전 3토큰 이내 매칭 단어를 역전.
    "안/못" 순방향 부정: 바로 다음 1토큰만 반전.

    Returns: (score_sum, weight_sum)
    """
    tokens = _tokenize(text)
    score_sum = 0.0
    weight_sum = 0.0
    intensifier_mult = 1.0
    negation_window = 0
    last_score: float | None = None
    last_score_idx: int = -99

    for idx, token in enumerate(tokens):
        # 강조어 감지
        for intens, mult in _INTENSIFIERS.items():
            if token == intens or (token.startswith(intens) and len(token) <= len(intens) + 2):
                intensifier_mult = mult
                break

        # 부정어 처리
        if token in _NEGATION_WORDS:
            absent = token.startswith("없")
            if absent and last_score is not None and (idx - last_score_idx) <= 3:
                # 역방향 부정: "X 없다" → X를 약하게 반전
                prev = last_score * abs(last_score)
                score_sum -= prev
                negated = -last_score * 0.4
                score_sum += negated * abs(negated)
                last_score = negated
            negation_window = 1
            intensifier_mult = 1.0
            continue

        score = _look_up_token(token)
        if score is not None:
            adjusted = score * intensifier_mult
            if negation_window > 0:
                adjusted = -adjusted * 0.7
            score_sum += adjusted * abs(adjusted)
            weight_sum += abs(adjusted)
            last_score = adjusted
            last_score_idx = idx
            intensifier_mult = 1.0

        if negation_window > 0:
            negation_window -= 1

    return score_sum, weight_sum


# "좋지(도) 않다" 계열: 완곡한 부정 (약한 negative) — 조사가 끼어도 매칭
_MILD_NEG_PATTERNS = re.compile(
    r"(좋지|좋진|나쁘지|별로이지|괜찮지|만족스럽지)"
    r"[\s\S]{0,6}(않|안)"
)
# "나쁘지 않다" 계열: 완곡한 긍정 (약한 positive)
_MILD_POS_PATTERNS = re.compile(
    r"(나쁘지|별로이지|불만이지|싫지|불편하지)"
    r"[\s\S]{0,6}(않|안)"
)


def _reversed_negation_adj(text: str) -> float:
    """
    역방향 부정 처리: "불만 없고" → 부정 명사가 없어져서 긍정.
    + 완곡 부정 패턴 처리.
    Returns score adjustment.
    """
    adj = 0.0
    if _NEG_NOUN_ABSENT.search(text):
        adj += 0.35   # "불만 없어요" → 긍정 방향 보정
    if _POS_NOUN_ABSENT.search(text):
        adj -= 0.35
    if _MILD_NEG_PATTERNS.search(text):
        adj -= 0.25  # "좋지(도) 않아요" → 약한 부정
    if _MILD_POS_PATTERNS.search(text):
        adj += 0.20  # "나쁘지 않아요" → 약한 긍정
    return adj


def analyze_sentiment(text: str) -> dict:
    """
    텍스트 → sentiment / emotion / sentiment_score 반환.

    Returns:
        {
            "sentiment": "negative" | "positive" | "neutral",
            "emotion": "분노" | "공포" | "혐오" | "슬픔" | "놀람" | "기쁨" | "중립",
            "sentiment_score": float (-1.0 ~ 1.0)
        }
    """
    if not text or not text.strip():
        return {"sentiment": "neutral", "emotion": "중립", "sentiment_score": 0.0}

    text = _normalize(text)

    # ── 구문 스캔 ─────────────────────────────────────────────────────
    p_score, p_weight = _scan_phrases(text)

    # ── 토큰 스캔 ─────────────────────────────────────────────────────
    t_score, t_weight = _scan_tokens(text)

    # ── 역방향 부정 보정 ──────────────────────────────────────────────
    rev_adj = _reversed_negation_adj(text)

    # ── 최종 점수 계산 ────────────────────────────────────────────────
    total_score = p_score + t_score
    total_weight = p_weight + t_weight

    if total_weight == 0:
        raw_score = 0.0
    else:
        raw_score = total_score / total_weight

    # 역방향 부정 보정
    if rev_adj != 0.0:
        boost = rev_adj * 0.4
        raw_score = raw_score + boost

    final_score = max(-1.0, min(1.0, raw_score))

    # ── 감정 카테고리 ─────────────────────────────────────────────────
    detected_emotion = "중립"
    for emotion, keywords in _EMOTION_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                detected_emotion = emotion
                break
        if detected_emotion != "중립":
            break

    if detected_emotion == "중립":
        if final_score <= -0.7:
            detected_emotion = "분노"
        elif final_score <= -0.3:
            detected_emotion = "슬픔"
        elif final_score >= 0.6:
            detected_emotion = "기쁨"

    # ── 감성 라벨 ─────────────────────────────────────────────────────
    if final_score <= -0.10:
        sentiment = "negative"
    elif final_score >= 0.10:
        sentiment = "positive"
    else:
        sentiment = "neutral"

    return {
        "sentiment": sentiment,
        "emotion": detected_emotion,
        "sentiment_score": round(final_score, 4),
    }
