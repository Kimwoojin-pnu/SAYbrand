"""고객센터 Q&A 게시판 API"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.database import get_db
from backend.middleware.auth import get_current_user
from backend.models.orm import SupportPost

router = APIRouter(prefix="/api/support", tags=["support"])


def _is_admin(email: str) -> bool:
    admins = [e.strip().lower() for e in settings.support_admin_emails.split(",") if e.strip()]
    return email.lower() in admins


class SupportPostCreate(BaseModel):
    title: str
    content: str


class SupportReplyCreate(BaseModel):
    reply: str


class SupportPostListItem(BaseModel):
    id: int
    title: str
    user_name: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class SupportPostDetail(BaseModel):
    id: int
    title: str
    content: str
    user_name: str
    status: str
    admin_reply: str | None
    admin_reply_by: str | None
    answered_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=list[SupportPostListItem])
async def list_posts(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(select(SupportPost).order_by(SupportPost.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=SupportPostDetail, status_code=201)
async def create_post(
    body: SupportPostCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    title = body.title.strip()
    content = body.content.strip()
    if not title or not content:
        raise HTTPException(status_code=400, detail="제목과 내용을 입력해 주세요")

    post = SupportPost(
        user_id=user["id"],
        user_name=user.get("name") or user.get("email") or "익명",
        title=title,
        content=content,
        status="pending",
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post


@router.get("/{post_id}", response_model=SupportPostDetail)
async def get_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = await db.execute(select(SupportPost).where(SupportPost.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다")
    return post


@router.post("/{post_id}/reply", response_model=SupportPostDetail)
async def reply_post(
    post_id: int,
    body: SupportReplyCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if not _is_admin(user.get("email", "")):
        raise HTTPException(status_code=403, detail="답변 권한이 없습니다")

    result = await db.execute(select(SupportPost).where(SupportPost.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다")

    reply = body.reply.strip()
    if not reply:
        raise HTTPException(status_code=400, detail="답변 내용을 입력해 주세요")

    post.admin_reply = reply
    post.admin_reply_by = user.get("name") or user.get("email") or "운영자"
    post.status = "answered"
    post.answered_at = datetime.utcnow()
    post.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(post)
    return post
