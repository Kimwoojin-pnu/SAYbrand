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

from backend.models.orm import Threat

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

    # 이전 기간 대비 (trend용 단순 집계)
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
        "summary": {
            "total_threats": total,
            "unresolved_count": unresolved_count,
            "resolved_count": resolved_count,
            "negative_mentions": negative_count,
            "brand_score": round(brand_score, 1),
            "false_positive_count": false_positive_count,
            "real_resolved_count": real_resolved_count,
        },
        # 하위 호환성
        "total_threats": total,
        "by_severity": by_severity,
        "by_platform": by_platform,
        "resolved_count": resolved_count,
        "top_threats": top_threats,
        "unresolved_threats": unresolved_threats,
        "resolved_threats": resolved_threats,
        "negative_samples": negative_samples,
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
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import (
            HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        )

        # ── 한글 폰트 등록 ──────────────────────────────────────────────────────
        # 우선순위: 번들 폰트(backend/fonts/) → 시스템 폰트 → Helvetica 폴백
        _FONT_CANDIDATES = [
            (_BUNDLED_REGULAR, _BUNDLED_BOLD),                                          # 번들 (항상 존재해야 함)
            ("C:/Windows/Fonts/malgun.ttf",   "C:/Windows/Fonts/malgunbd.ttf"),        # Windows
            ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
             "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"),                   # Linux 시스템
        ]
        KR = "Helvetica"
        KR_BOLD = "Helvetica-Bold"
        _registered = pdfmetrics.getRegisteredFontNames()
        for reg_path, bold_path in _FONT_CANDIDATES:
            if not os.path.exists(reg_path):
                continue
            try:
                if "SAYKorean" not in _registered:
                    pdfmetrics.registerFont(TTFont("SAYKorean", reg_path))
                KR = "SAYKorean"
                if os.path.exists(bold_path):
                    if "SAYKoreanBold" not in _registered:
                        pdfmetrics.registerFont(TTFont("SAYKoreanBold", bold_path))
                    KR_BOLD = "SAYKoreanBold"
                else:
                    KR_BOLD = KR
                break
            except Exception as _fe:
                logger.warning("폰트 등록 실패 (%s): %s", reg_path, _fe)
                continue

        NAVY = colors.HexColor("#0c1428")
        BLUE = colors.HexColor("#1d5fa8")
        RED  = colors.HexColor("#E24B4A")
        AMBER = colors.HexColor("#BA7517")
        GRAY = colors.HexColor("#f5f6f8")

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=20*mm, rightMargin=20*mm,
                                topMargin=20*mm, bottomMargin=20*mm)

        # 한글 폰트 적용된 스타일
        base = getSampleStyleSheet()
        ST_NORMAL  = ParagraphStyle("KrNormal",  fontName=KR,      fontSize=10, leading=15)
        ST_SMALL   = ParagraphStyle("KrSmall",   fontName=KR,      fontSize=9,  leading=13, textColor=colors.HexColor("#555555"))
        ST_TITLE   = ParagraphStyle("KrTitle",   fontName=KR_BOLD, fontSize=18, leading=24, spaceAfter=4)
        ST_H2      = ParagraphStyle("KrH2",      fontName=KR_BOLD, fontSize=13, leading=18, spaceBefore=6, spaceAfter=4)
        ST_FOOTER  = ParagraphStyle("KrFooter",  fontName=KR,      fontSize=8,  leading=12, textColor=colors.grey)

        story = []

        # 헤더
        story.append(Paragraph("SAYbrand 브랜드 보호 서비스", ST_NORMAL))
        story.append(Paragraph(_esc(data["label"]), ST_TITLE))
        story.append(Paragraph(
            f"기간: {_esc(data['period'])}   생성: {_esc(data['generated_at'][:10])}",
            ST_SMALL
        ))
        story.append(Spacer(1, 8*mm))

        # KPI 요약 테이블
        s = data["summary"]
        kpi_data = [
            ["항목", "수치"],
            ["총 위협 건수 (오탐 제외)", str(s["total_threats"])],
            ["미해결 위협", str(s["unresolved_count"])],
            ["해결 완료 (실제 위협)", str(s["real_resolved_count"])],
            ["부정적 언급", str(s["negative_mentions"])],
            ["오탐 처리", str(s["false_positive_count"])],
            ["브랜드 이미지 점수", f"{s['brand_score']}/100"],
        ]
        kpi_tbl = Table(kpi_data, colWidths=[110*mm, 60*mm])
        kpi_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), KR),
            ("FONTNAME", (0, 0), (-1, 0), KR_BOLD),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRAY]),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(kpi_tbl)
        story.append(Spacer(1, 8*mm))

        # 심각도별 분포
        by_s = data.get("by_severity", {})
        if any(by_s.values()):
            story.append(Paragraph("심각도별 분포", ST_H2))
            SEV_LABEL = {"critical": "위험 (Critical)", "high": "높음 (High)",
                         "medium": "중간 (Medium)", "low": "낮음 (Low)"}
            sev_rows = [["심각도", "건수"]]
            for sev in ("critical", "high", "medium", "low"):
                if by_s.get(sev, 0):
                    sev_rows.append([SEV_LABEL.get(sev, sev), str(by_s[sev])])
            if len(sev_rows) > 1:
                sev_tbl = Table(sev_rows, colWidths=[110*mm, 60*mm])
                sev_tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, -1), KR),
                    ("FONTNAME", (0, 0), (-1, 0), KR_BOLD),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRAY]),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]))
                story.append(sev_tbl)
                story.append(Spacer(1, 6*mm))

        # 미해결 위협
        unresolved = data.get("unresolved_threats", [])
        if unresolved:
            story.append(Paragraph("미해결 위협 (우선순위 순)", ST_H2))
            SEV_COLOR = {"critical": "#E24B4A", "high": "#BA7517", "medium": "#185FA5", "low": "#1D9E75"}
            for i, th in enumerate(unresolved):
                sc = SEV_COLOR.get(th.get("severity", ""), "#555555")
                preview = _clean(th.get("content_preview") or "", max_len=120)
                platform = _esc(th.get("platform") or "")
                sev_label = _esc(th.get("severity") or "")
                # 동일 ParagraphStyle 이름 충돌 방지 위해 index 포함
                story.append(Paragraph(
                    f"[{platform}] [{sev_label}] {preview}",
                    ParagraphStyle(f"ThreatRow{i}", fontName=KR, fontSize=9, leading=14,
                                   leftIndent=6, borderPad=4,
                                   borderColor=colors.HexColor(sc), borderWidth=0,
                                   borderLeftWidth=3)
                ))
                url = th.get("source_url") or ""
                if url:
                    story.append(Paragraph(
                        f"원본: {_esc(url[:100])}",
                        ST_SMALL
                    ))
                story.append(Spacer(1, 2*mm))
            story.append(Spacer(1, 4*mm))

        # 부정적 언급 샘플
        neg_samples = data.get("negative_samples", [])
        if neg_samples:
            story.append(Paragraph("부정적 언급 샘플", ST_H2))
            for i, ns in enumerate(neg_samples):
                platform = _esc(ns.get("platform") or "")
                content = _clean(ns.get("content") or "", max_len=120)
                story.append(Paragraph(
                    f"[{platform}] {content}",
                    ParagraphStyle(f"NegRow{i}", fontName=KR, fontSize=9, leading=14,
                                   leftIndent=6, textColor=colors.HexColor("#BA7517"))
                ))
                story.append(Spacer(1, 1*mm))
            story.append(Spacer(1, 4*mm))

        # 해결 완료 위협
        resolved_threats = data.get("resolved_threats", [])
        if resolved_threats:
            story.append(Paragraph("해결 완료된 위협", ST_H2))
            for t in resolved_threats:
                platform = _esc(t.get("platform") or "")
                method = _esc(t.get("resolution_method") or "기타")
                note_raw = t.get("note") or ""
                note = f" — {_clean(note_raw, 80)}" if note_raw else ""
                story.append(Paragraph(
                    f"[{platform}] 해결방법: {method}{note}",
                    ST_NORMAL
                ))
            story.append(Spacer(1, 4*mm))

        story.append(Spacer(1, 10*mm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        story.append(Paragraph(
            "SAYbrand AI 브랜드 보호 서비스  |  자동 생성 보고서",
            ST_FOOTER
        ))

        doc.build(story)
        return buf.getvalue()

    except ImportError:
        logger.warning("reportlab 미설치 — 텍스트 PDF 대체 반환 [MOCK]")
        lines = [
            b"%PDF-1.4\n",
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n",
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n",
            b"3 0 obj<</Type/Page/MediaBox[0 0 595 842]/Parent 2 0 R/Contents 4 0 R/Resources<<>>>>endobj\n",
            f"4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 100 700 Td (SAYbrand Report: {data['period']}) Tj ET\nendstream\nendobj\n".encode(),
            b"xref\n0 5\n0000000000 65535 f\n",
            b"trailer<</Size 5/Root 1 0 R>>\nstartxref\n0\n%%EOF\n",
        ]
        return b"".join(lines)
