import re
import secrets
import string
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import TIER_LIMITS
from backend.models.orm import InviteCode, Organization, OrganizationMember


async def get_billable_member_count(org_id: int, db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(OrganizationMember)
        .where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.status == "active",
            OrganizationMember.role != "viewer",
        )
    )
    return result.scalar() or 0


def get_effective_tier(org: Organization) -> str:
    if org.subscription_status == "active":
        return org.subscription_tier
    if org.subscription_status == "grace":
        if org.grace_period_ends_at and datetime.utcnow() < org.grace_period_ends_at:
            return org.subscription_tier
        return "free"
    return "free"


async def can_add_member(org: Organization, db: AsyncSession) -> dict:
    tier = get_effective_tier(org)
    limit = TIER_LIMITS[tier]["members"]
    current = await get_billable_member_count(org.id, db)
    if limit == -1:
        return {"allowed": True}
    if current >= limit:
        return {
            "allowed": False,
            "current": current,
            "limit": limit,
            "tier": tier,
            "upgrade_required": True,
            "message": f"현재 플랜({tier})의 최대 멤버 수({limit}명)에 도달했습니다.",
        }
    return {"allowed": True, "current": current, "limit": limit}


async def create_invite_code(
    org_id: int,
    created_by: int,
    role_to_assign: str = "member",
    expires_days: int = 7,
    max_uses: int = 0,
    db: AsyncSession = None,
) -> InviteCode:
    alphabet = (
        string.ascii_uppercase.replace("O", "").replace("I", "") + string.digits
    )
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(8))
        exists = await db.execute(
            select(InviteCode).where(InviteCode.code == code)
        )
        if not exists.scalar_one_or_none():
            break

    invite = InviteCode(
        org_id=org_id,
        code=code,
        created_by=created_by,
        role_to_assign=role_to_assign,
        expires_at=datetime.utcnow() + timedelta(days=expires_days),
        max_uses=max_uses,
    )
    db.add(invite)
    await db.commit()
    return invite


async def join_with_code(code: str, user_id: int, db: AsyncSession) -> dict:
    result = await db.execute(
        select(InviteCode).where(
            InviteCode.code == code, InviteCode.is_active == True
        )
    )
    invite = result.scalar_one_or_none()
    if not invite:
        return {"success": False, "error": "유효하지 않은 초대코드입니다."}
    if datetime.utcnow() > invite.expires_at:
        return {"success": False, "error": "만료된 초대코드입니다."}
    if invite.max_uses > 0 and invite.uses_count >= invite.max_uses:
        return {"success": False, "error": "사용 횟수가 초과된 초대코드입니다."}

    existing = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == invite.org_id,
            OrganizationMember.user_id == user_id,
        )
    )
    if existing.scalar_one_or_none():
        return {"success": False, "error": "이미 이 조직의 멤버입니다."}

    org_result = await db.execute(
        select(Organization).where(Organization.id == invite.org_id)
    )
    org = org_result.scalar_one()

    if invite.role_to_assign != "viewer":
        can_add = await can_add_member(org, db)
        if not can_add["allowed"]:
            return {
                "success": False,
                "error": can_add["message"],
                "upgrade_required": True,
            }

    # 초대코드로 참여 시 invite_mode와 무관하게 즉시 활성화
    # (코드 발급 자체가 사전 승인이므로 별도 승인 불필요)
    initial_status = "active"
    member = OrganizationMember(
        org_id=invite.org_id,
        user_id=user_id,
        role=invite.role_to_assign,
        status=initial_status,
        invited_by=invite.created_by,
        joined_at=datetime.utcnow() if initial_status == "active" else None,
    )
    db.add(member)
    invite.uses_count += 1
    await db.commit()

    if initial_status == "active":
        return {
            "success": True,
            "status": "active",
            "org_id": invite.org_id,
            "message": f"{org.name} 조직에 참여했습니다.",
        }
    return {
        "success": True,
        "status": "pending",
        "org_id": invite.org_id,
        "message": "가입 요청이 전송됐습니다. 관리자 승인을 기다려주세요.",
    }


async def handle_subscription_cancelled(org_id: int, db: AsyncSession):
    org = await db.get(Organization, org_id)
    if org:
        org.subscription_status = "grace"
        org.grace_period_ends_at = datetime.utcnow() + timedelta(days=7)
        await db.commit()


async def process_expired_grace_periods(db: AsyncSession):
    now = datetime.utcnow()
    result = await db.execute(
        select(Organization).where(
            Organization.subscription_status == "grace",
            Organization.grace_period_ends_at < now,
        )
    )
    orgs = result.scalars().all()
    for org in orgs:
        org.subscription_status = "cancelled"
        org.subscription_tier = "free"
        await _enforce_member_limit(org, db)
    await db.commit()


async def _enforce_member_limit(org: Organization, db: AsyncSession):
    result = await db.execute(
        select(OrganizationMember)
        .where(
            OrganizationMember.org_id == org.id,
            OrganizationMember.status == "active",
            OrganizationMember.role != "owner",
            OrganizationMember.role != "viewer",
        )
        .order_by(OrganizationMember.joined_at.desc())
    )
    members = result.scalars().all()
    for m in members:
        m.role = "viewer"


def make_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "org"
