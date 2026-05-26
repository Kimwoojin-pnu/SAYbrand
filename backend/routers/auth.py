from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import settings
from backend.db.database import get_db
from backend.models.orm import User
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

    return RedirectResponse("/dashboard")


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
