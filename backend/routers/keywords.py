"""키워드 관리 API — GET / POST / DELETE"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import TIER_LIMITS
from backend.db.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.org_context import optional_current_org, require_non_viewer
from backend.models.orm import Keyword, Organization, User
from backend.services.org_service import get_effective_tier

router = APIRouter(prefix="/api/keywords", tags=["keywords"])


class KeywordCreate(BaseModel):
    keyword: str
    platforms: list[str] = ["instagram", "x", "youtube", "naver"]


class KeywordOut(BaseModel):
    id: int
    keyword: str
    platforms: list[str]
    active: bool

    class Config:
        from_attributes = True


@router.get("", response_model=list[KeywordOut])
async def list_keywords(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
):
    if org is not None:
        q = select(Keyword).where(Keyword.org_id == org.id, Keyword.active.is_(True))
    else:
        q = select(Keyword).where(Keyword.user_id == user["id"], Keyword.active.is_(True))
    result = await db.execute(q.order_by(Keyword.created_at.asc()))
    return result.scalars().all()


@router.post("", response_model=KeywordOut, status_code=201)
async def create_keyword(
    body: KeywordCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
    _: None = Depends(require_non_viewer),
):
    kw_text = body.keyword.strip()
    if not kw_text:
        raise HTTPException(status_code=400, detail="키워드를 입력해 주세요")

    existing_result = await db.execute(
        select(Keyword).where(Keyword.user_id == user["id"], Keyword.keyword == kw_text)
    )
    existing_kw = existing_result.scalar_one_or_none()
    if existing_kw:
        if existing_kw.active:
            raise HTTPException(status_code=409, detail="이미 등록된 키워드입니다")
        # 소프트 삭제된 키워드 복원
        existing_kw.active = True
        existing_kw.platforms = body.platforms
        existing_kw.org_id = org.id if org else None
        await db.commit()
        await db.refresh(existing_kw)
        return existing_kw

    if org is not None:
        tier = get_effective_tier(org)
        kw_count = (await db.execute(
            select(func.count()).select_from(Keyword).where(
                Keyword.org_id == org.id, Keyword.active.is_(True)
            )
        )).scalar() or 0
    else:
        db_user = (await db.execute(select(User).where(User.id == user["id"]))).scalar_one_or_none()
        tier = (db_user.subscription_tier or "free") if db_user else "free"
        if tier not in TIER_LIMITS:
            tier = "free"
        kw_count = (await db.execute(
            select(func.count()).select_from(Keyword).where(
                Keyword.user_id == user["id"],
                Keyword.org_id.is_(None),
                Keyword.active.is_(True),
            )
        )).scalar() or 0
    kw_limit = TIER_LIMITS[tier]["keywords"]
    if kw_limit != -1 and kw_count >= kw_limit:
        raise HTTPException(
            403,
            detail=f"현재 플랜에서는 키워드를 {kw_limit}개까지 등록할 수 있습니다. 플랜을 업그레이드해 주세요.",
        )

    kw = Keyword(
        user_id=user["id"],
        org_id=org.id if org else None,
        keyword=kw_text,
        platforms=body.platforms,
        active=True,
    )
    db.add(kw)
    await db.commit()
    await db.refresh(kw)
    return kw


@router.delete("/{keyword_id}", status_code=204)
async def delete_keyword(
    keyword_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
    _: None = Depends(require_non_viewer),
):
    if org is not None:
        q = select(Keyword).where(Keyword.id == keyword_id, Keyword.org_id == org.id)
    else:
        q = select(Keyword).where(Keyword.id == keyword_id, Keyword.user_id == user["id"])
    result = await db.execute(q)
    kw = result.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="키워드를 찾을 수 없습니다")

    kw.active = False
    await db.commit()
