from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import TIER_LIMITS
from backend.db.database import get_db
from backend.middleware.auth import get_current_user
from backend.models.orm import InviteCode, Organization, OrganizationMember, User
from backend.models.schemas import JoinRequest, OrgCreate, OrgOut, RoleUpdate
from backend.services.org_service import (
    can_add_member,
    create_invite_code,
    get_billable_member_count,
    get_effective_tier,
    join_with_code,
    make_slug,
)

router = APIRouter(prefix="/api/orgs", tags=["organizations"])


async def _require_role(org_id: int, user_id: int, allowed_roles: list, db: AsyncSession):
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.status == "active",
        )
    )
    member = result.scalar_one_or_none()
    if not member or member.role not in allowed_roles:
        raise HTTPException(403, detail="권한이 없습니다.")
    return member


async def _org_out(org: Organization, user_id: int, db: AsyncSession) -> OrgOut:
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org.id,
            OrganizationMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    my_role = member.role if member else None

    tier = get_effective_tier(org)
    member_count = await get_billable_member_count(org.id, db)
    tier_limit = TIER_LIMITS[tier]["members"]

    return OrgOut(
        id=org.id,
        name=org.name,
        slug=org.slug,
        description=org.description,
        logo_url=org.logo_url,
        owner_user_id=org.owner_user_id,
        invite_mode=org.invite_mode,
        subscription_tier=org.subscription_tier,
        subscription_status=org.subscription_status,
        created_at=org.created_at,
        my_role=my_role,
        member_count=member_count,
        member_limit=tier_limit,
    )


@router.post("", response_model=OrgOut)
async def create_org(
    data: OrgCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_slug = make_slug(data.name)
    slug = base_slug
    i = 1
    while (
        await db.execute(select(Organization).where(Organization.slug == slug))
    ).scalar_one_or_none():
        slug = f"{base_slug}-{i}"
        i += 1

    org = Organization(
        name=data.name,
        slug=slug,
        description=data.description,
        invite_mode=data.invite_mode,
        owner_user_id=user["id"],
    )
    db.add(org)
    await db.flush()

    db.add(
        OrganizationMember(
            org_id=org.id,
            user_id=user["id"],
            role="owner",
            status="active",
            joined_at=datetime.utcnow(),
        )
    )
    await db.commit()
    await db.refresh(org)
    return await _org_out(org, user["id"], db)


@router.get("", response_model=list[OrgOut])
async def my_orgs(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Organization)
        .join(OrganizationMember, Organization.id == OrganizationMember.org_id)
        .where(
            OrganizationMember.user_id == user["id"],
            OrganizationMember.status == "active",
        )
    )
    orgs = result.scalars().all()
    return [await _org_out(o, user["id"], db) for o in orgs]


@router.post("/{org_id}/switch")
async def switch_org(
    org_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == user["id"],
            OrganizationMember.status == "active",
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(403, detail="이 조직에 접근할 수 없습니다.")
    request.session["current_org_id"] = org_id
    return {"success": True}


@router.post("/{org_id}/invite-codes")
async def issue_invite_code(
    org_id: int,
    role_to_assign: str = "member",
    expires_days: int = 7,
    max_uses: int = 0,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_role(org_id, user["id"], ["owner", "admin"], db)

    if role_to_assign != "viewer":
        org = await db.get(Organization, org_id)
        if not org:
            raise HTTPException(404)
        can_add = await can_add_member(org, db)
        if not can_add["allowed"]:
            raise HTTPException(
                402,
                detail={"message": can_add["message"], "upgrade_required": True},
            )

    invite = await create_invite_code(
        org_id, user["id"], role_to_assign, expires_days, max_uses, db
    )
    return {
        "code": invite.code,
        "expires_at": invite.expires_at,
        "role_to_assign": invite.role_to_assign,
    }


@router.post("/join")
async def join_org(
    body: JoinRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await join_with_code(body.code, user["id"], db)
    if not result["success"]:
        status_code = 402 if result.get("upgrade_required") else 400
        raise HTTPException(status_code, detail=result["error"])
    return result


@router.get("/{org_id}/members")
async def list_members(
    org_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_role(
        org_id, user["id"], ["owner", "admin", "member", "viewer"], db
    )
    rows = (
        await db.execute(
            select(OrganizationMember, User)
            .join(User, OrganizationMember.user_id == User.id)
            .where(OrganizationMember.org_id == org_id)
            .order_by(OrganizationMember.created_at)
        )
    ).all()

    org = await db.get(Organization, org_id)
    billable_count = await get_billable_member_count(org_id, db)
    tier_limit = TIER_LIMITS[get_effective_tier(org)]["members"]

    return {
        "members": [
            {
                "user_id": u.id,
                "name": u.name,
                "email": u.email,
                "avatar_url": u.avatar_url,
                "role": m.role,
                "status": m.status,
                "joined_at": m.joined_at,
            }
            for m, u in rows
        ],
        "billable_count": billable_count,
        "member_limit": tier_limit,
        "at_limit": billable_count >= tier_limit if tier_limit != -1 else False,
    }


@router.patch("/{org_id}/members/{target_user_id}/approve")
async def approve_member(
    org_id: int,
    target_user_id: int,
    action: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_role(org_id, user["id"], ["owner", "admin"], db)

    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == target_user_id,
            OrganizationMember.status == "pending",
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(404, detail="대기 중인 멤버를 찾을 수 없습니다.")

    if action == "approve":
        if member.role != "viewer":
            org = await db.get(Organization, org_id)
            can_add = await can_add_member(org, db)
            if not can_add["allowed"]:
                raise HTTPException(402, detail=can_add["message"])
        member.status = "active"
        member.joined_at = datetime.utcnow()
    else:
        member.status = "rejected"

    await db.commit()
    return {"success": True, "action": action}


@router.patch("/{org_id}/members/{target_user_id}/role")
async def change_role(
    org_id: int,
    target_user_id: int,
    body: RoleUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.role in ["owner", "admin"]:
        await _require_role(org_id, user["id"], ["owner"], db)
    else:
        await _require_role(org_id, user["id"], ["owner", "admin"], db)

    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == target_user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(404)

    if member.role == "viewer" and body.role in ["member", "admin"]:
        org = await db.get(Organization, org_id)
        can_add = await can_add_member(org, db)
        if not can_add["allowed"]:
            raise HTTPException(402, detail=can_add["message"])

    member.role = body.role
    await db.commit()
    return {"success": True}


@router.delete("/{org_id}/members/{target_user_id}")
async def remove_member(
    org_id: int,
    target_user_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_role(org_id, user["id"], ["owner", "admin"], db)

    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == target_user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(404)
    if member.role == "owner":
        raise HTTPException(400, detail="Owner는 강퇴할 수 없습니다.")

    await db.delete(member)
    await db.commit()
    return {"success": True}


@router.delete("/{org_id}/leave")
async def leave_org(
    org_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == user["id"],
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(404)
    if member.role == "owner":
        raise HTTPException(
            400,
            detail="Owner는 조직을 탈퇴할 수 없습니다. 조직을 삭제하거나 Owner를 이전하세요.",
        )

    await db.delete(member)
    await db.commit()
    return {"success": True}
