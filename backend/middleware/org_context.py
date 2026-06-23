from datetime import datetime

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.models.orm import Organization, OrganizationMember
from backend.services.org_service import make_slug


async def optional_current_org(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Organization | None:
    """인증된 사용자의 현재 조직 반환. 미인증이면 None."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None

    org_id = request.session.get("current_org_id")
    if org_id:
        org = await db.get(Organization, int(org_id))
        if org:
            return org

    result = await db.execute(
        select(Organization)
        .join(OrganizationMember, Organization.id == OrganizationMember.org_id)
        .where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.status == "active",
        )
        .limit(1)
    )
    org = result.scalar_one_or_none()
    if org:
        request.session["current_org_id"] = org.id
    return org


async def get_current_org(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Organization:
    """인증된 사용자의 현재 조직 반환. 조직이 없으면 자동 생성."""
    from backend.middleware.auth import get_current_user

    user = await get_current_user(request)
    user_id = user["id"]

    org = await optional_current_org(request, db)
    if org:
        return org

    base_slug = make_slug(user.get("name", "") or "org")
    slug = base_slug
    i = 1
    while (
        await db.execute(select(Organization).where(Organization.slug == slug))
    ).scalar_one_or_none():
        slug = f"{base_slug}-{i}"
        i += 1

    org = Organization(
        name=user.get("name", "내 조직"),
        slug=slug,
        owner_user_id=user_id,
        subscription_tier="free",
        subscription_status="active",
    )
    db.add(org)
    await db.flush()

    member = OrganizationMember(
        org_id=org.id,
        user_id=user_id,
        role="owner",
        status="active",
        joined_at=datetime.utcnow(),
    )
    db.add(member)
    await db.commit()
    await db.refresh(org)

    request.session["current_org_id"] = org.id
    return org


async def get_org_member_role(
    org_id: int,
    user_id: int,
    db: AsyncSession,
) -> str | None:
    """사용자의 조직 내 역할 반환. 멤버가 아니면 None."""
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.status == "active",
        )
    )
    member = result.scalar_one_or_none()
    return member.role if member else None


async def require_non_viewer(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Viewer 역할 차단 의존성. 미인증이면 통과(auth 의존성에 위임)."""
    user_id = request.session.get("user_id")
    if not user_id:
        return

    org = await optional_current_org(request, db)
    if org is None:
        return

    role = await get_org_member_role(org.id, user_id, db)
    if role == "viewer":
        raise HTTPException(403, detail="보고용 계정은 이 기능을 사용할 수 없습니다.")


async def require_admin_or_owner(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Admin/Owner만 허용. Viewer·Member 차단."""
    user_id = request.session.get("user_id")
    if not user_id:
        return

    org = await optional_current_org(request, db)
    if org is None:
        return

    role = await get_org_member_role(org.id, user_id, db)
    if role in ("viewer", "member"):
        raise HTTPException(403, detail="관리자 이상만 이 기능을 사용할 수 있습니다.")
