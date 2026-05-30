"""활동 로그 API — 조직 내 처리 내역 조회/삭제 (어드민·오너 전용)"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.org_context import optional_current_org
from backend.models.orm import ActivityLog, Organization, OrganizationMember

router = APIRouter(prefix="/api/activity", tags=["activity"])


async def _get_role(user_id: int, org: Organization | None, db: AsyncSession) -> str:
    if org is None:
        return "owner"
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org.id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.status == "active",
        )
    )
    member = result.scalar_one_or_none()
    return member.role if member else "member"


@router.get("/logs")
async def get_activity_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
):
    now = datetime.utcnow()
    await db.execute(delete(ActivityLog).where(ActivityLog.expires_at <= now))
    await db.commit()

    role = await _get_role(user["id"], org, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="관리자 이상 권한이 필요합니다.")

    if org:
        base = select(ActivityLog).where(ActivityLog.org_id == org.id)
        count_q = select(func.count(ActivityLog.id)).where(ActivityLog.org_id == org.id)
    else:
        base = select(ActivityLog).where(ActivityLog.user_id == user["id"])
        count_q = select(func.count(ActivityLog.id)).where(ActivityLog.user_id == user["id"])

    total = (await db.execute(count_q)).scalar() or 0
    result = await db.execute(
        base.order_by(ActivityLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = result.scalars().all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": l.id,
                "user_name": l.user_name,
                "action_type": l.action_type,
                "action_detail": l.action_detail,
                "target_id": l.target_id,
                "target_type": l.target_type,
                "created_at": l.created_at.isoformat() if l.created_at else None,
                "expires_at": l.expires_at.isoformat() if l.expires_at else None,
            }
            for l in logs
        ],
    }


@router.delete("/logs/{log_id}")
async def delete_activity_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
):
    role = await _get_role(user["id"], org, db)
    if role != "owner":
        raise HTTPException(status_code=403, detail="오너만 로그를 삭제할 수 있습니다.")

    result = await db.execute(select(ActivityLog).where(ActivityLog.id == log_id))
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="로그를 찾을 수 없습니다.")

    await db.delete(log)
    await db.commit()
    return {"id": log_id, "deleted": True}


@router.delete("/logs")
async def delete_all_activity_logs(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
):
    role = await _get_role(user["id"], org, db)
    if role != "owner":
        raise HTTPException(status_code=403, detail="오너만 로그를 일괄 삭제할 수 있습니다.")

    if org:
        await db.execute(delete(ActivityLog).where(ActivityLog.org_id == org.id))
    else:
        await db.execute(delete(ActivityLog).where(ActivityLog.user_id == user["id"]))
    await db.commit()
    return {"deleted": True}
