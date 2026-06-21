"""SAYbrand 발표용 PPT 생성 스크립트"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

# ── 색상 팔레트 ──────────────────────────────────────────────
NAVY   = RGBColor(0x0c, 0x14, 0x28)
NAVY2  = RGBColor(0x1d, 0x2a, 0x45)
BLUE   = RGBColor(0x1a, 0x6e, 0xf8)
LBLUE  = RGBColor(0xe8, 0xf0, 0xfb)
RED    = RGBColor(0xdc, 0x26, 0x26)
AMBER  = RGBColor(0xea, 0x58, 0x0c)
YELLOW = RGBColor(0xd9, 0x77, 0x06)
GREEN  = RGBColor(0x16, 0xa3, 0x4a)
WHITE  = RGBColor(0xff, 0xff, 0xff)
GRAY   = RGBColor(0x88, 0x88, 0x88)
LGRAY  = RGBColor(0xf1, 0xf5, 0xf9)
MGRAY  = RGBColor(0xcc, 0xcc, 0xcc)
DGRAY  = RGBColor(0x44, 0x44, 0x44)

TODAY = date.today().isoformat()

prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


# ── 헬퍼 ─────────────────────────────────────────────────────
def slide():
    return prs.slides.add_slide(BLANK)


def rect(sl, l, t, w, h, fill, alpha=None):
    shp = sl.shapes.add_shape(1, Inches(l), Inches(t), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.fill.background()
    return shp


def txt(sl, text, l, t, w, h, size=11, bold=False, color=None,
        align=PP_ALIGN.LEFT, italic=False, wrap=True):
    tb = sl.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = str(text or "")
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = color


def header(sl, title, subtitle=""):
    rect(sl, 0, 0, 13.33, 0.78, NAVY)
    rect(sl, 0, 0, 13.33, 0.06, BLUE)
    txt(sl, title, 0.45, 0.1, 11, 0.58, size=20, bold=True, color=WHITE)
    if subtitle:
        txt(sl, subtitle, 0.45, 0.56, 10, 0.3, size=10, color=RGBColor(0xAA, 0xBB, 0xDD))


def footer(sl):
    rect(sl, 0, 7.3, 13.33, 0.2, NAVY)
    txt(sl, f"SAYbrand  |  AI 기반 브랜드 보호 SaaS  |  {TODAY}",
        0.3, 7.32, 12.7, 0.18, size=7.5, color=RGBColor(0xAA, 0xBB, 0xDD))


def badge(sl, text, l, t, fill, text_color=WHITE, size=9.5):
    rect(sl, l, t, len(text) * 0.085 + 0.25, 0.3, fill)
    txt(sl, text, l + 0.07, t + 0.03, len(text) * 0.085 + 0.18, 0.26,
        size=size, bold=True, color=text_color)


def kpi_box(sl, label, value, x, y, w=2.8, h=1.55,
            bg=LGRAY, val_color=NAVY):
    rect(sl, x, y, w, h, bg)
    txt(sl, label, x + 0.15, y + 0.13, w - 0.3, 0.45, size=9.5, color=GRAY)
    txt(sl, value, x + 0.15, y + 0.55, w - 0.3, 0.8, size=22, bold=True, color=val_color)


def section_divider(title, subtitle=""):
    """섹션 구분 슬라이드 (NAVY 풀스크린)"""
    sl = slide()
    rect(sl, 0, 0, 13.33, 7.5, NAVY)
    rect(sl, 0, 0, 0.12, 7.5, BLUE)
    rect(sl, 0.12, 3.1, 8, 0.06, BLUE)
    txt(sl, title, 0.55, 2.3, 11, 1.1, size=36, bold=True, color=WHITE)
    if subtitle:
        txt(sl, subtitle, 0.55, 3.35, 10, 0.6, size=15,
            color=RGBColor(0xAA, 0xBB, 0xDD))
    txt(sl, "SAYbrand", 0.55, 6.9, 6, 0.4, size=9, color=RGBColor(0x55, 0x66, 0x88))
    return sl


def bullet_list(sl, items, x, y, w, line_h=0.48, size=11,
                color=DGRAY, indent="• "):
    for i, item in enumerate(items):
        txt(sl, indent + item, x, y + i * line_h, w, line_h + 0.05,
            size=size, color=color, wrap=True)


# ════════════════════════════════════════════════════════════════
# Slide 1 — Cover
# ════════════════════════════════════════════════════════════════
sl1 = slide()
rect(sl1, 0, 0, 13.33, 7.5, NAVY)
rect(sl1, 0, 0, 13.33, 0.06, BLUE)
rect(sl1, 0, 7.44, 13.33, 0.06, BLUE)

txt(sl1, "SAYbrand", 0.8, 0.55, 11, 1.4, size=58, bold=True, color=WHITE)
txt(sl1, "AI 기반 브랜드 위협 모니터링 SaaS",
    0.8, 2.1, 11, 0.75, size=22, color=RGBColor(0xAA, 0xBB, 0xDD))

rect(sl1, 0.8, 2.95, 11.5, 0.05, BLUE)

txt(sl1, "공개 SNS 데이터를 3계층 AI 파이프라인으로 실시간 분석하여",
    0.8, 3.15, 11, 0.5, size=14, color=WHITE)
txt(sl1, "브랜드 사칭 · 가짜뉴스 · 조직적 봇 공격을 자동 탐지합니다.",
    0.8, 3.62, 11, 0.5, size=14, color=WHITE)

for i, (lbl, val) in enumerate([
    ("핵심 기술", "3계층 AI 파이프라인"),
    ("수집 플랫폼", "Naver · YouTube · X"),
    ("카드뉴스", "자동 쇼츠 영상 생성"),
    ("보고서", "PDF / PPT 자동 생성"),
]):
    x = 0.8 + i * 3.13
    rect(sl1, x, 4.6, 2.95, 1.75, NAVY2)
    txt(sl1, lbl, x + 0.15, 4.72, 2.65, 0.38,
        size=9, color=RGBColor(0xAA, 0xBB, 0xDD))
    txt(sl1, val, x + 0.15, 5.08, 2.65, 0.95, size=13, bold=True, color=WHITE)

txt(sl1, TODAY, 0.8, 6.85, 11, 0.4, size=10,
    color=RGBColor(0x55, 0x66, 0x88), align=PP_ALIGN.RIGHT)


# ════════════════════════════════════════════════════════════════
# Slide 2 — 목차
# ════════════════════════════════════════════════════════════════
sl2 = slide()
header(sl2, "목차")
footer(sl2)

toc = [
    ("01", "문제 정의",       "브랜드가 직면한 위협"),
    ("02", "솔루션 개요",     "SAYbrand가 제공하는 것"),
    ("03", "3계층 AI 파이프라인", "L1 → L2 → L3 비용 최소화"),
    ("04", "리스크 스코어링",  "위협 점수 산출 공식"),
    ("05", "데이터 수집",     "5개 플랫폼 실시간 수집"),
    ("06", "카드뉴스 파이프라인", "위협 → 유튜브 쇼츠 자동 생성"),
    ("07", "보고서 시스템",   "PDF / PPT 자동 생성"),
    ("08", "조직 관리 & 배포", "RBAC · Vercel + Railway"),
    ("09", "차별화 & 가격",   "경쟁 우위 및 구독 티어"),
    ("10", "로드맵 & KPI",    "성공 지표와 일정"),
]

for i, (num, title, sub) in enumerate(toc):
    col = i % 2
    row = i // 2
    x = 0.5 + col * 6.5
    y = 0.92 + row * 1.22
    rect(sl2, x, y, 6.15, 1.08, LGRAY)
    rect(sl2, x, y, 0.55, 1.08, BLUE)
    txt(sl2, num, x + 0.08, y + 0.28, 0.45, 0.5, size=13, bold=True, color=WHITE)
    txt(sl2, title, x + 0.7, y + 0.08, 5.3, 0.45, size=13, bold=True, color=NAVY)
    txt(sl2, sub,   x + 0.7, y + 0.55, 5.3, 0.45, size=9.5, color=GRAY)


# ════════════════════════════════════════════════════════════════
# Section — 문제 정의
# ════════════════════════════════════════════════════════════════
section_divider("01  문제 정의", "브랜드가 직면한 디지털 위협")


# ════════════════════════════════════════════════════════════════
# Slide 3 — 문제 정의
# ════════════════════════════════════════════════════════════════
sl3 = slide()
header(sl3, "브랜드가 직면한 위협", "SNS 공간에서 하루에도 수백 건의 위협이 발생합니다")
footer(sl3)

threats_data = [
    (RED,    "브랜드 사칭",      "공식 계정을 흉내 낸 가짜 계정이\n소비자를 기만하고 신뢰를 훼손"),
    (AMBER,  "가짜뉴스 / 루머", "사실 무근의 악성 루머가 SNS를 타고\n수십만 명에게 순식간에 확산"),
    (YELLOW, "조직적 봇 공격",   "경쟁사 또는 악의적 세력이 봇 계정으로\n집단적인 부정 댓글·리뷰 공격"),
    (BLUE,   "임직원 리스크",    "임원·직원의 개인 SNS 발언이\n기업 이미지에 치명타를 입힘"),
]

for i, (col, title, desc) in enumerate(threats_data):
    x = 0.45 + i * 3.13
    rect(sl3, x, 0.95, 2.95, 5.85, LGRAY)
    rect(sl3, x, 0.95, 2.95, 0.08, col)
    txt(sl3, title, x + 0.15, 1.12, 2.65, 0.55, size=13, bold=True, color=NAVY)
    txt(sl3, desc,  x + 0.15, 1.75, 2.65, 1.8,  size=10.5, color=DGRAY, wrap=True)

rect(sl3, 0.45, 6.95, 12.43, 0.18, NAVY2)
txt(sl3, "문제: 사람이 24시간 모니터링하기엔 데이터가 너무 많고 빠릅니다.",
    0.6, 6.97, 12, 0.18, size=9, bold=True, color=WHITE)


# ════════════════════════════════════════════════════════════════
# Section — 솔루션
# ════════════════════════════════════════════════════════════════
section_divider("02  솔루션 개요", "SAYbrand가 제공하는 것")


# ════════════════════════════════════════════════════════════════
# Slide 4 — 솔루션
# ════════════════════════════════════════════════════════════════
sl4 = slide()
header(sl4, "SAYbrand 솔루션", "AI가 24시간 자동으로 브랜드를 지킵니다")
footer(sl4)

txt(sl4, "SAYbrand는 공개 SNS 데이터를 AI로 실시간 분석하여",
    0.5, 0.92, 12, 0.5, size=14, bold=True, color=NAVY)
txt(sl4, "브랜드를 위협하는 모든 요소를 사전 탐지·대응하는 B2B 브랜드 보호 SaaS입니다.",
    0.5, 1.38, 12, 0.5, size=14, color=NAVY)

values = [
    (BLUE,  "24시간 자동 감시",
     "사칭·가짜뉴스·루머·임직원 리스크를\n사람 없이 탐지"),
    (GREEN, "AI 위협 판단",
     "즉각 알림 vs 정기 리포트를\nAI가 자동 분기"),
    (AMBER, "조직적 공격 구분",
     "봇 공격과 실제 소비자 불만을 분리해\n불필요한 법적 대응 방지"),
    (RED,   "즉시 대응 문구 생성",
     "SNS 대응·보도자료·내부 조치\n3가지 문구 AI가 자동 생성"),
]

for i, (col, title, desc) in enumerate(values):
    x = 0.45 + i * 3.13
    rect(sl4, x, 2.05, 2.95, 4.8, LGRAY)
    rect(sl4, x, 2.05, 2.95, 0.45, col)
    txt(sl4, title, x + 0.12, 2.1, 2.71, 0.38, size=12, bold=True, color=WHITE)
    txt(sl4, desc,  x + 0.12, 2.62, 2.71, 2.0, size=10.5, color=DGRAY, wrap=True)

# 타겟 고객
rect(sl4, 0.45, 7.0, 12.43, 0.2, NAVY2)
txt(sl4, "타겟: B2C 브랜드(뷰티·패션·식품)  |  브랜드 모니터링이 없는 중견기업  |  팔로워 1만+ 인플루언서",
    0.6, 7.02, 12, 0.18, size=8.5, bold=True, color=WHITE)


# ════════════════════════════════════════════════════════════════
# Section — AI 파이프라인
# ════════════════════════════════════════════════════════════════
section_divider("03  3계층 AI 파이프라인", "비용을 최소화하면서 정확도를 극대화합니다")


# ════════════════════════════════════════════════════════════════
# Slide 5 — AI 파이프라인
# ════════════════════════════════════════════════════════════════
sl5 = slide()
header(sl5, "3계층 AI 파이프라인", "L1 → L2 → L3 순서로 고위협만 상위 계층 호출")
footer(sl5)

layers = [
    (GREEN, "L1", "규칙 기반 필터", "$0 비용",
     ["900개+ 키워드 데이터베이스 (18개 카테고리)",
      "CRITICAL_BYPASS — 법적 위협 즉시 통과",
      "NEGATIVE_FILTERS 20개+ 오탐 방지",
      "score < 0.05 → 즉시 탈락 (AI 비용 없음)"]),
    (BLUE,  "L2", "AI 감성·의도 분석", "저비용 (배치 10건/호출)",
     ["HyperCLOVA X → Gemini 2.5 Flash Lite → KNU 폴백",
      "12개 마케팅 위기 카테고리 분류",
      "감성 + 감정(분노/공포/혐오 등) 분석",
      "봇 확률(0.0–1.0) + 조직적 공격 판별"]),
    (AMBER, "L3", "심층 대응 분석", "고비용 (고위협만)",
     ["risk_score ≥ 85 케이스만 호출",
      "Gemini 2.5 Flash Lite → Claude Haiku 4.5 폴백",
      "brand_damage_type 분류 (매출·채용·파트너십 등)",
      "communication_urgency + 대응 문구 3가지 생성"]),
]

for i, (col, lnum, ltitle, cost, bullets) in enumerate(layers):
    x = 0.45 + i * 4.25
    rect(sl5, x, 0.9, 4.0, 6.0, LGRAY)
    rect(sl5, x, 0.9, 4.0, 0.55, col)
    txt(sl5, lnum,    x + 0.15, 0.93, 0.8,  0.42, size=18, bold=True, color=WHITE)
    txt(sl5, ltitle,  x + 0.85, 0.93, 3.0,  0.42, size=13, bold=True, color=WHITE)
    rect(sl5, x, 1.45, 4.0, 0.32, RGBColor(0xee, 0xee, 0xee))
    txt(sl5, cost,    x + 0.12, 1.48, 3.7,  0.28, size=9.5, bold=True, color=DGRAY)
    bullet_list(sl5, bullets, x + 0.15, 1.88, 3.7,
                line_h=0.97, size=10, color=DGRAY)

# 화살표 대체 텍스트
txt(sl5, "→", 4.3, 3.6, 0.3, 0.4, size=20, bold=True, color=BLUE)
txt(sl5, "→", 8.55, 3.6, 0.3, 0.4, size=20, bold=True, color=AMBER)


# ════════════════════════════════════════════════════════════════
# Slide 6 — 리스크 스코어링
# ════════════════════════════════════════════════════════════════
sl6 = slide()
header(sl6, "04  리스크 스코어링 엔진", "위협 점수 0–100 자동 산출")
footer(sl6)

# 공식
rect(sl6, 0.45, 0.9, 12.43, 1.3, NAVY2)
txt(sl6, "risk_score = SEVERITY × MODULE × PLATFORM × confidence × 100  ×  industry_multiplier  ×  (recency + velocity)",
    0.65, 1.0, 12.1, 0.55, size=11, bold=True, color=WHITE, wrap=True)
txt(sl6, "조직적 공격 +30%  |  결과값 0–100 클램프",
    0.65, 1.5, 12, 0.38, size=9.5, color=RGBColor(0xAA, 0xBB, 0xDD))

# 가중치 테이블 3개
tables = [
    ("심각도 가중치", [
        ("Critical", "1.0", RED),
        ("High",     "0.7", AMBER),
        ("Medium",   "0.4", YELLOW),
        ("Low",      "0.15", GREEN),
    ]),
    ("모듈 가중치", [
        ("A — 브랜드 사칭",   "1.0", RED),
        ("B — 루머·가짜뉴스", "0.85", AMBER),
        ("C — 임직원 리스크", "0.7",  YELLOW),
    ]),
    ("플랫폼 가중치", [
        ("Instagram", "1.0", NAVY),
        ("YouTube",   "0.9", NAVY),
        ("TikTok",    "0.85", NAVY),
        ("X (Twitter)","0.8", NAVY),
        ("Naver",     "0.7", NAVY),
    ]),
]

for ti, (title, rows) in enumerate(tables):
    x = 0.45 + ti * 4.3
    rect(sl6, x, 2.38, 4.0, 0.42, NAVY)
    txt(sl6, title, x + 0.1, 2.42, 3.8, 0.36, size=11, bold=True, color=WHITE)
    for ri, row in enumerate(rows):
        bg = LGRAY if ri % 2 == 0 else WHITE
        rect(sl6, x, 2.8 + ri * 0.42, 4.0, 0.42, bg)
        label, val, col = row
        txt(sl6, label, x + 0.1,  2.84 + ri * 0.42, 2.8, 0.36, size=9.5, color=DGRAY)
        txt(sl6, val,   x + 3.1,  2.84 + ri * 0.42, 0.8, 0.36, size=10,  bold=True, color=col, align=PP_ALIGN.RIGHT)

# 임계값
rect(sl6, 0.45, 6.85, 12.43, 0.35, LGRAY)
txt(sl6, "80–100: CRITICAL (즉각 Slack 알림)   60–79: HIGH (당일 대응)   35–59: MEDIUM (모니터링)   0–34: LOW (정기 리포트)",
    0.6, 6.88, 12.1, 0.3, size=9, color=NAVY, align=PP_ALIGN.CENTER)


# ════════════════════════════════════════════════════════════════
# Section — 데이터 수집
# ════════════════════════════════════════════════════════════════
section_divider("05  데이터 수집기", "5개 플랫폼 실시간 자동 수집")


# ════════════════════════════════════════════════════════════════
# Slide 7 — 수집기
# ════════════════════════════════════════════════════════════════
sl7 = slide()
header(sl7, "데이터 수집기", "Celery Beat 30분 주기 자동 수집 + robots.txt 준수")
footer(sl7)

collectors = [
    (GREEN,  "✅", "Naver",      "블로그·카페·뉴스",   "NAVER_CLIENT_ID/SECRET",  "검증 완료"),
    (GREEN,  "✅", "YouTube",    "영상 댓글",          "YOUTUBE_API_KEY",          "API 키 필요"),
    (GREEN,  "✅", "X (Twitter)","트윗·대화",          "X_BEARER_TOKEN",           "API 키 필요"),
    (YELLOW, "🟡", "한국 커뮤니티","에펨·더쿠·클리앙",  "크롤링",                  "Mock 처리"),
    (GRAY,   "❌", "Instagram",  "게시글·댓글",        "Meta API 제한",            "v1.1 목표"),
    (GRAY,   "❌", "TikTok",     "영상·댓글",          "API 제한",                 "v1.1 목표"),
]

rect(sl7, 0.4, 0.9, 12.53, 0.42, NAVY)
for hdr, xp in [("상태", 0.55), ("플랫폼", 1.05), ("수집 대상", 2.8),
                 ("API/방법", 5.0), ("비고", 9.3)]:
    txt(sl7, hdr, xp, 0.95, 2.0, 0.35, size=10, bold=True, color=WHITE)

for ri, (col, status, plat, target, api, note) in enumerate(collectors):
    bg = LGRAY if ri % 2 == 0 else WHITE
    y = 1.32 + ri * 0.82
    rect(sl7, 0.4, y, 12.53, 0.78, bg)
    rect(sl7, 0.4, y, 0.12, 0.78, col)
    txt(sl7, status, 0.55,  y + 0.2,  0.55, 0.4, size=14)
    txt(sl7, plat,   1.05,  y + 0.2,  1.75, 0.4, size=11, bold=True, color=NAVY)
    txt(sl7, target, 2.8,   y + 0.2,  2.2,  0.4, size=10, color=DGRAY)
    txt(sl7, api,    5.0,   y + 0.2,  4.3,  0.4, size=9.5, color=DGRAY)
    txt(sl7, note,   9.3,   y + 0.2,  3.4,  0.4, size=10, bold=(col == GREEN), color=col)

rect(sl7, 0.4, 6.28, 12.53, 0.6, LGRAY)
txt(sl7, "컴플라이언스:  robots.txt 자동 체크  |  PII(개인정보) 정규식 마스킹  |  요청 간 최소 2초 지연  |  언론사 도메인 자동 분류",
    0.6, 6.35, 12.1, 0.45, size=9.5, color=NAVY, wrap=True)


# ════════════════════════════════════════════════════════════════
# Section — 카드뉴스 파이프라인
# ════════════════════════════════════════════════════════════════
section_divider("06  카드뉴스 파이프라인", "위협 데이터 → 유튜브 쇼츠 영상 자동 생성")


# ════════════════════════════════════════════════════════════════
# Slide 8 — 카드뉴스 파이프라인
# ════════════════════════════════════════════════════════════════
sl8 = slide()
header(sl8, "카드뉴스 자동 생성 파이프라인", "card-news-pipeline/ — 독립 모듈")
footer(sl8)

steps = [
    (NAVY,   "DB 로드",      "최근 14일\ncritical/high/medium\n최신순 LIMIT 100"),
    (BLUE,   "소재 선택",    "오늘 우선 → 1–3일 전\n→ 전체 최고점\n중복(used_ids) 제거"),
    (GREEN,  "LLM 스크립팅", "Claude Haiku 4.5\nheadline ≤ 20자\nbody ≤ 150자 + 태그 5개"),
    (AMBER,  "슬라이드 렌더", "Playwright Chromium\n1080×1920 (세로형)\nPixazo 히어로 이미지"),
    (RED,    "영상 조립",    "FFmpeg MP4\nassets/bgm/*.mp3\n믹싱 삽입"),
    (DGRAY,  "검수·업로드",  "Discord Webhook\n검수 후 YouTube\n비공개 Shorts 업로드"),
]

for i, (col, title, desc) in enumerate(steps):
    x = 0.4 + i * 2.1
    rect(sl8, x, 0.9, 1.95, 5.8, LGRAY)
    rect(sl8, x, 0.9, 1.95, 0.45, col)
    txt(sl8, str(i + 1), x + 0.1,  0.93, 0.4, 0.38, size=14, bold=True, color=WHITE)
    txt(sl8, title,      x + 0.44, 0.95, 1.4, 0.38, size=11, bold=True, color=WHITE)
    txt(sl8, desc,       x + 0.1,  1.45, 1.75, 4.8, size=9.5, color=DGRAY, wrap=True)
    if i < 5:
        txt(sl8, "→", x + 1.97, 3.5, 0.2, 0.4, size=14, bold=True, color=BLUE)

rect(sl8, 0.4, 6.82, 12.53, 0.35, NAVY2)
txt(sl8, "테스트: 93 passed (2026-06-21)  |  폴백: API 키 없을 때 규칙 기반 템플릿 자동 대체",
    0.6, 6.86, 12, 0.28, size=9, color=WHITE)


# ════════════════════════════════════════════════════════════════
# Section — 보고서
# ════════════════════════════════════════════════════════════════
section_divider("07  보고서 시스템", "PDF · PPT 자동 생성")


# ════════════════════════════════════════════════════════════════
# Slide 9 — 보고서 시스템
# ════════════════════════════════════════════════════════════════
sl9 = slide()
header(sl9, "보고서 시스템", "일간·주간·월간 보고서 자동 생성 — GET /api/reports/{period}/{format}")
footer(sl9)

# PDF 컬럼
rect(sl9, 0.4,  0.9, 5.95, 0.42, RED)
txt(sl9, "PDF 보고서 (ReportLab)  —  8섹션 A4",
    0.55, 0.94, 5.65, 0.35, size=11, bold=True, color=WHITE)

pdf_sections = [
    "표지 — 브랜드명·기간·KPI 6개",
    "1. 핵심 요약 — Executive Summary",
    "2. 위협 현황 — 심각도·플랫폼·Top5",
    "3. 감성·감정 — 분포 + 부정 사례",
    "4. 조직공격·봇 — 플랫폼별 감성",
    "5. 미해결 위협 Top 10 (AI 권고)",
    "6. 조치 완료 내역",
    "7. 모니터링 현황 + 8. 대응 권고",
]
for ri, sec in enumerate(pdf_sections):
    bg = LGRAY if ri % 2 == 0 else WHITE
    rect(sl9, 0.4, 1.32 + ri * 0.63, 5.95, 0.62, bg)
    txt(sl9, sec, 0.55, 1.37 + ri * 0.63, 5.7, 0.5, size=9.5, color=DGRAY)

# PPT 컬럼
rect(sl9, 6.98, 0.9, 5.95, 0.42, BLUE)
txt(sl9, "PPT 보고서 (python-pptx)  —  6슬라이드 16:9",
    7.12, 0.94, 5.7, 0.35, size=11, bold=True, color=WHITE)

ppt_slides = [
    "Slide 1 — Cover (NAVY 배경, KPI 4개 박스)",
    "Slide 2 — 핵심 요약 (KPI 6개 그리드)",
    "Slide 3 — 위협 현황 (인라인 바 차트)",
    "Slide 4 — 감성 분석 (분포 + 감정)",
    "Slide 5 — 미해결 Top 5 (테이블)",
    "Slide 6 — 권고사항 (색상 헤더 카드)",
]
for ri, sec in enumerate(ppt_slides):
    bg = LGRAY if ri % 2 == 0 else WHITE
    rect(sl9, 6.98, 1.32 + ri * 0.63, 5.95, 0.62, bg)
    txt(sl9, sec, 7.12, 1.37 + ri * 0.63, 5.7, 0.5, size=9.5, color=DGRAY)

rect(sl9, 0.4, 6.42, 12.53, 0.75, LGRAY)
txt(sl9, "공통 기술 특징",
    0.55, 6.47, 12, 0.3, size=10, bold=True, color=NAVY)
txt(sl9, "한국어 폰트: NanumGothic TTF 번들  |  wordWrap='CJK' 한국어 오버플로 방지  |  헤더·푸터 자동 삽입",
    0.55, 6.75, 12, 0.35, size=9, color=DGRAY)


# ════════════════════════════════════════════════════════════════
# Section — 조직 관리 & 배포
# ════════════════════════════════════════════════════════════════
section_divider("08  조직 관리 & 배포", "RBAC · Vercel + Railway 듀얼 배포")


# ════════════════════════════════════════════════════════════════
# Slide 10 — 조직 관리
# ════════════════════════════════════════════════════════════════
sl10 = slide()
header(sl10, "조직 관리 시스템", "다중 사용자 RBAC + 초대코드 + 가입 승인 플로우")
footer(sl10)

# 역할
rect(sl10, 0.4, 0.9, 5.5, 0.42, NAVY)
txt(sl10, "멤버 역할 (RBAC)", 0.55, 0.94, 5.2, 0.35, size=11, bold=True, color=WHITE)

roles = [
    ("owner",  "전체 관리 (삭제 포함)",          RED),
    ("admin",  "멤버 관리 · 설정 변경",          AMBER),
    ("member", "스캔 · 위협 처리",               BLUE),
    ("viewer", "읽기 전용",                      GRAY),
]
for ri, (role, perm, col) in enumerate(roles):
    bg = LGRAY if ri % 2 == 0 else WHITE
    rect(sl10, 0.4, 1.32 + ri * 0.62, 5.5, 0.62, bg)
    rect(sl10, 0.4, 1.32 + ri * 0.62, 0.08, 0.62, col)
    txt(sl10, role, 0.58, 1.37 + ri * 0.62, 1.4, 0.5, size=10, bold=True, color=col)
    txt(sl10, perm, 1.9,  1.37 + ri * 0.62, 3.8, 0.5, size=9.5, color=DGRAY)

# 구독 티어 제한
rect(sl10, 0.4, 3.82, 5.5, 0.42, NAVY)
txt(sl10, "구독 티어별 조직 수 제한", 0.55, 3.86, 5.2, 0.35, size=11, bold=True, color=WHITE)
tiers = [("Free", "1개", GRAY), ("Starter", "3개", BLUE), ("Pro", "5개", GREEN), ("Enterprise", "무제한", AMBER)]
for ri, (tier, limit, col) in enumerate(tiers):
    bg = LGRAY if ri % 2 == 0 else WHITE
    rect(sl10, 0.4, 4.24 + ri * 0.55, 5.5, 0.55, bg)
    txt(sl10, tier,  0.55, 4.29 + ri * 0.55, 2.8, 0.45, size=10, bold=True, color=col)
    txt(sl10, limit, 4.5,  4.29 + ri * 0.55, 1.2, 0.45, size=10, color=DGRAY, align=PP_ALIGN.RIGHT)

# 가입 플로우
rect(sl10, 6.5, 0.9, 6.4, 0.42, NAVY)
txt(sl10, "가입 플로우", 6.65, 0.94, 6.1, 0.35, size=11, bold=True, color=WHITE)

flow1 = [
    "방법 1 — 초대 코드",
    "관리자 → 코드 생성 (역할·만료일·횟수 지정)",
    "URL 공유 → 코드 입력 → 즉시 active",
]
flow2 = [
    "방법 2 — 승인 요청",
    "사용자 → 참여 신청 (pending)",
    "관리자 승인(active) / 거절(DB 삭제)",
]
for fi, (items, y_start) in enumerate([(flow1, 1.42), (flow2, 3.25)]):
    col = GREEN if fi == 0 else BLUE
    rect(sl10, 6.5, y_start, 6.4, 0.38, col)
    txt(sl10, items[0], 6.65, y_start + 0.06, 6.1, 0.3, size=10, bold=True, color=WHITE)
    for ii, item in enumerate(items[1:]):
        rect(sl10, 6.5, y_start + 0.38 + ii * 0.52, 6.4, 0.5, LGRAY if ii % 2 == 0 else WHITE)
        txt(sl10, "  " + item, 6.6, y_start + 0.42 + ii * 0.52, 6.2, 0.44, size=9.5, color=DGRAY)


# ════════════════════════════════════════════════════════════════
# Slide 11 — 시스템 아키텍처 & 배포
# ════════════════════════════════════════════════════════════════
sl11 = slide()
header(sl11, "시스템 아키텍처 & 배포 구성", "Vercel (API + 프론트엔드) + Railway (Celery 워커)")
footer(sl11)

# 아키텍처 플로우
arch_steps = [
    (BLUE,  "SNS 플랫폼", "YouTube · Naver · X"),
    (NAVY,  "수집기",     "Celery Beat 30분"),
    (GREEN, "L1 필터",    "규칙 기반 $0"),
    (BLUE,  "L2 분석",    "Gemini 2.5 Flash"),
    (AMBER, "L3 심층",    "Claude Haiku 4.5"),
    (RED,   "DB 저장",    "PostgreSQL"),
]

for i, (col, title, sub) in enumerate(arch_steps):
    x = 0.45 + i * 2.14
    rect(sl11, x, 0.9, 1.9, 1.2, col)
    txt(sl11, title, x + 0.1, 0.98, 1.7, 0.48, size=11, bold=True, color=WHITE)
    txt(sl11, sub,   x + 0.1, 1.43, 1.7, 0.58, size=9,  color=WHITE)
    if i < 5:
        txt(sl11, "→", x + 1.92, 1.35, 0.25, 0.4, size=14, bold=True, color=NAVY)

# 결과 분기
rect(sl11, 0.45, 2.3, 12.43, 0.42, LGRAY)
txt(sl11, "대시보드 API  →  프론트엔드 실시간 표시   |   Slack/이메일 알림   |   PDF/PPT 보고서",
    0.65, 2.36, 12, 0.32, size=10, color=NAVY, align=PP_ALIGN.CENTER)

# 배포 구성
rect(sl11, 0.45, 2.88, 5.95, 0.42, BLUE)
txt(sl11, "Vercel — API + 프론트엔드", 0.6, 2.92, 5.65, 0.35, size=11, bold=True, color=WHITE)
vercel_items = [
    "진입점: app.py (main.py는 Vercel 미반영)",
    "로깅: print()만 Vercel 로그에 표시",
    "lifespan 미작동 → DB 마이그레이션은 Railway에서 직접 SQL",
    "datetime: naive UTC 사용 (timezone.utc → asyncpg 오류)",
]
for ri, item in enumerate(vercel_items):
    bg = LGRAY if ri % 2 == 0 else WHITE
    rect(sl11, 0.45, 3.3 + ri * 0.6, 5.95, 0.6, bg)
    txt(sl11, item, 0.6, 3.35 + ri * 0.6, 5.7, 0.5, size=9.5, color=DGRAY, wrap=True)

rect(sl11, 7.0, 2.88, 5.88, 0.42, RGBColor(0xdc, 0x26, 0x26))
txt(sl11, "Railway — Celery 워커", 7.15, 2.92, 5.58, 0.35, size=11, bold=True, color=WHITE)
railway_items = [
    "startCommand: celery -A backend.workers.celery_app worker -B -c 2",
    "collect_all_profiles: 30분 주기",
    "send_daily_reports: 매일 09:00 KST",
    "purge_expired_data: 매일 새벽 02:00",
]
for ri, item in enumerate(railway_items):
    bg = LGRAY if ri % 2 == 0 else WHITE
    rect(sl11, 7.0, 3.3 + ri * 0.6, 5.88, 0.6, bg)
    txt(sl11, item, 7.15, 3.35 + ri * 0.6, 5.65, 0.5, size=9.5, color=DGRAY, wrap=True)


# ════════════════════════════════════════════════════════════════
# Slide 12 — 기술 스택
# ════════════════════════════════════════════════════════════════
sl12 = slide()
header(sl12, "기술 스택", "Python 3.11+ 풀스택 — 빌드 도구 없는 경량 프론트엔드")
footer(sl12)

stack_groups = [
    ("백엔드", NAVY, [
        ("FastAPI 0.115",       "비동기 REST API"),
        ("SQLAlchemy 2.0 async","ORM + 마이그레이션"),
        ("Celery 5.4 + Redis",  "비동기 워커 + 스케줄"),
        ("Authlib",             "Google OAuth 2.0"),
    ]),
    ("AI / 분석", BLUE, [
        ("Gemini 2.5 Flash Lite","L2 텍스트 분석 (google-genai ≥ 1.0)"),
        ("Claude Haiku 4.5",    "L3 심층 분석 + 카드뉴스 스크립팅"),
        ("KNU 감성 사전",       "14,854개 단어 오프라인 폴백"),
        ("imagehash (pHash)",   "이미지 사칭 탐지"),
    ]),
    ("프론트엔드", GREEN, [
        ("Tailwind CSS CDN",    "빌드 없는 유틸리티 CSS"),
        ("Vanilla JS",          "fetch 래퍼 + 공통 API 모듈"),
        ("Syne / Noto Sans KR", "영문 Display / 한글 본문 폰트"),
        ("PWA (manifest + SW)", "모바일 앱처럼 설치 가능"),
    ]),
    ("인프라 / 외부", AMBER, [
        ("Vercel",              "서버리스 API + 정적 프론트엔드"),
        ("Railway PostgreSQL",  "운영 DB + Celery 워커 호스팅"),
        ("Polar",               "구독 결제 + Svix 웹훅"),
        ("Slack Webhook",       "위협 등급별 즉각 알림"),
    ]),
]

for gi, (group, col, items) in enumerate(stack_groups):
    x = 0.4 + gi * 3.23
    rect(sl12, x, 0.9, 3.08, 0.42, col)
    txt(sl12, group, x + 0.1, 0.94, 2.88, 0.35, size=11, bold=True, color=WHITE)
    for ri, (tech, desc) in enumerate(items):
        bg = LGRAY if ri % 2 == 0 else WHITE
        rect(sl12, x, 1.32 + ri * 1.35, 3.08, 1.32, bg)
        txt(sl12, tech, x + 0.1, 1.38 + ri * 1.35, 2.88, 0.45, size=10.5, bold=True, color=NAVY)
        txt(sl12, desc, x + 0.1, 1.82 + ri * 1.35, 2.88, 0.65, size=9,   color=GRAY, wrap=True)


# ════════════════════════════════════════════════════════════════
# Section — 차별화 & 가격
# ════════════════════════════════════════════════════════════════
section_divider("09  차별화 & 가격 모델", "왜 SAYbrand인가")


# ════════════════════════════════════════════════════════════════
# Slide 13 — 차별화 포인트
# ════════════════════════════════════════════════════════════════
sl13 = slide()
header(sl13, "차별화 포인트", "경쟁 솔루션 대비 SAYbrand의 강점")
footer(sl13)

diffs = [
    (BLUE,  "3계층 AI 파이프라인",
     "L1($0) → L2(저비용) → L3(고위협만)\nAI 비용을 최소화하면서 정확도를 극대화"),
    (RED,   "조직적 공격 자동 탐지",
     "6개 지표 가중합으로 봇·조직 공격 vs\n실제 소비자 불만을 정량적으로 구분"),
    (GREEN, "한국 시장 특화",
     "KNU 감성 사전 · 커뮤니티어 · 초성 반어법\n한국어 뉘앙스 전문 처리"),
    (AMBER, "마케팅 위기 12개 카테고리",
     "불매운동 · 캠페인 역풍 · 갑질 폭로 등\n브랜드 특화 위기 유형 정밀 분류"),
    (NAVY,  "즉시 활용 대응 문구",
     "SNS 공식 대응 · 보도자료 · 내부 조치\n3가지 구체 문구 AI가 자동 생성"),
    (RGBColor(0x7c, 0x3a, 0xed), "카드뉴스 자동 생성",
     "위협 데이터 → Claude로 스크립팅\n→ YouTube Shorts 영상 완전 자동화"),
]

for i, (col, title, desc) in enumerate(diffs):
    row = i // 3
    c   = i % 3
    x = 0.4 + c * 4.3
    y = 0.9 + row * 2.95
    rect(sl13, x, y, 4.1, 2.7, LGRAY)
    rect(sl13, x, y, 4.1, 0.08, col)
    rect(sl13, x, y, 0.08, 2.7, col)
    txt(sl13, title, x + 0.2, y + 0.15, 3.8, 0.55, size=13, bold=True, color=NAVY)
    txt(sl13, desc,  x + 0.2, y + 0.78, 3.8, 1.6,  size=10.5, color=DGRAY, wrap=True)


# ════════════════════════════════════════════════════════════════
# Slide 14 — 가격 모델
# ════════════════════════════════════════════════════════════════
sl14 = slide()
header(sl14, "가격 모델", "Polar 결제 — 체크아웃 링크 방식 + Svix 웹훅")
footer(sl14)

pricing = [
    (GRAY,  "Free",       "무료",     ["키워드 5개", "조직 1개", "PDF 다운로드", "기본 모니터링"]),
    (BLUE,  "Starter",    "유료",     ["키워드 20개", "조직 3개", "Slack 알림", "주간 리포트"]),
    (GREEN, "Pro",        "유료",     ["키워드 무제한", "조직 5개", "화이트라벨", "PPT 리포트"]),
    (AMBER, "Enterprise", "문의",     ["맞춤 조직 수", "무제한 모든 기능", "전담 지원", "SLA 보장"]),
]

for i, (col, tier, price, features) in enumerate(pricing):
    x = 0.4 + i * 3.18
    rect(sl14, x, 0.9, 3.0, 5.8, LGRAY)
    rect(sl14, x, 0.9, 3.0, 0.65, col)
    txt(sl14, tier,  x + 0.15, 0.95, 2.7, 0.42, size=16, bold=True, color=WHITE)
    txt(sl14, price, x + 0.15, 1.35, 2.7, 0.32, size=10, color=WHITE)
    for fi, feat in enumerate(features):
        bg = WHITE if fi % 2 == 0 else LGRAY
        rect(sl14, x, 1.58 + fi * 0.9, 3.0, 0.88, bg)
        txt(sl14, "✓  " + feat, x + 0.15, 1.65 + fi * 0.9, 2.7, 0.75,
            size=10, color=NAVY, wrap=True)

# 결제 플로우
rect(sl14, 0.4, 6.82, 12.53, 0.4, NAVY2)
txt(sl14, "결제 플로우:  사용자 → /billing/checkout/{plan} → Polar 체크아웃 → Svix 웹훅 수신 → DB 티어 업데이트",
    0.6, 6.88, 12, 0.3, size=9, color=WHITE)


# ════════════════════════════════════════════════════════════════
# Section — 로드맵 & KPI
# ════════════════════════════════════════════════════════════════
section_divider("10  로드맵 & KPI", "성공 지표와 성장 계획")


# ════════════════════════════════════════════════════════════════
# Slide 15 — 구현 현황
# ════════════════════════════════════════════════════════════════
sl15 = slide()
header(sl15, "현재 구현 상태", f"기준일: {TODAY}")
footer(sl15)

impl_items = [
    ("✅", GREEN, "코어 AI 파이프라인 (L1→L2→L3)",    "실동작"),
    ("✅", GREEN, "리스크 스코어링 엔진",               "실동작"),
    ("✅", GREEN, "Naver 수집기",                       "검증 완료"),
    ("✅", GREEN, "YouTube · X 수집기",                 "API 키 있을 때"),
    ("✅", GREEN, "Gemini L2 분석",                     "유료 전환 완료"),
    ("✅", GREEN, "Claude Haiku L3 분석",               "API 키 있을 때"),
    ("✅", GREEN, "KNU 감성 사전 폴백",                 "항상 동작"),
    ("✅", GREEN, "조직 관리 (RBAC·초대코드·승인)",    "실동작"),
    ("✅", GREEN, "온보딩 플로우 (3단계)",              "실동작"),
    ("✅", GREEN, "Google OAuth 인증",                  "실동작"),
    ("✅", GREEN, "Polar 결제·웹훅",                    "실동작"),
    ("✅", GREEN, "PDF / PPT 보고서",                   "실동작"),
    ("✅", GREEN, "카드뉴스 파이프라인",                "93 tests passed"),
    ("✅", GREEN, "Slack 알림",                         "실동작"),
    ("🟡", AMBER, "Celery 비동기 워커",                 "Redis 환경 필요"),
    ("🟡", AMBER, "이미지 분석 (pHash)",                "엔진 구현, 미통합"),
    ("❌", GRAY,  "Instagram 수집기",                   "v1.1 목표"),
    ("❌", GRAY,  "TikTok 수집기",                     "v1.1 목표"),
]

per_col = (len(impl_items) + 1) // 2
for i, (icon, col, feature, status) in enumerate(impl_items):
    ci = i // per_col
    ri = i % per_col
    x = 0.4 + ci * 6.46
    y = 0.9 + ri * 0.38
    bg = LGRAY if ri % 2 == 0 else WHITE
    rect(sl15, x, y, 6.28, 0.37, bg)
    txt(sl15, icon,    x + 0.08, y + 0.04, 0.4,  0.3, size=11)
    txt(sl15, feature, x + 0.5,  y + 0.04, 4.0,  0.3, size=9.5, color=NAVY)
    txt(sl15, status,  x + 4.6,  y + 0.04, 1.55, 0.3, size=9, bold=True, color=col, align=PP_ALIGN.RIGHT)


# ════════════════════════════════════════════════════════════════
# Slide 16 — 로드맵 & KPI
# ════════════════════════════════════════════════════════════════
sl16 = slide()
header(sl16, "로드맵 & 성공 지표 (KPI)")
footer(sl16)

phases = [
    (GREEN, "MVP — 현재",   "3개월",
     ["파일럿 고객 5개사", "오탐률 < 10%", "핵심 기능 안정화"]),
    (BLUE,  "v1.0",         "6개월",
     ["MRR 2,000만원", "Instagram · TikTok 수집기", "이미지 분석 통합"]),
    (AMBER, "v2.0",         "12개월",
     ["고객사 100개 / NPS 50+", "HyperCLOVA X 연동 강화", "화이트라벨 대량 공급"]),
]

for i, (col, phase, period, goals) in enumerate(phases):
    x = 0.4 + i * 4.3
    rect(sl16, x, 0.9,  4.1, 0.52, col)
    txt(sl16, phase,  x + 0.15, 0.94, 2.5, 0.38, size=14, bold=True, color=WHITE)
    txt(sl16, period, x + 3.0,  0.94, 1.0, 0.38, size=11, color=WHITE, align=PP_ALIGN.RIGHT)
    for gi, goal in enumerate(goals):
        bg = LGRAY if gi % 2 == 0 else WHITE
        rect(sl16, x, 1.42 + gi * 0.7, 4.1, 0.68, bg)
        txt(sl16, "→  " + goal, x + 0.15, 1.47 + gi * 0.7, 3.8, 0.58, size=10.5, color=NAVY, wrap=True)

# KPI 표
rect(sl16, 0.4, 3.58, 12.53, 0.42, NAVY)
for hdr, xp in [("단계", 0.55), ("지표", 3.5), ("목표", 9.5)]:
    txt(sl16, hdr, xp, 3.63, 3.0, 0.35, size=10, bold=True, color=WHITE)

kpis = [
    ("MVP (3개월)",   "파일럿 고객",          "5개사"),
    ("v1.0 (6개월)",  "MRR",                  "2,000만원"),
    ("v2.0 (12개월)", "고객사 / NPS",         "100개 / 50+"),
    ("정확도 (상시)", "오탐률 (False Positive)", "< 10%"),
]
for ri, (stage, metric, target) in enumerate(kpis):
    bg = LGRAY if ri % 2 == 0 else WHITE
    rect(sl16, 0.4, 4.0 + ri * 0.7, 12.53, 0.7, bg)
    txt(sl16, stage,  0.55, 4.07 + ri * 0.7, 3.0,  0.55, size=10, color=NAVY)
    txt(sl16, metric, 3.5,  4.07 + ri * 0.7, 6.1,  0.55, size=10, color=DGRAY)
    txt(sl16, target, 9.5,  4.07 + ri * 0.7, 3.2,  0.55, size=10, bold=True, color=BLUE, align=PP_ALIGN.RIGHT)


# ════════════════════════════════════════════════════════════════
# Slide 17 — 마무리
# ════════════════════════════════════════════════════════════════
sl17 = slide()
rect(sl17, 0, 0, 13.33, 7.5, NAVY)
rect(sl17, 0, 0, 13.33, 0.06, BLUE)
rect(sl17, 0, 7.44, 13.33, 0.06, BLUE)

txt(sl17, "감사합니다", 0.8, 1.2, 11, 1.5, size=52, bold=True, color=WHITE)
txt(sl17, "SAYbrand — AI 기반 브랜드 보호 SaaS",
    0.8, 2.85, 11, 0.65, size=18, color=RGBColor(0xAA, 0xBB, 0xDD))

rect(sl17, 0.8, 3.65, 10.8, 0.05, BLUE)

contacts = [
    ("서비스",   "SAYbrand v0.3.1"),
    ("배포",     "Vercel (API + Frontend)  +  Railway (Celery Worker)"),
    ("AI 엔진",  "Gemini 2.5 Flash Lite (L2)  +  Claude Haiku 4.5 (L3)"),
    ("테스트",   "카드뉴스 파이프라인 93 tests passed"),
]
for i, (label, val) in enumerate(contacts):
    txt(sl17, label, 0.8, 3.9 + i * 0.65, 2.2, 0.55, size=11,
        color=RGBColor(0xAA, 0xBB, 0xDD))
    txt(sl17, val,   3.1, 3.9 + i * 0.65, 8.5, 0.55, size=11, color=WHITE)

txt(sl17, TODAY, 0.8, 7.0, 12, 0.4, size=9,
    color=RGBColor(0x55, 0x66, 0x88), align=PP_ALIGN.RIGHT)


# ════════════════════════════════════════════════════════════════
# 저장
# ════════════════════════════════════════════════════════════════
out_path = Path(__file__).parent / "SAYbrand_deck.pptx"
prs.save(str(out_path))
print(f"저장 완료: {out_path}")
print(f"슬라이드 수: {len(prs.slides)}장")
