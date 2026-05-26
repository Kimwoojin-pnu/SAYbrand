from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import settings
from backend.db.database import get_db
from backend.models.orm import (
    Alert, CustomerAlias, CustomerExecutive, CustomerProfile,
    CustomerSocialAccount, CompetitorKeyword, CompetitorMention,
    HashtagTrend, InviteCode, Keyword, Organization, OrganizationMember,
    OutboundWebhook, Threat, UsageLog, User,
)
from backend.models.schemas import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/login")
async def login(request: Request):
    return await oauth.google.authorize_redirect(request, settings.google_redirect_uri)


@router.get("/callback")
async def callback(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        return RedirectResponse("/login?error=auth_failed")

    user_info = token.get("userinfo") or {}
    email = user_info.get("email")
    if not email:
        return RedirectResponse("/login?error=no_email")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user:
        user.google_id = user_info.get("sub", user.google_id)
        user.avatar_url = user_info.get("picture", user.avatar_url)
        user.name = user_info.get("name", user.name)
    else:
        user = User(
            email=email,
            name=user_info.get("name", ""),
            google_id=user_info.get("sub"),
            avatar_url=user_info.get("picture"),
            subscription_status="free",
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    request.session["user_id"] = user.id
    request.session["user_name"] = user.name
    request.session["user_email"] = user.email
    request.session["user_avatar"] = user.avatar_url or ""
    request.session["subscription_status"] = user.subscription_status

    profile_result = await db.execute(
        select(CustomerProfile).where(CustomerProfile.user_id == user.id).limit(1)
    )
    has_profile = profile_result.scalar_one_or_none() is not None

    return RedirectResponse("/dashboard" if has_profile else "/onboarding")


@router.get("/demo-status")
async def demo_status():
    return {"demo_mode": settings.demo_mode}


@router.get("/demo-login")
async def demo_login(request: Request, db: AsyncSession = Depends(get_db)):
    if not settings.demo_mode:
        raise HTTPException(status_code=403, detail="Demo mode is disabled")
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="No seed user found")
    request.session["user_id"] = user.id
    request.session["user_name"] = user.name
    request.session["user_email"] = user.email
    request.session["user_avatar"] = user.avatar_url or ""
    request.session["subscription_status"] = user.subscription_status or "free"
    return RedirectResponse("/dashboard")


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")


@router.get("/me", response_model=UserOut)
async def me(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/account")
async def delete_account(request: Request, db: AsyncSession = Depends(get_db)):
    """계정 및 모든 관련 데이터 영구 삭제."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")

    # 1. 위협에 연결된 알림 먼저 삭제
    threat_ids = (
        await db.execute(select(Threat.id).where(Threat.user_id == user_id))
    ).scalars().all()
    if threat_ids:
        await db.execute(delete(Alert).where(Alert.threat_id.in_(threat_ids)))

    # 2. 위협
    await db.execute(delete(Threat).where(Threat.user_id == user_id))

    # 3. 키워드
    await db.execute(delete(Keyword).where(Keyword.user_id == user_id))

    # 4. 프로파일 하위 항목 → 프로파일
    profile_ids = (
        await db.execute(select(CustomerProfile.id).where(CustomerProfile.user_id == user_id))
    ).scalars().all()
    if profile_ids:
        await db.execute(delete(CustomerAlias).where(CustomerAlias.profile_id.in_(profile_ids)))
        await db.execute(delete(CustomerSocialAccount).where(CustomerSocialAccount.profile_id.in_(profile_ids)))
        await db.execute(delete(CustomerExecutive).where(CustomerExecutive.profile_id.in_(profile_ids)))
    await db.execute(delete(CustomerProfile).where(CustomerProfile.user_id == user_id))

    # 5. 기타 사용자 데이터
    await db.execute(delete(CompetitorKeyword).where(CompetitorKeyword.user_id == user_id))
    await db.execute(delete(CompetitorMention).where(CompetitorMention.user_id == user_id))
    await db.execute(delete(HashtagTrend).where(HashtagTrend.user_id == user_id))
    await db.execute(delete(OutboundWebhook).where(OutboundWebhook.user_id == user_id))
    await db.execute(delete(UsageLog).where(UsageLog.user_id == user_id))

    # 6. 조직 처리 — 소유 조직은 초대코드·멤버·조직 순으로 삭제
    owned_org_ids = (
        await db.execute(select(Organization.id).where(Organization.owner_user_id == user_id))
    ).scalars().all()
    if owned_org_ids:
        await db.execute(delete(InviteCode).where(InviteCode.org_id.in_(owned_org_ids)))
        await db.execute(delete(OrganizationMember).where(OrganizationMember.org_id.in_(owned_org_ids)))
        await db.execute(delete(Organization).where(Organization.id.in_(owned_org_ids)))

    # 7. 다른 조직에서 멤버 제거
    await db.execute(delete(OrganizationMember).where(OrganizationMember.user_id == user_id))

    # 8. 유저 삭제
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()

    request.session.clear()
    return {"ok": True}
