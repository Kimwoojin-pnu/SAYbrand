"""아웃바운드 웹훅 발송 — HMAC-SHA256 서명 포함"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time

import httpx

logger = logging.getLogger(__name__)


async def send_webhook(
    url: str,
    payload: dict,
    secret: str = "",
    timeout: int = 10,
) -> bool:
    body = json.dumps(payload, ensure_ascii=False)
    headers: dict[str, str] = {"Content-Type": "application/json"}

    if secret:
        sig = hmac.new(
            secret.encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()
        headers["X-SAYbrand-Signature"] = f"sha256={sig}"
        headers["X-SAYbrand-Timestamp"] = str(int(time.time()))

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, content=body, headers=headers)
        if resp.status_code >= 400:
            logger.warning("웹훅 응답 오류 %s → %s", url, resp.status_code)
            return False
        return True
    except Exception as e:
        logger.warning("웹훅 발송 실패 %s: %s", url, e)
        return False
