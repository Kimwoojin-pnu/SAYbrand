"""키워드 관리 API — GET / POST / DELETE"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.org_context import optional_current_org, require_non_viewer
from backend.models.orm import Keyword, Organization

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

    existing = await db.execute(
        select(Keyword).where(Keyword.user_id == user["id"], Keyword.keyword == kw_text)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="이미 등록된 키워드입니다")

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
