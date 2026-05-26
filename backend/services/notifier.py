"""이메일 알림 서비스 — Critical/High 위협 즉시 발송, Medium 이하 일간 다이제스트"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.config import settings

logger = logging.getLogger(__name__)


def _can_send() -> bool:
    return bool(settings.smtp_user and settings.smtp_password)


async def send_alert_email(to: str, subject: str, body_html: str) -> bool:
    """
    단일 이메일을 SMTP로 발송한다.

    Returns:
        True = 발송 성공, False = 설정 없음(Mock) 또는 실패
    """
    if not _can_send():
        logger.info("[Mock] 이메일 알림 (SMTP 설정 없음): %s → %s", subject, to)
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.alert_from_email
        msg["To"] = to
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.alert_from_email, to, msg.as_string())

        logger.info("이메일 발송 성공: %s → %s", subject, to)
        return True
    except Exception as e:
        logger.warning("이메일 발송 실패: %s", e)
        return False


async def notify_threat(user_email: str, threat, profile=None) -> None:
    """
    위협 심각도에 따라 알림 발송.
    - critical/high: 즉시 발송
    - medium 이하: 로그만 (일간 다이제스트 예정)

    profile(ProfileLoader.LoadedProfile)이 있으면 임직원 관련 위협의 알림 강도를 상향한다.
    """
    effective_severity = threat.severity

    # 임직원 관련 위협 → 알림 강도 상향
    if profile and threat.module == "C":
        content_preview = threat.content_preview or ""
        for exec_info in profile.executives:
            if exec_info["name"] in content_preview:
                priority = exec_info.get("priority", 2)
                if priority == 1:          # CEO → 강제 critical
                    effective_severity = "critical"
                elif priority == 2 and effective_severity == "medium":
                    effective_severity = "high"   # 임원 → medium → high 상향
                break

    if effective_severity not in ("critical", "high"):
        logger.debug("Medium 이하 위협 — 일간 다이제스트 포함 예정: id=%s", threat.id)
        return

    level_label = {"critical": "긴급", "high": "주의"}.get(effective_severity, "알림")
    subject = f"[SAYbrand {level_label}] {threat.platform} 위협 탐지 — {threat.source_account}"

    body = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto;">
      <h2 style="color:#{'dc2626' if threat.severity == 'critical' else 'ea580c'};">
        [{level_label}] 브랜드 위협 탐지
      </h2>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <tr><td style="padding:6px 0;color:#6b7280;width:100px;">심각도</td>
            <td style="padding:6px 0;font-weight:700;">{threat.severity.upper()}</td></tr>
        <tr><td style="padding:6px 0;color:#6b7280;">플랫폼</td>
            <td style="padding:6px 0;">{threat.platform}</td></tr>
        <tr><td style="padding:6px 0;color:#6b7280;">계정</td>
            <td style="padding:6px 0;font-family:monospace;">{threat.source_account}</td></tr>
        <tr><td style="padding:6px 0;color:#6b7280;">리스크</td>
            <td style="padding:6px 0;font-weight:700;">{threat.risk_score}/100</td></tr>
      </table>
      <div style="margin-top:12px;padding:12px;background:#f9fafb;border-radius:6px;font-size:13px;line-height:1.6;">
        {threat.content_preview[:300]}
      </div>
      {"<div style='margin-top:12px;'><a href='" + threat.source_url + "' style='color:#1a6ef8;'>원본 게시글 보기</a></div>" if threat.source_url else ""}
      <hr style="margin:20px 0;border:none;border-top:1px solid #e5e7eb;" />
      <p style="font-size:11px;color:#9ca3af;">SAYbrand 브랜드 리스크 모니터링 서비스</p>
    </div>
    """

    await send_alert_email(user_email, subject, body)
