import hashlib
import hmac
import json
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.database import get_db
from backend.middleware.auth import get_current_user
from backend.models.orm import User

router = APIRouter(prefix="/billing", tags=["billing"])
logger = logging.getLogger(__name__)

_POLAR_API = "https://api.polar.sh/v1"


@router.get("/checkout")
async def checkout(
    request: Request,
    plan: str = "starter",
    current_user: dict = Depends(get_current_user),
):
    if plan == "pro":
        product_id = settings.polar_product_id_pro
    else:
        product_id = settings.polar_product_id_starter

    logger.info("[BILLING] checkout 요청: plan=%s product_id=%s email=%s",
                plan, product_id, current_user.get("email"))

    if not settings.polar_access_token or not product_id:
        logger.error("[BILLING] 환경변수 누락: token=%s product_id=%s",
                     bool(settings.polar_access_token), bool(product_id))
        raise HTTPException(status_code=503, detail="결제 서비스가 설정되지 않았습니다")

    payload = {
        "product_id": product_id,
        "customer_email": current_user["email"],
        "success_url": str(request.base_url).rstrip("/") + "/dashboard",
    }
    logger.info("[BILLING] Polar API 호출: POST %s/checkouts payload=%s", _POLAR_API, payload)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{_POLAR_API}/checkouts",
                headers={"Authorization": f"Bearer {settings.polar_access_token}",
                         "Content-Type": "application/json"},
                json=payload,
            )
        logger.info("[BILLING] Polar 응답: status=%s body=%s", resp.status_code, resp.text[:500])

        if resp.status_code not in (200, 201):
            try:
                err_body = resp.json()
                detail = err_body.get("detail") or err_body.get("message") or str(err_body)
            except Exception:
                detail = resp.text[:200] or "결제 페이지 생성 실패"
            logger.error("[BILLING ERROR] Polar %s: %s", resp.status_code, detail)
            raise HTTPException(status_code=502, detail=f"Polar API {resp.status_code}: {detail}")

        body = resp.json()
        checkout_url = body.get("url") or body.get("checkout_url") or body.get("hosted_url")
        if not checkout_url:
            logger.error("[BILLING ERROR] checkout URL 없음. 응답 keys: %s", list(body.keys()))
            raise HTTPException(status_code=502, detail=f"결제 URL 없음. 응답: {list(body.keys())}")

        logger.info("[BILLING] 리다이렉트: %s", checkout_url)
        return RedirectResponse(checkout_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[BILLING ERROR] %s: %s", type(e).__name__, e, exc_info=True)
        raise HTTPException(status_code=502, detail=f"결제 서비스 연결 실패: {type(e).__name__}: {e}")


@router.post("/webhook")
async def webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()

    if settings.polar_webhook_secret:
        webhook_id = request.headers.get("webhook-id", "")
        timestamp = request.headers.get("webhook-timestamp", "")
        sig_header = request.headers.get("webhook-signature", "")

        msg = f"{webhook_id}.{timestamp}.{body.decode()}"
        expected = hmac.new(
            settings.polar_webhook_secret.encode(),
            msg.encode(),
            hashlib.sha256,
        ).hexdigest()

        valid = any(
            part.split("=", 1)[1] == expected
            for part in sig_header.split(" ")
            if "=" in part
        )
        if not valid:
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event_type = event.get("type", "")
    data = event.get("data", {})

    customer_email = (
        data.get("customer", {}).get("email") or data.get("customer_email")
    )
    if not customer_email:
        return {"ok": True}

    result = await db.execute(select(User).where(User.email == customer_email))
    user = result.scalar_one_or_none()
    if not user:
        return {"ok": True}

    from backend.models.orm import Organization, OrganizationMember
    from backend.services.org_service import handle_subscription_cancelled

    org_result = await db.execute(
        select(Organization).where(Organization.owner_user_id == user.id).limit(1)
    )
    org = org_result.scalar_one_or_none()

    def _resolve_tier(product_id: str) -> str:
        if product_id and product_id == settings.polar_product_id_pro:
            return "pro"
        if product_id and product_id == settings.polar_product_id_starter:
            return "starter"
        return "starter"

    if event_type == "subscription.created":
        product_id = data.get("product_id") or data.get("product", {}).get("id", "")
        new_tier = _resolve_tier(product_id)
        user.subscription_status = "active"
        user.polar_customer_id = data.get("customer_id")
        user.subscription_tier = new_tier
        if org:
            org.subscription_status = "active"
            org.subscription_tier = new_tier
            org.polar_subscription_id = data.get("id")
    elif event_type == "subscription.cancelled":
        user.subscription_status = "cancelled"
        if org:
            await handle_subscription_cancelled(org.id, db)
            return {"ok": True}
    elif event_type == "subscription.updated":
        product_id = data.get("product_id") or data.get("product", {}).get("id", "")
        new_tier = _resolve_tier(product_id)
        user.subscription_tier = new_tier
        if org:
            org.subscription_tier = new_tier

    await db.commit()
    return {"ok": True}
