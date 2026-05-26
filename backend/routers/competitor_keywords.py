"""경쟁사 키워드 CRUD"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.middleware.auth import require_login
from backend.models.orm import CompetitorKeyword

router = APIRouter(prefix="/api/competitor-keywords", tags=["competitor-keywords"])


class CompKeywordCreate(BaseModel):
    keyword: str
    competitor_name: str


@router.get("")
async def list_keywords(
    user=Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CompetitorKeyword)
        .where(CompetitorKeyword.user_id == user.id, CompetitorKeyword.active.is_(True))
        .order_by(CompetitorKeyword.created_at.desc())
    )
    rows = result.scalars().all()
    return [
        {"id": r.id, "keyword": r.keyword, "competitor_name": r.competitor_name}
        for r in rows
    ]


@router.post("", status_code=201)
async def create_keyword(
    body: CompKeywordCreate,
    user=Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    kw = CompetitorKeyword(
        user_id=user.id,
        keyword=body.keyword.strip(),
        competitor_name=body.competitor_name.strip(),
        active=True,
    )
    db.add(kw)
    await db.commit()
    await db.refresh(kw)
    return {"id": kw.id, "keyword": kw.keyword, "competitor_name": kw.competitor_name}


@router.delete("/{kw_id}", status_code=204)
async def delete_keyword(
    kw_id: int,
    user=Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CompetitorKeyword).where(
            CompetitorKeyword.id == kw_id,
            CompetitorKeyword.user_id == user.id,
        )
    )
    kw = result.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="Not found")
    kw.active = False
    await db.commit()
