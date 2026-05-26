"""아웃바운드 웹훅 엔드포인트 관리"""
from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.middleware.auth import require_login
from backend.models.orm import OutboundWebhook

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class WebhookCreate(BaseModel):
    url: str
    description: str = ""
    events: list[str] = ["threat.critical", "threat.high"]


class WebhookResponse(BaseModel):
    id: int
    url: str
    description: str
    events: list[str]
    secret: str
    active: bool

    class Config:
        from_attributes = True


def _wh_out(wh: OutboundWebhook) -> dict:
    import json as _json
    return {
        "id": wh.id, "url": wh.url, "description": wh.description,
        "events": _json.loads(wh.events or "[]"),
        "secret": wh.secret, "active": wh.active,
    }


@router.get("", response_model=list[WebhookResponse])
async def list_webhooks(
    user=Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OutboundWebhook).where(OutboundWebhook.user_id == user.id)
    )
    return [_wh_out(wh) for wh in result.scalars().all()]


@router.post("", response_model=WebhookResponse, status_code=201)
async def create_webhook(
    body: WebhookCreate,
    user=Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    import json
    wh = OutboundWebhook(
        user_id=user.id,
        url=body.url,
        description=body.description,
        events=json.dumps(body.events),
        secret=secrets.token_hex(32),
        active=True,
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    return _wh_out(wh)


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: int,
    user=Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OutboundWebhook).where(
            OutboundWebhook.id == webhook_id,
            OutboundWebhook.user_id == user.id,
        )
    )
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await db.delete(wh)
    await db.commit()
