"""고객센터 Q&A 게시판 API"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
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
    category: str = "general"
    is_secret: bool = False


class SupportReplyCreate(BaseModel):
    reply: str


class SupportPostListItem(BaseModel):
    id: int
    title: str
    user_name: str
    status: str
    category: str = "general"
    is_secret: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class SupportPostDetail(BaseModel):
    id: int
    title: str
    content: str
    user_name: str
    status: str
    category: str = "general"
    is_secret: bool = False
    admin_reply: str | None
    admin_reply_by: str | None
    answered_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/is-admin")
async def check_is_admin(user: dict = Depends(get_current_user)):
    return {"is_admin": _is_admin(user.get("email", ""))}


@router.get("", response_model=list[SupportPostListItem])
async def list_posts(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    is_admin = _is_admin(user.get("email", ""))
    stmt = select(SupportPost).order_by(SupportPost.created_at.desc())
    if not is_admin:
        stmt = stmt.where(SupportPost.category != "sales")
    result = await db.execute(stmt)
    posts = result.scalars().all()

    items = []
    for p in posts:
        # 비밀글이면서 본인/관리자가 아닌 경우 → 제목·작성자 가림
        hidden = p.is_secret and not is_admin and p.user_id != user["id"]
        items.append(SupportPostListItem(
            id=p.id,
            title="비밀글입니다" if hidden else p.title,
            user_name="익명" if hidden else p.user_name,
            status=p.status,
            category=p.category,
            is_secret=p.is_secret,
            created_at=p.created_at,
        ))
    return items


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

    category = body.category if body.category in ("general", "sales") else "general"
    post = SupportPost(
        user_id=user["id"],
        user_name=user.get("name") or user.get("email") or "익명",
        title=title,
        content=content,
        category=category,
        is_secret=body.is_secret,
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

    is_admin = _is_admin(user.get("email", ""))

    # 영업 문의는 관리자만
    if post.category == "sales" and not is_admin:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다")

    # 비밀글은 작성자 본인 또는 관리자만
    if post.is_secret and not is_admin and post.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="비밀글입니다. 작성자 본인 또는 관리자만 확인할 수 있습니다.")

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
