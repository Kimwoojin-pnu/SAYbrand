from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import TIER_LIMITS
from backend.db.database import get_db
from backend.middleware.auth import get_current_user
from backend.models.orm import Alert, InviteCode, Organization, OrganizationMember, User
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
        white_label_enabled=org.white_label_enabled or False,
        white_label_brand_name=org.white_label_brand_name,
        white_label_color=org.white_label_color,
        white_label_sidebar_color=org.white_label_sidebar_color,
        white_label_logo_url=org.white_label_logo_url,
        slack_webhook_url=org.slack_webhook_url,
    )


@router.post("", response_model=OrgOut)
async def create_org(
    data: OrgCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    db_user = (await db.execute(select(User).where(User.id == user["id"]))).scalar_one_or_none()
    user_tier = (db_user.subscription_tier or "free") if db_user else "free"
    if user_tier not in TIER_LIMITS:
        user_tier = "free"

    owned_count = (await db.execute(
        select(func.count()).select_from(OrganizationMember).where(
            OrganizationMember.user_id == user["id"],
            OrganizationMember.role == "owner",
            OrganizationMember.status == "active",
        )
    )).scalar() or 0
    org_limit = TIER_LIMITS[user_tier]["orgs"]
    if org_limit != -1 and owned_count >= org_limit:
        raise HTTPException(
            403,
            detail=f"현재 플랜에서는 조직을 {org_limit}개까지 만들 수 있습니다. 플랜을 업그레이드해 주세요.",
        )

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


@router.get("/my-pending")
async def my_pending_requests(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """현재 사용자의 승인 대기 중인 가입 요청 목록"""
    rows = (
        await db.execute(
            select(OrganizationMember, Organization)
            .join(Organization, Organization.id == OrganizationMember.org_id)
            .where(
                OrganizationMember.user_id == user["id"],
                OrganizationMember.status == "pending",
            )
        )
    ).all()
    return [
        {
            "org_id": org.id,
            "org_name": org.name,
            "role": m.role,
            "requested_at": m.created_at,
        }
        for m, org in rows
    ]


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


@router.patch("/{org_id}/settings")
async def update_org_settings(
    org_id: int,
    data: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_role(org_id, user["id"], ["owner", "admin"], db)
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if "slack_webhook_url" in data:
        org.slack_webhook_url = data["slack_webhook_url"] or None
    white_label_keys = {"white_label_enabled", "white_label_brand_name", "white_label_color", "white_label_sidebar_color", "white_label_logo_url"}
    if white_label_keys & data.keys():
        if get_effective_tier(org) not in ("pro", "enterprise"):
            raise HTTPException(status_code=403, detail="화이트 라벨 기능은 Pro 이상 플랜에서만 사용할 수 있습니다.")
    if "white_label_enabled" in data:
        org.white_label_enabled = bool(data["white_label_enabled"])
    if "white_label_brand_name" in data:
        org.white_label_brand_name = data["white_label_brand_name"] or None
    if "white_label_color" in data:
        org.white_label_color = data["white_label_color"] or None
    if "white_label_sidebar_color" in data:
        org.white_label_sidebar_color = data["white_label_sidebar_color"] or None
    if "white_label_logo_url" in data:
        org.white_label_logo_url = data["white_label_logo_url"] or None
    await db.commit()
    return {"ok": True}


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


@router.get("/{org_id}/invite-codes")
async def list_invite_codes(
    org_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """유효한 초대코드 목록 조회 (owner/admin 전용)"""
    await _require_role(org_id, user["id"], ["owner", "admin"], db)
    result = await db.execute(
        select(InviteCode)
        .where(
            InviteCode.org_id == org_id,
            InviteCode.is_active == True,
            InviteCode.expires_at > datetime.utcnow(),
        )
        .order_by(InviteCode.created_at.desc())
    )
    codes = result.scalars().all()

    # 역할별로 가장 최근 1개만 유지
    seen: set[str] = set()
    deduped = []
    for c in codes:
        if c.role_to_assign not in seen:
            seen.add(c.role_to_assign)
            deduped.append(c)

    now = datetime.utcnow()
    return [
        {
            "code": c.code,
            "role_to_assign": c.role_to_assign,
            "expires_at": c.expires_at,
            "remaining_days": max(0, (c.expires_at - now).days),
            "uses_count": c.uses_count,
            "max_uses": c.max_uses,
        }
        for c in deduped
    ]


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

    # 멤버 한도 체크는 실제 join 시점(join_with_code)에서 수행
    # 코드 발급 자체는 항상 허용 (발급된 코드로 가입 시 한도 초과 시 거부)

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
    if result.get("status") == "active":
        u_row = (await db.execute(select(User).where(User.id == user["id"]))).scalar_one_or_none()
        name = (u_row.name or u_row.email) if u_row else "새 멤버"
        db.add(Alert(
            alert_type="member_join", org_id=result.get("org_id"),
            user_id=user["id"], severity="low",
            message=f"{name}님이 조직에 합류했습니다.", channel="dashboard",
        ))
        await db.commit()
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
        u_row = (await db.execute(select(User).where(User.id == target_user_id))).scalar_one_or_none()
        name = (u_row.name or u_row.email) if u_row else f"멤버 #{target_user_id}"
        db.add(Alert(
            alert_type="member_join", org_id=org_id, user_id=target_user_id,
            severity="low",
            message=f"{name}님의 가입이 승인되었습니다.", channel="dashboard",
        ))
    else:
        await db.delete(member)

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

    u_row = (await db.execute(select(User).where(User.id == target_user_id))).scalar_one_or_none()
    name = (u_row.name or u_row.email) if u_row else f"멤버 #{target_user_id}"
    role_str = member.role
    await db.delete(member)
    db.add(Alert(
        alert_type="member_leave", org_id=org_id, user_id=target_user_id,
        severity="low",
        message=f"{name}님({role_str})이 조직에서 제거되었습니다.", channel="dashboard",
    ))
    await db.commit()
    return {"success": True}


@router.patch("/{org_id}/transfer-ownership")
async def transfer_ownership(
    org_id: int,
    target_user_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """소유권을 다른 활성 멤버에게 이전한다. 기존 owner는 admin으로 강등."""
    if target_user_id == user["id"]:
        raise HTTPException(400, detail="자신에게 소유권을 이전할 수 없습니다.")

    await _require_role(org_id, user["id"], ["owner"], db)

    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(404)

    target_result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == target_user_id,
            OrganizationMember.status == "active",
        )
    )
    target_member = target_result.scalar_one_or_none()
    if not target_member:
        raise HTTPException(404, detail="이전할 멤버를 찾을 수 없습니다.")

    current_owner_result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == user["id"],
        )
    )
    current_owner_member = current_owner_result.scalar_one_or_none()

    org.owner_user_id = target_user_id
    target_member.role = "owner"
    if current_owner_member:
        current_owner_member.role = "admin"

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

    u_row = (await db.execute(select(User).where(User.id == user["id"]))).scalar_one_or_none()
    name = (u_row.name or u_row.email) if u_row else "멤버"
    await db.delete(member)
    db.add(Alert(
        alert_type="member_leave", org_id=org_id, user_id=user["id"],
        severity="low",
        message=f"{name}님이 조직에서 탈퇴했습니다.", channel="dashboard",
    ))
    await db.commit()
    return {"success": True}
