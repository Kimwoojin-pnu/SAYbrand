import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.middleware.auth import get_current_user
from backend.middleware.org_context import optional_current_org, require_non_viewer
from backend.models.orm import (
    Organization,
    CustomerAlias,
    CustomerExecutive,
    CustomerProfile,
    CustomerSocialAccount,
    Keyword,
)
from backend.models.schemas import (
    CustomerAliasCreate,
    CustomerAliasOut,
    CustomerExecutiveCreate,
    CustomerExecutiveOut,
    CustomerProfileCreate,
    CustomerProfileOut,
    CustomerSocialAccountCreate,
    CustomerSocialAccountOut,
    DartLookupResult,
    WikidataLookupResult,
)
from backend.services.analyzers.l2_image import logo_engine
from backend.services.profile_enricher import enrich_from_dart, search_wikidata
from backend.services.profile_loader import profile_loader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["profile"])


async def _get_profile_or_404(
    profile_id: int,
    user_id: int,
    db: AsyncSession,
    org_id: int | None = None,
) -> CustomerProfile:
    if org_id is not None:
        q = select(CustomerProfile).where(
            CustomerProfile.id == profile_id,
            CustomerProfile.org_id == org_id,
        )
    else:
        q = select(CustomerProfile).where(
            CustomerProfile.id == profile_id,
            CustomerProfile.user_id == user_id,
        )
    profile = (await db.execute(q)).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


async def _load_full_profile(profile: CustomerProfile, db: AsyncSession) -> CustomerProfileOut:
    aliases = (await db.execute(
        select(CustomerAlias).where(CustomerAlias.profile_id == profile.id)
    )).scalars().all()
    accounts = (await db.execute(
        select(CustomerSocialAccount).where(CustomerSocialAccount.profile_id == profile.id)
    )).scalars().all()
    executives = (await db.execute(
        select(CustomerExecutive).where(CustomerExecutive.profile_id == profile.id)
    )).scalars().all()

    out = CustomerProfileOut.model_validate(profile)
    out.aliases = [CustomerAliasOut.model_validate(a) for a in aliases]
    out.social_accounts = [CustomerSocialAccountOut.model_validate(a) for a in accounts]
    out.executives = [CustomerExecutiveOut.model_validate(e) for e in executives]
    return out


# ── 자동 처리 헬퍼 ────────────────────────────────────────────────────────────

async def _sync_keywords_from_profile(
    profile_id: int,
    user_id: int,
    db: AsyncSession,
    org_id: int | None = None,
) -> None:
    """alias + 임직원 이름(priority ≤ 2) → keywords 테이블 upsert."""
    loaded = await profile_loader.load(profile_id, db)
    if not loaded:
        return
    all_platforms = ["instagram", "x", "youtube", "tiktok", "naver"]
    existing_result = await db.execute(
        select(Keyword.keyword).where(Keyword.user_id == user_id)
    )
    existing = {r[0] for r in existing_result.all()}
    for kw in loaded.search_keywords:
        if kw and kw not in existing:
            db.add(Keyword(
                user_id=user_id,
                org_id=org_id,
                keyword=kw,
                platforms=all_platforms,
                active=True,
            ))
    await db.commit()


async def _register_phash_background(profile_id: int, db: AsyncSession) -> None:
    """로고 + 임직원 사진 pHash 등록 (백그라운드, 실패해도 무시)."""
    try:
        loaded = await profile_loader.load(profile_id, db)
        if loaded:
            await logo_engine.register_from_profile(loaded)
    except Exception as e:
        logger.warning("pHash 자동 등록 실패 (무시): %s", e)


async def _post_profile_update(
    profile_id: int,
    user_id: int,
    db: AsyncSession,
    org_id: int | None = None,
) -> None:
    """프로파일 변경 후 공통 후처리."""
    profile_loader.invalidate(profile_id)
    await _sync_keywords_from_profile(profile_id, user_id, db, org_id=org_id)
    asyncio.create_task(_register_phash_background(profile_id, db))


# ── Profile CRUD ──────────────────────────────────────────────────────────────

