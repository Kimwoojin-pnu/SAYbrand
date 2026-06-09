"""리포트 생성 서비스 — 일간/주간/월간 위협 요약 + PDF"""
from __future__ import annotations

import html
import io
import logging
import os
import re
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.orm import CustomerAlias, CustomerProfile, Keyword, Threat

logger = logging.getLogger(__name__)

# 이 파일 기준으로 번들 폰트 경로 결정
_FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
_BUNDLED_REGULAR = os.path.join(_FONTS_DIR, "NanumGothic.ttf")
_BUNDLED_BOLD    = os.path.join(_FONTS_DIR, "NanumGothicBold.ttf")


def _esc(text: object) -> str:
    """ReportLab Paragraph XML 특수문자 이스케이프."""
    return html.escape(str(text or ""), quote=False)


def _clean(text: object, max_len: int = 200) -> str:
    """텍스트 정리 후 이스케이프: 개행/탭→공백, 과도한 공백 제거, XML 이스케이프."""
    s = str(text or "")[:max_len]
    s = re.sub(r"[\r\n\t]+", " ", s)
    s = re.sub(r" {2,}", " ", s).strip()
    return html.escape(s, quote=False)


def _period_range(period: str) -> tuple[datetime, str]:
    # DB DateTime 컬럼은 naive UTC — timezone.utc 사용 시 asyncpg DataError
    now = datetime.utcnow()
    if period == "daily":
        since = now - timedelta(days=1)
        label = f"{now.strftime('%Y년 %m월 %d일')} 일간 보고서"
    elif period == "weekly":
        since = now - timedelta(days=7)
        label = f"{now.strftime('%Y년 %m월 %d일')} 기준 주간 보고서"
    else:  # monthly
        since = now - timedelta(days=30)
        label = f"{now.strftime('%Y년 %m월')} 월간 보고서"
    return since, label


