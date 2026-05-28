import hashlib
import hmac
import json
import logging

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


@router.get("/checkout")
async def checkout(
    plan: str = "starter",
    current_user: dict = Depends(get_current_user),
):
    """
    Polar Checkout Link(정적 URL)으로 직접 리다이렉트.
    Vercel Python 서버리스는 외부 HTTP 불가 → API 호출 없이 미리 생성된 링크 사용.
    POLAR_CHECKOUT_URL_STARTER / POLAR_CHECKOUT_URL_PRO 환경변수에 설정.
    """
    if plan == "pro":
        checkout_url = settings.polar_checkout_url_pro
    else:
        checkout_url = settings.polar_checkout_url_starter

    logger.info("[BILLING] checkout 요청: plan=%s url=%s email=%s",
                plan, checkout_url, current_user.get("email"))

    if not checkout_url:
        logger.error("[BILLING] 환경변수 누락: POLAR_CHECKOUT_URL_%s", plan.upper())
        raise HTTPException(
            status_code=503,
            detail="결제 서비스가 설정되지 않았습니다. 관리자에게 문의하세요.",
        )

    return RedirectResponse(checkout_url)


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
