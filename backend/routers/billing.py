import base64
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
from backend.models.orm import Organization, User

router = APIRouter(prefix="/billing", tags=["billing"])
logger = logging.getLogger(__name__)


def _verify_svix_signature(
    secret: str, webhook_id: str, timestamp: str, body: bytes, sig_header: str
) -> bool:
    """Polar(Svix) 웹훅 서명 검증.
    secret: whsec_<base64> 형식. 서명 헤더 형식: 'v1,<base64_sig>'
    """
    try:
        raw = secret[6:] if secret.startswith("whsec_") else secret
        secret_bytes = base64.b64decode(raw)
        signed_content = f"{webhook_id}.{timestamp}.{body.decode()}"
        expected = base64.b64encode(
            hmac.new(secret_bytes, signed_content.encode(), hashlib.sha256).digest()
        ).decode()
        # 헤더에 공백으로 구분된 여러 서명이 올 수 있음: "v1,<sig1> v1,<sig2>"
        for part in sig_header.split(" "):
            if "," in part:
                version, sig = part.split(",", 1)
                if version == "v1" and sig == expected:
                    return True
        return False
    except Exception as e:
        print(f"[BILLING] 서명 검증 오류: {e}")
        return False


def _resolve_tier(product_id: str) -> str:
    if product_id and product_id == settings.polar_product_id_pro:
        return "pro"
    if product_id and product_id == settings.polar_product_id_starter:
        return "starter"
    # product_id 불일치 시 — 일단 starter로 처리 (무료 → 유료)
    return "starter"


async def _apply_subscription(
    user: User,
    org: Organization | None,
    new_tier: str,
    customer_id: str | None,
    subscription_id: str | None,
    db: AsyncSession,
) -> None:
    """구독 티어 반영 공통 로직"""
    user.subscription_status = "active"
    user.subscription_tier = new_tier
    if customer_id:
        user.polar_customer_id = customer_id
    if org:
        org.subscription_status = "active"
        org.subscription_tier = new_tier
        if subscription_id:
            org.polar_subscription_id = subscription_id
    await db.commit()
    print(f"[BILLING] 구독 반영: user={user.email} tier={new_tier}")


@router.get("/checkout")
async def checkout(
    plan: str = "starter",
    user=Depends(get_current_user),
):
    urls = {
        "starter": settings.polar_checkout_url_starter,
        "pro": settings.polar_checkout_url_pro,
    }
    url = urls.get(plan, urls["starter"])
    if not url:
        raise HTTPException(404, "결제 링크가 설정되지 않았습니다.")
    return RedirectResponse(url)


@router.get("/success")
async def billing_success(
    request: Request,
    checkout_id: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Polar 결제 완료 후 리다이렉트. checkout_id로 즉시 구독 반영."""
    print(f"[BILLING] 결제 성공 콜백: checkout_id={checkout_id}")

    if checkout_id and settings.polar_access_token:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{settings.polar_server_url}/v1/checkouts/custom/{checkout_id}",
                    headers={"Authorization": f"Bearer {settings.polar_access_token}"},
                )
            print(f"[BILLING] Polar checkout API 응답: {resp.status_code}")
            if resp.status_code == 200:
                checkout_data = resp.json()
                status = checkout_data.get("status", "")
                print(f"[BILLING] checkout status={status}")

                if status == "succeeded":
                    customer_email = (
                        checkout_data.get("customer_email")
                        or (checkout_data.get("customer") or {}).get("email", "")
                    )
                    if customer_email:
                        result = await db.execute(
                            select(User).where(User.email == customer_email)
                        )
                        user = result.scalar_one_or_none()
                        if user:
                            product_id = checkout_data.get("product_id") or (
                                checkout_data.get("product") or {}
                            ).get("id", "")
                            new_tier = _resolve_tier(product_id)

                            org_result = await db.execute(
                                select(Organization)
                                .where(Organization.owner_user_id == user.id)
                                .limit(1)
                            )
                            org = org_result.scalar_one_or_none()

                            await _apply_subscription(
                                user, org, new_tier,
                                customer_id=checkout_data.get("customer_id"),
                                subscription_id=None,
                                db=db,
                            )
                        else:
                            print(f"[BILLING] 이메일 {customer_email}에 해당 유저 없음")
                    else:
                        print("[BILLING] checkout에 customer_email 없음")
        except Exception as e:
            print(f"[BILLING] 결제 성공 처리 오류: {e}")

    return RedirectResponse("/dashboard")


@router.get("/me")
async def billing_me(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """현재 로그인 유저의 구독 상태 조회"""
    result = await db.execute(select(User).where(User.id == user.id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(404, "User not found")
    return {
        "subscription_status": db_user.subscription_status,
        "subscription_tier": db_user.subscription_tier or "free",
    }


@router.post("/webhook")
async def webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()

    # 서명 검증 (POLAR_WEBHOOK_SECRET 설정된 경우만)
    if settings.polar_webhook_secret:
        webhook_id = request.headers.get("webhook-id", "")
        timestamp = request.headers.get("webhook-timestamp", "")
        sig_header = request.headers.get("webhook-signature", "")

        if not _verify_svix_signature(
            settings.polar_webhook_secret, webhook_id, timestamp, body, sig_header
        ):
            print(f"[BILLING] 웹훅 서명 불일치 — id={webhook_id}")
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event_type = event.get("type", "")
    data = event.get("data", {})
    print(f"[BILLING] 웹훅 수신: type={event_type}")

    # American/British spelling 통일
    if event_type == "subscription.canceled":
        event_type = "subscription.cancelled"

    # 이메일 추출 (이벤트 유형별로 위치가 다를 수 있음)
    customer = data.get("customer") or {}
    customer_email = (
        customer.get("email")
        or data.get("customer_email")
        or ""
    )

    if not customer_email:
        print(f"[BILLING] 이메일 없음 (type={event_type})")
        return {"ok": True}

    result = await db.execute(select(User).where(User.email == customer_email))
    user = result.scalar_one_or_none()
    if not user:
        print(f"[BILLING] 유저 없음: {customer_email}")
        return {"ok": True}

    from backend.services.org_service import handle_subscription_cancelled

    org_result = await db.execute(
        select(Organization).where(Organization.owner_user_id == user.id).limit(1)
    )
    org = org_result.scalar_one_or_none()

    def _get_product_id() -> str:
        return data.get("product_id") or (data.get("product") or {}).get("id", "")

    if event_type == "checkout.updated" and data.get("status") == "succeeded":
        # 결제 완료 — 구독 생성 전에 발생하는 이벤트
        new_tier = _resolve_tier(_get_product_id())
        await _apply_subscription(
            user, org, new_tier,
            customer_id=data.get("customer_id"),
            subscription_id=None,
            db=db,
        )

    elif event_type in ("subscription.created", "subscription.active"):
        new_tier = _resolve_tier(_get_product_id())
        await _apply_subscription(
            user, org, new_tier,
            customer_id=data.get("customer_id"),
            subscription_id=data.get("id"),
            db=db,
        )

    elif event_type == "subscription.updated":
        new_tier = _resolve_tier(_get_product_id())
        user.subscription_tier = new_tier
        if org:
            org.subscription_tier = new_tier
        await db.commit()
        print(f"[BILLING] subscription.updated → {customer_email}: {new_tier}")

    elif event_type == "subscription.cancelled":
        user.subscription_status = "cancelled"
        if org:
            await handle_subscription_cancelled(org.id, db)
        else:
            await db.commit()
        print(f"[BILLING] 구독 취소: {customer_email}")

    else:
        print(f"[BILLING] 미처리 이벤트: {event_type}")

    return {"ok": True}
