"""Slack Block Kit 위협 알림 및 일일 리포트 발송"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_SEVERITY_EMOJI = {
    "critical": ":red_circle:",
    "high":     ":orange_circle:",
    "medium":   ":yellow_circle:",
    "low":      ":white_circle:",
}


async def send_slack_threat_alert(webhook_url: str, threat: dict) -> bool:
    if not webhook_url:
        return False

    severity = threat.get("severity", "low")
    emoji = _SEVERITY_EMOJI.get(severity, ":white_circle:")
    platform = threat.get("platform", "unknown")
    account = threat.get("source_account", "")
    preview = (threat.get("content_preview") or "")[:200]

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji} 브랜드 위협 감지"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*등급:*\n{severity.upper()}"},
                {"type": "mrkdwn", "text": f"*플랫폼:*\n{platform}"},
                {"type": "mrkdwn", "text": f"*계정:*\n{account or '-'}"},
                {"type": "mrkdwn", "text": f"*위협 유형:*\n{threat.get('threat_type', '-')}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*내용 미리보기:*\n{preview}"},
        },
    ]

    if threat.get("ai_analysis"):
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*AI 분석:*\n{threat['ai_analysis'][:300]}"},
        })

    if threat.get("ai_response_suggestion"):
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*대처 방안:*\n{threat['ai_response_suggestion'][:300]}"},
        })

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json={"blocks": blocks})
        return resp.status_code == 200
    except Exception as e:
        logger.warning("Slack 알림 발송 실패: %s", e)
        return False


async def send_slack_daily_report(webhook_url: str, report: dict) -> bool:
    if not webhook_url:
        return False

    total = report.get("total_threats", 0)
    by_sev = report.get("by_severity", {})

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": ":bar_chart: SAYbrand 일일 리포트"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*총 위협:*\n{total}건"},
                {"type": "mrkdwn", "text": f"*Critical:*\n{by_sev.get('critical', 0)}건"},
                {"type": "mrkdwn", "text": f"*High:*\n{by_sev.get('high', 0)}건"},
                {"type": "mrkdwn", "text": f"*Medium/Low:*\n{by_sev.get('medium', 0) + by_sev.get('low', 0)}건"},
            ],
        },
    ]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json={"blocks": blocks})
        return resp.status_code == 200
    except Exception as e:
        logger.warning("Slack 일일 리포트 발송 실패: %s", e)
        return False