@router.post("", response_model=CustomerProfileOut, status_code=201)
async def create_profile(
    body: CustomerProfileCreate,
    current_user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
    _: None = Depends(require_non_viewer),
    db: AsyncSession = Depends(get_db),
):
    profile = CustomerProfile(
        **body.model_dump(),
        user_id=current_user["id"],
        org_id=org.id if org else None,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    await _post_profile_update(profile.id, current_user["id"], db, org_id=org.id if org else None)
    return await _load_full_profile(profile, db)


@router.get("", response_model=list[CustomerProfileOut])
async def list_profiles(
    current_user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
    db: AsyncSession = Depends(get_db),
):
    if org is not None:
        q = select(CustomerProfile).where(CustomerProfile.org_id == org.id)
    else:
        q = select(CustomerProfile).where(CustomerProfile.user_id == current_user["id"])
    result = await db.execute(q)
    profiles = result.scalars().all()
    return [await _load_full_profile(p, db) for p in profiles]


@router.get("/{profile_id}", response_model=CustomerProfileOut)
async def get_profile(
    profile_id: int,
    current_user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_profile_or_404(
        profile_id, current_user["id"], db, org_id=org.id if org else None
    )
    return await _load_full_profile(profile, db)


@router.patch("/{profile_id}", response_model=CustomerProfileOut)
async def update_profile(
    profile_id: int,
    body: CustomerProfileCreate,
    current_user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
    _: None = Depends(require_non_viewer),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_profile_or_404(
        profile_id, current_user["id"], db, org_id=org.id if org else None
    )
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(profile, k, v)
    await db.commit()
    await db.refresh(profile)
    await _post_profile_update(profile_id, current_user["id"], db, org_id=org.id if org else None)
    return await _load_full_profile(profile, db)


# ── Aliases ───────────────────────────────────────────────────────────────────

@router.post("/{profile_id}/aliases", response_model=CustomerAliasOut, status_code=201)
async def add_alias(
    profile_id: int,
    body: CustomerAliasCreate,
    current_user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
    _: None = Depends(require_non_viewer),
    db: AsyncSession = Depends(get_db),
):
    await _get_profile_or_404(profile_id, current_user["id"], db, org_id=org.id if org else None)
    alias = CustomerAlias(**body.model_dump(), profile_id=profile_id)
    db.add(alias)
    await db.commit()
    await db.refresh(alias)
    profile_loader.invalidate(profile_id)
    return alias


@router.delete("/{profile_id}/aliases/{alias_id}", status_code=204)
async def delete_alias(
    profile_id: int,
    alias_id: int,
    current_user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
    _: None = Depends(require_non_viewer),
    db: AsyncSession = Depends(get_db),
):
    await _get_profile_or_404(profile_id, current_user["id"], db, org_id=org.id if org else None)
    result = await db.execute(
        select(CustomerAlias).where(
            CustomerAlias.id == alias_id, CustomerAlias.profile_id == profile_id
        )
    )
    alias = result.scalar_one_or_none()
    if not alias:
        raise HTTPException(status_code=404, detail="Alias not found")
    await db.delete(alias)
    await db.commit()
    profile_loader.invalidate(profile_id)


# ── Social Accounts ───────────────────────────────────────────────────────────

@router.post("/{profile_id}/social-accounts", response_model=CustomerSocialAccountOut, status_code=201)
async def add_social_account(
    profile_id: int,
    body: CustomerSocialAccountCreate,
    current_user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
    _: None = Depends(require_non_viewer),
    db: AsyncSession = Depends(get_db),
):
    await _get_profile_or_404(profile_id, current_user["id"], db, org_id=org.id if org else None)
    account = CustomerSocialAccount(**body.model_dump(), profile_id=profile_id)
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.delete("/{profile_id}/social-accounts/{account_id}", status_code=204)
async def delete_social_account(
    profile_id: int,
    account_id: int,
    current_user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
    _: None = Depends(require_non_viewer),
    db: AsyncSession = Depends(get_db),
):
    await _get_profile_or_404(profile_id, current_user["id"], db, org_id=org.id if org else None)
    result = await db.execute(
        select(CustomerSocialAccount).where(
            CustomerSocialAccount.id == account_id,
            CustomerSocialAccount.profile_id == profile_id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Social account not found")
    await db.delete(account)
    await db.commit()


# ── Executives ────────────────────────────────────────────────────────────────

@router.post("/{profile_id}/executives", response_model=CustomerExecutiveOut, status_code=201)
async def add_executive(
    profile_id: int,
    body: CustomerExecutiveCreate,
    current_user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
    _: None = Depends(require_non_viewer),
    db: AsyncSession = Depends(get_db),
):
    await _get_profile_or_404(profile_id, current_user["id"], db, org_id=org.id if org else None)
    exec_ = CustomerExecutive(**body.model_dump(), profile_id=profile_id)
    db.add(exec_)
    await db.commit()
    await db.refresh(exec_)
    profile_loader.invalidate(profile_id)
    asyncio.create_task(_register_phash_background(profile_id, db))
    return exec_


@router.delete("/{profile_id}/executives/{exec_id}", status_code=204)
async def delete_executive(
    profile_id: int,
    exec_id: int,
    current_user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
    _: None = Depends(require_non_viewer),
    db: AsyncSession = Depends(get_db),
):
    await _get_profile_or_404(profile_id, current_user["id"], db, org_id=org.id if org else None)
    result = await db.execute(
        select(CustomerExecutive).where(
            CustomerExecutive.id == exec_id,
            CustomerExecutive.profile_id == profile_id,
        )
    )
    exec_ = result.scalar_one_or_none()
    if not exec_:
        raise HTTPException(status_code=404, detail="Executive not found")
    await db.delete(exec_)
    await db.commit()
    profile_loader.invalidate(profile_id)


# ── Enrichment ────────────────────────────────────────────────────────────────

@router.post("/{profile_id}/enrich/dart", response_model=DartLookupResult)
async def enrich_dart(
    profile_id: int,
    current_user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
    _: None = Depends(require_non_viewer),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_profile_or_404(
        profile_id, current_user["id"], db, org_id=org.id if org else None
    )
    if not profile.dart_corp_code:
        raise HTTPException(status_code=400, detail="dart_corp_code가 설정되지 않았습니다")

    result = await enrich_from_dart(profile.dart_corp_code)
    if not result:
        raise HTTPException(status_code=502, detail="DART API 조회 실패")

    profile.display_name = result.corp_name
    profile.industry = result.industry
    await db.commit()
    return result


@router.post("/{profile_id}/enrich/wikidata", response_model=WikidataLookupResult)
async def enrich_wikidata(
    profile_id: int,
    current_user: dict = Depends(get_current_user),
    org: Organization | None = Depends(optional_current_org),
    _: None = Depends(require_non_viewer),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_profile_or_404(
        profile_id, current_user["id"], db, org_id=org.id if org else None
    )
    result = await search_wikidata(profile.display_name)
    if not result:
        raise HTTPException(status_code=404, detail="Wikidata에서 해당 기업을 찾을 수 없습니다")

    profile.wikidata_id = result.wikidata_id
    if result.logo_url:
        profile.logo_url = result.logo_url
    await db.commit()
    return result
