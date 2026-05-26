"""리포트 생성 서비스 — 일간/주간 위협 요약 + PDF"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.orm import Threat

logger = logging.getLogger(__name__)


async def generate_report(
    user_id: int,
    period: str,
    db: AsyncSession,
    org_id: int | None = None,
) -> dict:
    """
    period: "daily" (24시간) | "weekly" (7일)
    org_id: 조직 기준 필터링. None이면 user_id 기준.
    """
    now = datetime.now(timezone.utc)
    days = 1 if period == "daily" else 7
    since = now - timedelta(days=days)
    period_label = f"{since.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}"

    def _scope(q):
        if org_id is not None:
            return q.where(Threat.org_id == org_id, Threat.detected_at >= since)
        return q.where(Threat.user_id == user_id, Threat.detected_at >= since)

    total_result = await db.execute(_scope(select(func.count(Threat.id))))
    total = total_result.scalar() or 0

    # 심각도별
    sev_result = await db.execute(
        _scope(select(Threat.severity, func.count(Threat.id))).group_by(Threat.severity)
    )
    by_severity = {row[0]: row[1] for row in sev_result}

    # 플랫폼별
    plat_result = await db.execute(
        _scope(select(Threat.platform, func.count(Threat.id))).group_by(Threat.platform)
    )
    by_platform = {row[0]: row[1] for row in plat_result}

    # 해결 완료
    resolved_result = await db.execute(
        _scope(select(func.count(Threat.id))).where(Threat.status == "resolved")
    )
    resolved_count = resolved_result.scalar() or 0

    # TOP 5 위협
    top_result = await db.execute(
        _scope(select(Threat)).order_by(Threat.risk_score.desc()).limit(5)
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
        for t in top_result.scalars().all()
    ]

    return {
        "period": period_label,
        "total_threats": total,
        "by_severity": by_severity,
        "by_platform": by_platform,
        "top_threats": top_threats,
        "resolved_count": resolved_count,
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
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        story = []

        title_style = styles["Title"]
        story.append(Paragraph("SAYbrand 위협 분석 리포트", title_style))
        story.append(Paragraph(f"기간: {data['period']}", styles["Normal"]))
        story.append(Spacer(1, 0.5*cm))

        summary_data = [
            ["총 위협", "Critical", "High", "Medium", "Low", "해결 완료"],
            [
                str(data["total_threats"]),
                str(data["by_severity"].get("critical", 0)),
                str(data["by_severity"].get("high", 0)),
                str(data["by_severity"].get("medium", 0)),
                str(data["by_severity"].get("low", 0)),
                str(data["resolved_count"]),
            ],
        ]
        tbl = Table(summary_data, hAlign="LEFT")
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a6ef8")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.5*cm))

        if data["top_threats"]:
            story.append(Paragraph("Top 위협 목록", styles["Heading2"]))
            threat_rows = [["등급", "플랫폼", "계정", "리스크", "상태"]]
            for t in data["top_threats"]:
                threat_rows.append([
                    t["severity"].upper(),
                    t["platform"],
                    (t["source_account"] or "")[:30],
                    str(t["risk_score"]),
                    t["status"],
                ])
            ttbl = Table(threat_rows, hAlign="LEFT", colWidths=[2*cm, 2.5*cm, 5*cm, 2*cm, 2.5*cm])
            ttbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a6ef8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ]))
            story.append(ttbl)

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