async def generate_report(
    user_id: int,
    period: str,
    db: AsyncSession,
    org_id: int | None = None,
) -> dict:
    """
    period: "daily" (24h) | "weekly" (7일) | "monthly" (30일)
    오탐(false_positive)은 통계에서 제외.
    """
    # DB DateTime 컬럼은 naive UTC — timezone.utc 사용 시 asyncpg DataError
    now = datetime.utcnow()
    since, label = _period_range(period)

    def _scope(q):
        q = q.where(Threat.detected_at >= since)
        if org_id is not None:
            return q.where(Threat.org_id == org_id)
        return q.where(Threat.user_id == user_id)

    def _scope_no_fp(q):
        return _scope(q).where(
            (Threat.resolution_type == None) | (Threat.resolution_type != "false_positive")
        )

    total_result = await db.execute(_scope_no_fp(select(func.count(Threat.id))))
    total = total_result.scalar() or 0

    sev_result = await db.execute(
        _scope_no_fp(select(Threat.severity, func.count(Threat.id))).group_by(Threat.severity)
    )
    by_severity = {row[0]: row[1] for row in sev_result}

    plat_result = await db.execute(
        _scope_no_fp(select(Threat.platform, func.count(Threat.id))).group_by(Threat.platform)
    )
    by_platform = {row[0]: row[1] for row in plat_result}

    resolved_result = await db.execute(
        _scope_no_fp(select(func.count(Threat.id))).where(Threat.status == "resolved")
    )
    resolved_count = resolved_result.scalar() or 0

    # 미해결 위협 (active)
    unresolved_result = await db.execute(
        _scope_no_fp(select(func.count(Threat.id))).where(Threat.status == "active")
    )
    unresolved_count = unresolved_result.scalar() or 0

    # 부정적 언급 수
    negative_result = await db.execute(
        _scope_no_fp(select(func.count(Threat.id))).where(Threat.sentiment == "negative")
    )
    negative_count = negative_result.scalar() or 0

    # 브랜드 이미지 점수
    brand_score = max(0.0, 100.0 - (negative_count / max(total, 1) * 100))

    # 오탐 건수
    fp_result = await db.execute(
        _scope(select(func.count(Threat.id))).where(Threat.resolution_type == "false_positive")
    )
    false_positive_count = fp_result.scalar() or 0

    # 실제 위협 해결 건수
    real_resolved_result = await db.execute(
        _scope(select(func.count(Threat.id))).where(Threat.resolution_type == "real_resolved")
    )
    real_resolved_count = real_resolved_result.scalar() or 0

    # Top 10 미해결 위협
    top_result = await db.execute(
        _scope_no_fp(select(Threat))
        .where(Threat.status == "active")
        .order_by(Threat.risk_score.desc())
        .limit(10)
    )
    unresolved_threats = [
        {
            "id": t.id,
            "severity": t.severity,
            "platform": t.platform,
            "source_account": t.source_account,
            "content_preview": (t.content_preview or "")[:100],
            "risk_score": t.risk_score,
            "source_url": t.source_url,
            "detected_at": t.detected_at.isoformat() if t.detected_at else None,
        }
        for t in top_result.scalars().all()
    ]

    # 해결 완료된 실제 위협 (보고서용)
    real_res_result = await db.execute(
        _scope(select(Threat))
        .where(Threat.resolution_type == "real_resolved")
        .order_by(Threat.updated_at.desc())
        .limit(5)
    )
    resolved_threats = [
        {
            "id": t.id,
            "platform": t.platform,
            "resolution_method": t.resolution_method,
            "note": t.resolution_note,
        }
        for t in real_res_result.scalars().all()
    ]

    # 부정적 언급 샘플
    neg_result = await db.execute(
        _scope_no_fp(select(Threat))
        .where(Threat.sentiment == "negative")
        .order_by(Threat.risk_score.desc())
        .limit(5)
    )
    negative_samples = [
        {
            "platform": t.platform,
            "content": (t.content_preview or "")[:80],
            "reach": t.reach_estimate,
        }
        for t in neg_result.scalars().all()
    ]

    # 감정(emotion) 분포 Top 7
    emotion_result = await db.execute(
        _scope_no_fp(
            select(Threat.emotion, func.count(Threat.id).label("cnt"))
        ).where(Threat.emotion.isnot(None)).group_by(Threat.emotion).order_by(func.count(Threat.id).desc()).limit(7)
    )
    by_emotion = {row[0]: row[1] for row in emotion_result if row[0]}

    # 감성 분포 (긍정/중립/부정)
    senti_result = await db.execute(
        _scope_no_fp(
            select(Threat.sentiment, func.count(Threat.id).label("cnt"))
        ).where(Threat.sentiment.isnot(None)).group_by(Threat.sentiment)
    )
    by_sentiment = {row[0]: row[1] for row in senti_result if row[0]}

    # 플랫폼별 감성 분포
    plat_senti_result = await db.execute(
        _scope_no_fp(
            select(Threat.platform, Threat.sentiment, func.count(Threat.id).label("cnt"))
        ).where(Threat.sentiment.isnot(None)).group_by(Threat.platform, Threat.sentiment)
    )
    by_platform_sentiment: dict[str, dict] = {}
    for row in plat_senti_result:
        p = row[0] or "unknown"
        s = row[1] or "neutral"
        by_platform_sentiment.setdefault(p, {})[s] = row[2]

    # 위협 유형 Top 5
    ttype_result = await db.execute(
        _scope_no_fp(
            select(Threat.threat_type, func.count(Threat.id).label("cnt"))
        ).where(Threat.threat_type.isnot(None)).group_by(Threat.threat_type)
        .order_by(func.count(Threat.id).desc()).limit(5)
    )
    top_threat_types = [{"type": row[0], "count": row[1]} for row in ttype_result if row[0]]

    # 조직적 공격 건수
    organized_result = await db.execute(
        _scope_no_fp(select(func.count(Threat.id))).where(Threat.is_organized == True)
    )
    organized_count = organized_result.scalar() or 0

    # 봇 의심 건수 (bot_probability >= 0.5)
    bot_result = await db.execute(
        _scope_no_fp(select(func.count(Threat.id))).where(Threat.bot_probability >= 0.5)
    )
    bot_count = bot_result.scalar() or 0

    # Top 10 미해결 위협 (상세 정보 포함)
    top_result = await db.execute(
        _scope_no_fp(select(Threat))
        .where(Threat.status == "active")
        .order_by(Threat.risk_score.desc())
        .limit(10)
    )
    unresolved_threats = [
        {
            "id": t.id,
            "severity": t.severity,
            "platform": t.platform,
            "module": t.module,
            "threat_type": t.threat_type,
            "source_account": t.source_account,
            "content_preview": (t.content_preview or "")[:200],
            "risk_score": t.risk_score,
            "confidence": t.confidence,
            "source_url": t.source_url,
            "sentiment": t.sentiment,
            "emotion": t.emotion,
            "bot_probability": t.bot_probability,
            "is_organized": t.is_organized,
            "ai_response_suggestion": (t.ai_response_suggestion or "")[:300],
            "detected_at": t.detected_at.isoformat() if t.detected_at else None,
        }
        for t in top_result.scalars().all()
    ]

    # AI 권고 샘플 (ai_response_suggestion이 있는 위협 Top 3)
    ai_sugg_result = await db.execute(
        _scope_no_fp(select(Threat))
        .where(Threat.ai_response_suggestion.isnot(None))
        .order_by(Threat.risk_score.desc())
        .limit(3)
    )
    ai_suggestions = [
        {
            "severity": t.severity,
            "platform": t.platform,
            "threat_type": t.threat_type,
            "suggestion": (t.ai_response_suggestion or "")[:400],
        }
        for t in ai_sugg_result.scalars().all()
        if t.ai_response_suggestion
    ]

    # 브랜드 프로파일
    profile_result = await db.execute(
        select(CustomerProfile).where(CustomerProfile.user_id == user_id).limit(1)
    )
    profile = profile_result.scalar_one_or_none()
    brand_info = {
        "name": profile.display_name if profile else "내 브랜드",
        "industry": profile.industry if profile else "",
    }

    # 모니터링 키워드
    kw_filter = Keyword.org_id == org_id if org_id else Keyword.user_id == user_id
    kw_result = await db.execute(
        select(Keyword.keyword).where(kw_filter, Keyword.active == True).limit(20)
    )
    keywords = [row[0] for row in kw_result if row[0]]

    # 해결 완료된 실제 위협 (보고서용)
    real_res_result = await db.execute(
        _scope(select(Threat))
        .where(Threat.resolution_type == "real_resolved")
        .order_by(Threat.updated_at.desc())
        .limit(10)
    )
    resolved_threats = [
        {
            "id": t.id,
            "platform": t.platform,
            "severity": t.severity,
            "threat_type": t.threat_type,
            "source_account": t.source_account,
            "resolution_method": t.resolution_method,
            "note": t.resolution_note,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in real_res_result.scalars().all()
    ]

    # 부정적 언급 샘플
    neg_result = await db.execute(
        _scope_no_fp(select(Threat))
        .where(Threat.sentiment == "negative")
        .order_by(Threat.risk_score.desc())
        .limit(5)
    )
    negative_samples = [
        {
            "platform": t.platform,
            "content": (t.content_preview or "")[:150],
            "reach": t.reach_estimate,
            "emotion": t.emotion,
            "source_url": t.source_url,
        }
        for t in neg_result.scalars().all()
    ]

    # 하위 호환성 top_threats
    top_all_result = await db.execute(
        _scope_no_fp(select(Threat)).order_by(Threat.risk_score.desc()).limit(5)
    )
    top_threats = [
        {
            "id": t.id,
            "severity": t.severity,
            "platform": t.platform,
            "source_account": t.source_account,
            "content_preview": t.content_preview,
            "risk_score": t.risk_score,
            "status": t.status,
            "source_url": t.source_url,
        }
        for t in top_all_result.scalars().all()
    ]

    return {
        "label": label,
        "period": f"{since.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}",
        "period_type": period,
        "generated_at": now.isoformat(),
        "brand_info": brand_info,
        "keywords": keywords,
        "summary": {
            "total_threats": total,
            "unresolved_count": unresolved_count,
            "resolved_count": resolved_count,
            "negative_mentions": negative_count,
            "brand_score": round(brand_score, 1),
            "false_positive_count": false_positive_count,
            "real_resolved_count": real_resolved_count,
            "organized_count": organized_count,
            "bot_count": bot_count,
        },
        # 하위 호환성
        "total_threats": total,
        "by_severity": by_severity,
        "by_platform": by_platform,
        "by_sentiment": by_sentiment,
        "by_emotion": by_emotion,
        "by_platform_sentiment": by_platform_sentiment,
        "top_threat_types": top_threat_types,
        "resolved_count": resolved_count,
        "top_threats": top_threats,
        "unresolved_threats": unresolved_threats,
        "resolved_threats": resolved_threats,
        "negative_samples": negative_samples,
        "ai_suggestions": ai_suggestions,
        "is_mock": total == 0,
    }


async def generate_pdf_report(
    user_id: int,
    period: str,
    db: AsyncSession,
    org_id: int | None = None,
) -> bytes:
    data = await generate_report(user_id, period, db, org_id=org_id)

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import (
            HRFlowable, KeepTogether, PageBreak, Paragraph,
            SimpleDocTemplate, Spacer, Table, TableStyle,
        )

        # ── 폰트 등록 ──────────────────────────────────────────────────────────
        _FONT_CANDIDATES = [
            (_BUNDLED_REGULAR, _BUNDLED_BOLD),
            ("C:/Windows/Fonts/malgun.ttf", "C:/Windows/Fonts/malgunbd.ttf"),
            ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
             "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"),
        ]
        KR, KR_BOLD = "Helvetica", "Helvetica-Bold"
        _reg = pdfmetrics.getRegisteredFontNames()
        for rp, bp in _FONT_CANDIDATES:
            if not os.path.exists(rp):
                continue
            try:
                if "SAYKorean" not in _reg:
                    pdfmetrics.registerFont(TTFont("SAYKorean", rp))
                KR = "SAYKorean"
                if os.path.exists(bp):
                    if "SAYKoreanBold" not in _reg:
                        pdfmetrics.registerFont(TTFont("SAYKoreanBold", bp))
                    KR_BOLD = "SAYKoreanBold"
                else:
                    KR_BOLD = KR
                break
            except Exception as _fe:
                logger.warning("폰트 등록 실패: %s", _fe)

        # ── 색상 팔레트 ─────────────────────────────────────────────────────────
        C_NAVY   = colors.HexColor("#0c1428")
        C_BLUE   = colors.HexColor("#1d5fa8")
        C_BLUE_L = colors.HexColor("#e8f0fb")
        C_RED    = colors.HexColor("#E24B4A")
        C_AMBER  = colors.HexColor("#BA7517")
        C_GREEN  = colors.HexColor("#1D9E75")
        C_PURPLE = colors.HexColor("#185FA5")
        C_GRAY   = colors.HexColor("#f5f6f8")
        C_DGRAY  = colors.HexColor("#888888")
        C_LGRAY  = colors.HexColor("#dddddd")
        C_WHITE  = colors.white

        SEV_COLOR = {
            "critical": C_RED, "high": C_AMBER,
            "medium": C_PURPLE, "low": C_GREEN,
        }
        SEV_LABEL = {
            "critical": "위험 (Critical)", "high": "높음 (High)",
            "medium": "중간 (Medium)", "low": "낮음 (Low)",
        }
        PLAT_KO = {
            "youtube": "YouTube", "instagram": "Instagram",
            "x": "X (Twitter)", "tiktok": "TikTok", "naver": "Naver",
        }

        # ── 스타일 ──────────────────────────────────────────────────────────────
        def ST(name, font=None, size=10, leading=15, color=None, bold=False, **kw):
            fn = kw.pop("fontName", KR_BOLD if bold else (font or KR))
            fs = kw.pop("fontSize", size)
            return ParagraphStyle(
                name, fontName=fn, fontSize=fs, leading=leading,
                textColor=color or colors.black, **kw
            )

        ST_BODY    = ST("Body",   size=10, leading=16)
        ST_SMALL   = ST("Small",  size=8,  leading=12, color=C_DGRAY)
        ST_CAPTION = ST("Cap",    size=9,  leading=13, color=C_DGRAY)
        ST_H1      = ST("H1",     size=20, leading=26, bold=True)
        ST_H2      = ST("H2",     size=13, leading=19, bold=True, spaceBefore=4, spaceAfter=3)
        ST_H3      = ST("H3",     size=11, leading=16, bold=True, spaceBefore=2, spaceAfter=2)
        ST_COVER_S = ST("CovS",   size=11, leading=17, color=colors.HexColor("#aabbdd"))
        ST_COVER_T = ST("CovT",   size=28, leading=36, bold=True, color=C_WHITE)
        ST_COVER_B = ST("CovB",   size=14, leading=20, color=C_WHITE)
        ST_SCORE   = ST("Score",  size=48, leading=56, bold=True, color=C_BLUE, alignment=1)
        ST_SCORE_L = ST("ScoreL", size=11, leading=15, color=C_DGRAY, alignment=1)
        ST_TBL_H   = ST("TblH",   size=9,  leading=13, bold=True, color=C_WHITE)
        ST_TBL_C   = ST("TblC",   size=9,  leading=13)
        ST_FOOTER  = ST("Foot",   size=8,  leading=12, color=C_DGRAY)

        def _tbl_style(hdr_color=C_NAVY, row_alt=True):
            base = [
                ("BACKGROUND", (0, 0), (-1, 0), hdr_color),
                ("TEXTCOLOR",  (0, 0), (-1, 0), C_WHITE),
                ("FONTNAME",   (0, 0), (-1, 0), KR_BOLD),
                ("FONTNAME",   (0, 1), (-1, -1), KR),
                ("FONTSIZE",   (0, 0), (-1, -1), 9),
                ("GRID",       (0, 0), (-1, -1), 0.4, C_LGRAY),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING",   (0, 0), (-1, -1), 6),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
                ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ]
            if row_alt:
                base.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_GRAY]))
            return TableStyle(base)

        def _bar(ratio: float, width_mm: float = 80, color=C_BLUE) -> Table:
            """비율 막대 그래프 (0~1)."""
            ratio = max(0.0, min(1.0, ratio))
            filled = width_mm * ratio
            empty  = width_mm - filled
            cells  = [[" "]]
            col_w  = [filled * mm] if filled > 0 else []
            col_w += [empty * mm] if empty > 0 else []
            if not col_w:
                col_w = [width_mm * mm]
            row = [""] * len(col_w)
            tbl = Table([row], colWidths=col_w, rowHeights=[5 * mm])
            style_cmds = [
                ("TOPPADDING",    (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
                ("GRID",          (0, 0), (-1, -1), 0, C_WHITE),
                ("BOX",           (0, 0), (-1, -1), 0.3, C_LGRAY),
            ]
            if filled > 0:
                style_cmds.append(("BACKGROUND", (0, 0), (0, 0), color))
            if empty > 0 and len(col_w) > 1:
                style_cmds.append(("BACKGROUND", (1, 0), (1, 0), C_GRAY))
            tbl.setStyle(TableStyle(style_cmds))
            return tbl

        def _section_hdr(title: str, subtitle: str = "") -> list:
            """섹션 구분 헤더 블록."""
            items = [
                Spacer(1, 3 * mm),
                HRFlowable(width="100%", thickness=1.5, color=C_NAVY, spaceAfter=3),
                Paragraph(_esc(title), ST_H2),
            ]
            if subtitle:
                items.append(Paragraph(_esc(subtitle), ST_CAPTION))
            items.append(Spacer(1, 2 * mm))
            return items

        # ── 헤더/푸터 콜백 ──────────────────────────────────────────────────────
        PAGE_W, PAGE_H = A4
        brand_name = _esc(data.get("brand_info", {}).get("name", "내 브랜드"))
        gen_date   = _esc(data["generated_at"][:10])

        def _on_page(canvas, doc):
            canvas.saveState()
            pg = doc.page
            if pg == 1:  # 표지는 헤더/푸터 없음
                canvas.restoreState()
                return
            # 상단 헤더 라인
            canvas.setFillColor(C_NAVY)
            canvas.rect(15 * mm, PAGE_H - 13 * mm, PAGE_W - 30 * mm, 0.5, fill=1, stroke=0)
            canvas.setFont(KR_BOLD, 8)
            canvas.setFillColor(C_NAVY)
            canvas.drawString(15 * mm, PAGE_H - 11 * mm, "SAYbrand 브랜드 위협 모니터링 보고서")
            canvas.setFont(KR, 8)
            canvas.setFillColor(C_DGRAY)
            canvas.drawRightString(PAGE_W - 15 * mm, PAGE_H - 11 * mm, f"{brand_name}  |  {gen_date}")
            # 하단 푸터
            canvas.setFillColor(C_LGRAY)
            canvas.rect(15 * mm, 10 * mm, PAGE_W - 30 * mm, 0.5, fill=1, stroke=0)
            canvas.setFont(KR, 7.5)
            canvas.setFillColor(C_DGRAY)
            canvas.drawString(15 * mm, 7 * mm, "본 보고서는 SAYbrand AI가 자동 생성한 문서입니다. 배포 시 기밀 유지 의무가 적용됩니다.")
            canvas.drawRightString(PAGE_W - 15 * mm, 7 * mm, f"- {pg} -")
            canvas.restoreState()

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=15 * mm, rightMargin=15 * mm,
            topMargin=18 * mm, bottomMargin=18 * mm,
        )

        story = []
        s = data["summary"]
        total = s["total_threats"] or 1  # 0 나눗셈 방지

        # ════════════════════════════════════════════════════════════════
        # 1. 표지
        # ════════════════════════════════════════════════════════════════
        period_type_ko = {"daily": "일간", "weekly": "주간", "monthly": "월간"}.get(
            data.get("period_type", ""), "기간"
        )
        industry = _esc(data.get("brand_info", {}).get("industry") or "")
        industry_str = f"  |  {industry}" if industry else ""

        # 표지 전용 큰 색상 블록 (Table로 구현)
        cover_top = Table(
            [[Paragraph(f"SAYbrand{industry_str}", ST_COVER_S)],
             [Paragraph(f"{brand_name}", ST_COVER_T)],
             [Spacer(1, 6 * mm)],
             [Paragraph(f"브랜드 위협 모니터링  {period_type_ko} 보고서", ST_COVER_B)],
             [Spacer(1, 4 * mm)],
             [Paragraph(f"보고 기간 : {_esc(data['period'])}", ST_COVER_S)],
             [Paragraph(f"생성일      : {gen_date}", ST_COVER_S)]],
            colWidths=[PAGE_W - 30 * mm],
            rowHeights=None,
        )
        cover_top.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), C_NAVY),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 14),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ]))

        # 브랜드 이미지 점수 강조 블록
        score_val = s["brand_score"]
        score_color = C_GREEN if score_val >= 70 else (C_AMBER if score_val >= 40 else C_RED)
        score_tbl = Table(
            [[Paragraph(f"{score_val}", ST("ScoreBig", size=52, leading=60, bold=True,
                                           color=score_color, alignment=1))],
             [Paragraph("브랜드 이미지 점수 / 100", ST_SCORE_L)]],
            colWidths=[PAGE_W - 30 * mm],
        )
        score_tbl.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("BACKGROUND",    (0, 0), (-1, -1), C_BLUE_L),
        ]))

        # 표지 KPI 요약 (2열 그리드)
        cover_kpi = [
            ["총 탐지 위협", str(s["total_threats"]),
             "미해결", str(s["unresolved_count"])],
            ["부정 언급", str(s["negative_mentions"]),
             "조직적 공격", str(s.get("organized_count", 0))],
            ["오탐 처리", str(s["false_positive_count"]),
             "봇 의심", str(s.get("bot_count", 0))],
        ]
        cover_kpi_tbl = Table(cover_kpi, colWidths=[40 * mm, 28 * mm, 40 * mm, 28 * mm])
        cover_kpi_tbl.setStyle(TableStyle([
            ("FONTNAME",      (0, 0), (-1, -1), KR),
            ("FONTNAME",      (0, 0), (0, -1), KR_BOLD),
            ("FONTNAME",      (2, 0), (2, -1), KR_BOLD),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("FONTSIZE",      (1, 0), (1, -1), 14),
            ("FONTSIZE",      (3, 0), (3, -1), 14),
            ("ALIGN",         (1, 0), (1, -1), "CENTER"),
            ("ALIGN",         (3, 0), (3, -1), "CENTER"),
            ("TEXTCOLOR",     (1, 0), (1, -1), C_NAVY),
            ("TEXTCOLOR",     (3, 0), (3, -1), C_NAVY),
            ("GRID",          (0, 0), (-1, -1), 0.4, C_LGRAY),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS",(0, 0), (-1, -1), [C_WHITE, C_GRAY]),
        ]))

        story += [
            cover_top,
            Spacer(1, 6 * mm),
            score_tbl,
            Spacer(1, 6 * mm),
            cover_kpi_tbl,
            Spacer(1, 8 * mm),
            Paragraph(
                "본 보고서는 SAYbrand AI 브랜드 보호 서비스가 자동 수집·분석한 "
                "데이터를 기반으로 생성되었습니다. 위협 탐지, 감성 분석, "
                "조직적 공격 패턴, AI 대응 권고사항을 포함합니다.",
                ST("CoverNote", fontName=KR, fontSize=9, leading=14, color=C_DGRAY)
            ),
            PageBreak(),
        ]

        # ════════════════════════════════════════════════════════════════
        # 2. 핵심 요약 (Executive Summary)
        # ════════════════════════════════════════════════════════════════
        story += _section_hdr("1. 핵심 요약 (Executive Summary)",
                               f"분석 기간: {_esc(data['period'])}")

        kpi_rows = [
            ["항목", "수치", "항목", "수치"],
            ["총 위협 건수", f"{s['total_threats']:,}건",
             "브랜드 이미지 점수", f"{s['brand_score']}/100"],
            ["미해결 위협", f"{s['unresolved_count']:,}건",
             "부정적 언급", f"{s['negative_mentions']:,}건"],
            ["실제 위협 해결", f"{s['real_resolved_count']:,}건",
             "오탐 처리", f"{s['false_positive_count']:,}건"],
            ["조직적 공격", f"{s.get('organized_count', 0):,}건",
             "봇 의심 계정", f"{s.get('bot_count', 0):,}건"],
        ]
        kpi_tbl = Table(kpi_rows, colWidths=[48 * mm, 30 * mm, 48 * mm, 30 * mm])
        kpi_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), C_NAVY),
            ("TEXTCOLOR",     (0, 0), (-1, 0), C_WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), KR_BOLD),
            ("FONTNAME",      (0, 1), (-1, -1), KR),
            ("FONTNAME",      (0, 1), (0, -1), KR_BOLD),
            ("FONTNAME",      (2, 1), (2, -1), KR_BOLD),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("FONTSIZE",      (1, 1), (1, -1), 13),
            ("FONTSIZE",      (3, 1), (3, -1), 13),
            ("ALIGN",         (1, 0), (1, -1), "CENTER"),
            ("ALIGN",         (3, 0), (3, -1), "CENTER"),
            ("TEXTCOLOR",     (1, 1), (1, -1), C_NAVY),
            ("TEXTCOLOR",     (3, 1), (3, -1), C_NAVY),
            ("GRID",          (0, 0), (-1, -1), 0.4, C_LGRAY),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_WHITE, C_GRAY]),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(kpi_tbl)
        story.append(Spacer(1, 5 * mm))

        # 브랜드 이미지 점수 상태 설명
        score_status = (
            "양호 — 부정 언급 비율이 낮고 브랜드 평판이 안정적입니다." if score_val >= 70 else
            "주의 — 부정적 언급이 증가하고 있습니다. 신속한 모니터링이 필요합니다." if score_val >= 40 else
            "위험 — 브랜드 평판 훼손이 우려됩니다. 즉각적인 대응이 필요합니다."
        )
        story.append(Paragraph(
            f"브랜드 이미지 점수 {score_val}/100 — {_esc(score_status)}",
            ST("SumNote", fontName=KR, fontSize=9, leading=14,
               backColor=C_BLUE_L, leftIndent=6, rightIndent=6,
               borderPad=5, borderWidth=0, borderLeftWidth=3, borderColor=C_BLUE)
        ))
        story.append(Spacer(1, 5 * mm))

        # 미해결 고위험 건수 인사이트
        crit_cnt = data.get("by_severity", {}).get("critical", 0)
        high_cnt = data.get("by_severity", {}).get("high", 0)
        if crit_cnt or high_cnt:
            story.append(Paragraph(
                f"  위험(Critical) {crit_cnt:,}건, 높음(High) {high_cnt:,}건의 고위험 위협이 탐지되었습니다. "
                "즉각적인 검토와 대응이 권고됩니다.",
                ST("Insight", fontName=KR, fontSize=9, leading=14,
                   backColor=colors.HexColor("#fff5f5"), leftIndent=6,
                   borderPad=5, borderWidth=0, borderLeftWidth=3, borderColor=C_RED)
            ))
        story.append(PageBreak())

        # ════════════════════════════════════════════════════════════════
        # 3. 위협 현황 분석
        # ════════════════════════════════════════════════════════════════
        story += _section_hdr("2. 위협 현황 분석")

        # 3-1 심각도별 분포
        story.append(Paragraph("■ 심각도별 분포", ST_H3))
        by_s = data.get("by_severity", {})
        sev_rows = [["심각도", "건수", "비율", "분포"]]
        for sev in ("critical", "high", "medium", "low"):
            cnt = by_s.get(sev, 0)
            if cnt == 0:
                continue
            ratio = cnt / total
            sev_rows.append([
                Paragraph(SEV_LABEL.get(sev, sev),
                          ST(f"SL{sev}", fontName=KR_BOLD, fontSize=9,
                             color=SEV_COLOR.get(sev, C_NAVY))),
                f"{cnt:,}",
                f"{ratio*100:.1f}%",
                _bar(ratio, 55, SEV_COLOR.get(sev, C_BLUE)),
            ])
        if len(sev_rows) > 1:
            sev_tbl = Table(sev_rows, colWidths=[42 * mm, 20 * mm, 18 * mm, 58 * mm])
            sev_tbl.setStyle(_tbl_style(C_NAVY))
            story.append(sev_tbl)
        story.append(Spacer(1, 4 * mm))

        # 3-2 플랫폼별 분포
        story.append(Paragraph("■ 플랫폼별 분포", ST_H3))
        by_p = data.get("by_platform", {})
        plat_rows = [["플랫폼", "건수", "비율", "분포"]]
        for plat, cnt in sorted(by_p.items(), key=lambda x: x[1], reverse=True):
            ratio = cnt / total
            plat_rows.append([
                PLAT_KO.get(plat, _esc(plat)),
                f"{cnt:,}",
                f"{ratio*100:.1f}%",
                _bar(ratio, 55, C_BLUE),
            ])
        if len(plat_rows) > 1:
            plat_tbl = Table(plat_rows, colWidths=[42 * mm, 20 * mm, 18 * mm, 58 * mm])
            plat_tbl.setStyle(_tbl_style(C_BLUE))
            story.append(plat_tbl)
        story.append(Spacer(1, 4 * mm))

        # 3-3 위협 유형 Top 5
        top_types = data.get("top_threat_types", [])
        if top_types:
            story.append(Paragraph("■ 위협 유형 Top 5", ST_H3))
            type_rows = [["위협 유형", "건수", "비율", "분포"]]
            max_t = top_types[0]["count"] if top_types else 1
            for tt in top_types[:5]:
                ratio = tt["count"] / total
                type_rows.append([
                    _clean(tt["type"], 40),
                    f"{tt['count']:,}",
                    f"{ratio*100:.1f}%",
                    _bar(tt["count"] / max_t, 55, C_PURPLE),
                ])
            type_tbl = Table(type_rows, colWidths=[58 * mm, 16 * mm, 18 * mm, 46 * mm])
            type_tbl.setStyle(_tbl_style(C_PURPLE))
            story.append(type_tbl)

        story.append(PageBreak())

        # ════════════════════════════════════════════════════════════════
        # 4. 감성 · 감정 분석
        # ════════════════════════════════════════════════════════════════
        story += _section_hdr("3. 감성 · 감정 분석",
                               "KNU 한국어 감성 사전 기반 AI 분석 결과")

        by_senti = data.get("by_sentiment", {})
        senti_total = sum(by_senti.values()) or 1
        senti_ko = {"negative": "부정", "neutral": "중립", "positive": "긍정"}
        senti_color = {"negative": C_RED, "neutral": C_DGRAY, "positive": C_GREEN}

        # 4-1 감성 분포
        story.append(Paragraph("■ 감성 분포", ST_H3))
        senti_rows = [["감성", "건수", "비율", "분포"]]
        for sk in ("negative", "neutral", "positive"):
            cnt = by_senti.get(sk, 0)
            ratio = cnt / senti_total
            senti_rows.append([
                Paragraph(senti_ko.get(sk, sk),
                          ST(f"SentiL{sk}", fontName=KR_BOLD, fontSize=9,
                             color=senti_color.get(sk, C_NAVY))),
                f"{cnt:,}",
                f"{ratio*100:.1f}%",
                _bar(ratio, 55, senti_color.get(sk, C_BLUE)),
            ])
        senti_tbl = Table(senti_rows, colWidths=[42 * mm, 20 * mm, 18 * mm, 58 * mm])
        senti_tbl.setStyle(_tbl_style(C_NAVY))
        story.append(senti_tbl)
        story.append(Spacer(1, 4 * mm))

        # 4-2 감정 분류 Top 7
        by_emo = data.get("by_emotion", {})
        if by_emo:
            story.append(Paragraph("■ 감정 분류", ST_H3))
            emo_total = sum(by_emo.values()) or 1
            emo_rows = [["감정", "건수", "비율", "분포"]]
            emo_color_map = {
                "분노": C_RED, "공포": C_AMBER, "혐오": colors.HexColor("#9B59B6"),
                "슬픔": C_PURPLE, "놀람": colors.HexColor("#E67E22"),
                "기쁨": C_GREEN, "중립": C_DGRAY,
            }
            for emo, cnt in sorted(by_emo.items(), key=lambda x: x[1], reverse=True):
                ratio = cnt / emo_total
                emo_rows.append([
                    Paragraph(_esc(emo),
                              ST(f"EmoL{emo}", fontName=KR_BOLD, fontSize=9,
                                 color=emo_color_map.get(emo, C_NAVY))),
                    f"{cnt:,}",
                    f"{ratio*100:.1f}%",
                    _bar(ratio, 55, emo_color_map.get(emo, C_BLUE)),
                ])
            emo_tbl = Table(emo_rows, colWidths=[42 * mm, 20 * mm, 18 * mm, 58 * mm])
            emo_tbl.setStyle(_tbl_style(C_BLUE))
            story.append(emo_tbl)
            story.append(Spacer(1, 4 * mm))

        # 4-3 부정 언급 샘플
        neg_samples = data.get("negative_samples", [])
        if neg_samples:
            story.append(Paragraph("■ 주요 부정적 언급 사례", ST_H3))
            neg_rows = [["플랫폼", "감정", "주요 내용"]]
            for ns in neg_samples:
                neg_rows.append([
                    PLAT_KO.get(ns.get("platform", ""), _esc(ns.get("platform", ""))),
                    _esc(ns.get("emotion") or "—"),
                    _clean(ns.get("content") or "", 120),
                ])
            neg_tbl = Table(neg_rows, colWidths=[22 * mm, 18 * mm, 98 * mm])
            neg_tbl.setStyle(_tbl_style(C_AMBER))
            story.append(neg_tbl)

        story.append(PageBreak())

        # ════════════════════════════════════════════════════════════════
        # 5. 조직적 공격 · 봇 분석
        # ════════════════════════════════════════════════════════════════
        story += _section_hdr("4. 조직적 공격 및 봇 활동 분석")

        org_cnt  = s.get("organized_count", 0)
        bot_cnt  = s.get("bot_count", 0)
        org_ratio = org_cnt / total
        bot_ratio = bot_cnt / total

        threat_summary_rows = [
            ["구분", "건수", "전체 대비 비율"],
            ["조직적 공격 탐지", f"{org_cnt:,}건", f"{org_ratio*100:.1f}%"],
            ["봇 의심 계정 발생", f"{bot_cnt:,}건", f"{bot_ratio*100:.1f}%"],
        ]
        org_tbl = Table(threat_summary_rows, colWidths=[60 * mm, 40 * mm, 38 * mm])
        org_tbl.setStyle(_tbl_style(C_RED))
        story.append(org_tbl)
        story.append(Spacer(1, 4 * mm))

        # 플랫폼별 감성 분포 테이블
        by_ps = data.get("by_platform_sentiment", {})
        if by_ps:
            story.append(Paragraph("■ 플랫폼별 감성 분포", ST_H3))
            ps_rows = [["플랫폼", "부정", "중립", "긍정", "합계"]]
            for plat in sorted(by_ps.keys()):
                d = by_ps[plat]
                neg_n = d.get("negative", 0)
                neu_n = d.get("neutral", 0)
                pos_n = d.get("positive", 0)
                tot_n = neg_n + neu_n + pos_n or 1
                ps_rows.append([
                    PLAT_KO.get(plat, _esc(plat)),
                    f"{neg_n:,} ({neg_n/tot_n*100:.0f}%)",
                    f"{neu_n:,} ({neu_n/tot_n*100:.0f}%)",
                    f"{pos_n:,} ({pos_n/tot_n*100:.0f}%)",
                    f"{tot_n:,}",
                ])
            ps_tbl = Table(ps_rows, colWidths=[28 * mm, 36 * mm, 36 * mm, 36 * mm, 22 * mm])
            ps_tbl.setStyle(_tbl_style(C_PURPLE))
            story.append(ps_tbl)

        if org_cnt == 0 and bot_cnt == 0:
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph(
                "분석 기간 중 조직적 공격 및 봇 활동 패턴이 탐지되지 않았습니다.",
                ST("NoneNote", fontName=KR, fontSize=9, leading=14, color=C_DGRAY)
            ))

        story.append(PageBreak())

        # ════════════════════════════════════════════════════════════════
        # 6. 미해결 위협 상세 목록 (Top 10)
        # ════════════════════════════════════════════════════════════════
        story += _section_hdr("5. 미해결 위협 상세 (위험도 순 Top 10)",
                               "오탐(False Positive) 제외 · 리스크 스코어 기준 내림차순")

        unresolved = data.get("unresolved_threats", [])
        if unresolved:
            for idx, th in enumerate(unresolved, 1):
                sev = th.get("severity", "")
                sc_color = SEV_COLOR.get(sev, C_DGRAY)
                sev_txt = SEV_LABEL.get(sev, sev)
                plat = PLAT_KO.get(th.get("platform", ""), _esc(th.get("platform", "")))
                account = _esc(th.get("source_account") or "—")
                preview = _clean(th.get("content_preview") or "", 200)
                risk = th.get("risk_score") or 0
                conf = th.get("confidence") or 0.0
                bot_p = th.get("bot_probability")
                is_org = th.get("is_organized")
                emotion_txt = _esc(th.get("emotion") or "—")
                url = _esc((th.get("source_url") or "")[:120])
                detected = (th.get("detected_at") or "")[:10]
                ai_sugg = _clean(th.get("ai_response_suggestion") or "", 300)

                # 위협 카드 (KeepTogether로 페이지 분리 방지)
                card_items = [
                    Table(
                        [[
                            Paragraph(f"{idx}. [{plat}] {sev_txt}",
                                      ST(f"TH{idx}Hdr", fontName=KR_BOLD, fontSize=10,
                                         color=sc_color)),
                            Paragraph(f"리스크: {risk}점  |  신뢰도: {conf*100:.0f}%",
                                      ST(f"TH{idx}Score", fontName=KR, fontSize=9,
                                         color=C_DGRAY, alignment=2)),
                        ]],
                        colWidths=[110 * mm, 48 * mm],
                    ),
                ]
                card_items[0].setStyle(TableStyle([
                    ("BACKGROUND",    (0, 0), (-1, -1), C_BLUE_L),
                    ("TOPPADDING",    (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
                    ("BOX",           (0, 0), (-1, -1), 0, C_WHITE),
                    ("LINEABOVE",     (0, 0), (-1, 0), 2.5, sc_color),
                ]))

                detail_rows = [["계정", account, "탐지일", _esc(detected)]]
                flags = []
                if bot_p is not None and bot_p >= 0.5:
                    flags.append(f"봇 의심 ({bot_p*100:.0f}%)")
                if is_org:
                    flags.append("조직적 공격")
                detail_rows.append(["감정", emotion_txt, "특이사항", _esc(", ".join(flags) if flags else "—")])

                dtl_tbl = Table(detail_rows, colWidths=[14 * mm, 72 * mm, 14 * mm, 58 * mm])
                dtl_tbl.setStyle(TableStyle([
                    ("FONTNAME",      (0, 0), (-1, -1), KR),
                    ("FONTNAME",      (0, 0), (0, -1), KR_BOLD),
                    ("FONTNAME",      (2, 0), (2, -1), KR_BOLD),
                    ("FONTSIZE",      (0, 0), (-1, -1), 8),
                    ("GRID",          (0, 0), (-1, -1), 0.3, C_LGRAY),
                    ("TOPPADDING",    (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 5),
                    ("BACKGROUND",    (0, 0), (-1, -1), C_WHITE),
                    ("ROWBACKGROUNDS",(0, 0), (-1, -1), [C_GRAY, C_WHITE]),
                ]))

                card = [
                    card_items[0],
                    dtl_tbl,
                    Paragraph(preview,
                              ST(f"TH{idx}Pre", fontName=KR, fontSize=9, leading=14,
                                 leftIndent=4, rightIndent=4,
                                 backColor=C_WHITE, borderPad=4,
                                 borderWidth=0.3, borderColor=C_LGRAY)),
                ]
                if url:
                    card.append(Paragraph(
                        f"URL: {url}",
                        ST(f"TH{idx}Url", fontName=KR, fontSize=8, leading=12, color=C_DGRAY,
                           leftIndent=4)
                    ))
                if ai_sugg:
                    card.append(Paragraph(
                        f"AI 대응 권고: {ai_sugg}",
                        ST(f"TH{idx}AI", fontName=KR, fontSize=8, leading=13,
                           backColor=colors.HexColor("#f0f7ff"), leftIndent=4,
                           borderPad=4, borderWidth=0, borderLeftWidth=2, borderColor=C_BLUE)
                    ))
                card.append(Spacer(1, 4 * mm))
                story.append(KeepTogether(card))
        else:
            story.append(Paragraph("해당 기간 미해결 위협이 없습니다.", ST_BODY))

        story.append(PageBreak())

        # ════════════════════════════════════════════════════════════════
        # 7. 조치 완료 내역
        # ════════════════════════════════════════════════════════════════
        story += _section_hdr("6. 조치 완료 내역",
                               "실제 위협으로 확인된 후 해결 처리된 건")

        resolved = data.get("resolved_threats", [])
        if resolved:
            res_rows = [["번호", "플랫폼", "심각도", "위협 유형", "조치 방법", "처리일"]]
            for i, t in enumerate(resolved, 1):
                res_rows.append([
                    str(i),
                    PLAT_KO.get(t.get("platform", ""), _esc(t.get("platform", ""))),
                    _esc(SEV_LABEL.get(t.get("severity", ""), t.get("severity", "—"))),
                    _clean(t.get("threat_type") or "—", 25),
                    _clean(t.get("resolution_method") or "기타", 30),
                    _esc((t.get("updated_at") or "")[:10]),
                ])
            res_tbl = Table(res_rows, colWidths=[8 * mm, 20 * mm, 22 * mm, 34 * mm, 38 * mm, 20 * mm])
            res_tbl.setStyle(_tbl_style(C_GREEN))
            story.append(res_tbl)

            # 메모가 있는 건 상세 표시
            notes = [(i+1, t) for i, t in enumerate(resolved) if t.get("note")]
            if notes:
                story.append(Spacer(1, 3 * mm))
                story.append(Paragraph("■ 조치 메모", ST_H3))
                for num, t in notes:
                    story.append(Paragraph(
                        f"#{num} [{_esc(t.get('platform',''))}] {_clean(t.get('note',''), 200)}",
                        ST(f"ResNote{num}", fontName=KR, fontSize=9, leading=14,
                           leftIndent=6, borderPad=4,
                           borderWidth=0, borderLeftWidth=2, borderColor=C_GREEN)
                    ))
                    story.append(Spacer(1, 1 * mm))
        else:
            story.append(Paragraph(
                "해당 기간 조치 완료된 실제 위협이 없습니다.",
                ST_BODY
            ))

        story.append(Spacer(1, 5 * mm))

        # ════════════════════════════════════════════════════════════════
        # 8. 모니터링 현황
        # ════════════════════════════════════════════════════════════════
        story += _section_hdr("7. 모니터링 현황")

        keywords = data.get("keywords", [])
        by_plat = data.get("by_platform", {})
        active_plats = sorted(by_plat.keys())

        mon_rows = [
            ["모니터링 키워드", ", ".join(_esc(k) for k in keywords) if keywords else "등록된 키워드 없음"],
            ["수집 플랫폼", ", ".join(PLAT_KO.get(p, p) for p in active_plats) if active_plats else "—"],
            ["총 수집 건수", f"{s['total_threats']:,}건 (오탐 포함 전체 수집량 기준)"],
            ["분석 엔진", "L1 키워드 필터 → L2 KNU 감성 사전 + Gemini AI → L3 Claude Haiku 심층 분석"],
        ]
        mon_tbl = Table(mon_rows, colWidths=[36 * mm, 122 * mm])
        mon_tbl.setStyle(TableStyle([
            ("FONTNAME",      (0, 0), (-1, -1), KR),
            ("FONTNAME",      (0, 0), (0, -1), KR_BOLD),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("GRID",          (0, 0), (-1, -1), 0.4, C_LGRAY),
            ("ROWBACKGROUNDS",(0, 0), (-1, -1), [C_GRAY, C_WHITE]),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 7),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(mon_tbl)
        story.append(Spacer(1, 5 * mm))

        # ════════════════════════════════════════════════════════════════
        # 9. 권고사항
        # ════════════════════════════════════════════════════════════════
        story += _section_hdr("8. 대응 권고사항")

        # 심각도 기반 고정 권고
        rec_items = []
        if crit_cnt:
            rec_items.append(("긴급 대응 필요",
                              f"위험(Critical) 위협 {crit_cnt}건이 탐지되었습니다. "
                              "법적 대응 검토, 공식 입장 발표, 내부 에스컬레이션을 즉시 진행하십시오.", C_RED))
        if high_cnt:
            rec_items.append(("고위험 위협 모니터링 강화",
                              f"높음(High) 위협 {high_cnt}건에 대해 24시간 집중 모니터링과 "
                              "담당자 배정이 필요합니다.", C_AMBER))
        if org_cnt:
            rec_items.append(("조직적 공격 대응",
                              f"조직적 공격 패턴 {org_cnt}건 탐지. SNS 플랫폼 신고, "
                              "법무팀 협의, 미디어 모니터링을 병행하십시오.", C_RED))
        if bot_cnt:
            rec_items.append(("봇 계정 신고",
                              f"봇 의심 계정 {bot_cnt}건을 각 플랫폼에 신고하고 "
                              "관련 콘텐츠 삭제 요청을 진행하십시오.", C_AMBER))
        neg_ratio = by_senti.get("negative", 0) / senti_total
        if neg_ratio > 0.3:
            rec_items.append(("부정 여론 관리",
                              f"부정 감성 비율이 {neg_ratio*100:.1f}%로 높습니다. "
                              "고객 소통 강화, 긍정 콘텐츠 생산, PR 활동을 검토하십시오.", C_PURPLE))
        if not rec_items:
            rec_items.append(("정기 모니터링 유지",
                              "현재 심각한 위협이 없습니다. 주기적 모니터링을 지속하고 "
                              "이상 징후 발생 시 즉시 대응 체계를 유지하십시오.", C_GREEN))

        for i, (title, desc, color) in enumerate(rec_items):
            rec_hdr_tbl = Table(
                [[Paragraph(f"  {i+1}. {_esc(title)}",
                            ST(f"RecT{i}", fontName=KR_BOLD, fontSize=10, color=C_WHITE))]],
                colWidths=[PAGE_W - 30 * mm],
            )
            rec_hdr_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), color),
                ("TOPPADDING",    (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ]))
            story.append(KeepTogether([
                rec_hdr_tbl,
                Paragraph(_esc(desc),
                          ST(f"RecD{i}", fontName=KR, fontSize=9, leading=15,
                             leftIndent=6, rightIndent=6, borderPad=6,
                             borderWidth=0, borderLeftWidth=3, borderColor=color,
                             backColor=colors.HexColor("#f8f9fa"))),
                Spacer(1, 3 * mm),
            ]))

        # AI 권고 (DB에 ai_response_suggestion 있는 경우)
        ai_suggestions = data.get("ai_suggestions", [])
        if ai_suggestions:
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph("■ AI 분석 기반 대응 제안", ST_H3))
            for i, sg in enumerate(ai_suggestions):
                plat = PLAT_KO.get(sg.get("platform", ""), _esc(sg.get("platform", "")))
                sev = _esc(SEV_LABEL.get(sg.get("severity", ""), sg.get("severity", "")))
                sugg_text = _clean(sg.get("suggestion") or "", 350)
                story.append(Paragraph(
                    f"[{plat}] {sev} — {sugg_text}",
                    ST(f"AISugg{i}", fontName=KR, fontSize=9, leading=14,
                       leftIndent=6, borderPad=5,
                       borderWidth=0, borderLeftWidth=2, borderColor=C_BLUE,
                       backColor=colors.HexColor("#f0f7ff"))
                ))
                story.append(Spacer(1, 2 * mm))

        # 최종 푸터 라인
        story.append(Spacer(1, 8 * mm))
        story.append(HRFlowable(width="100%", thickness=0.8, color=C_NAVY))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(
            f"SAYbrand AI 브랜드 보호 서비스  |  보고서 생성: {gen_date}  |  "
            "본 문서는 자동 생성된 기밀 보고서입니다.",
            ST("FinalFoot", fontName=KR, fontSize=8, leading=12,
               color=C_DGRAY, alignment=1)
        ))

        doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
        return buf.getvalue()

    except ImportError:
        logger.warning("reportlab 미설치 [MOCK]")
        return (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 595 842]/Parent 2 0 R"
            b"/Contents 4 0 R/Resources<<>>>>endobj\n"
            + f"4 0 obj<</Length 30>>stream\nBT /F1 12 Tf 100 700 Td"
              f" (SAYbrand {data['period']}) Tj ET\nendstream\nendobj\n"
              f"xref\n0 5\n0000000000 65535 f\n"
              f"trailer<</Size 5/Root 1 0 R>>\nstartxref\n0\n%%EOF\n".encode()
        )
