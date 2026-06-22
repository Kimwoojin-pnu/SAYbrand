from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel


class ThreatBase(BaseModel):
    id: int
    module: str
    threat_type: str
    severity: str
    platform: str
    source_account: str
    source_url: str
    content_preview: str
    confidence: float
    risk_score: int
    ai_analysis: Optional[str] = None
    ai_response_suggestion: Optional[str] = None
    bot_probability: Optional[float] = None
    is_organized: Optional[bool] = None
    status: str
    post_published_at: Optional[datetime] = None
    engagements_per_hour: float = 0.0
    detected_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ThreatListResponse(BaseModel):
    items: list[ThreatBase]
    total: int
    page: int
    page_size: int


class AlertResponse(BaseModel):
    id: int
    threat_id: int
    severity: str
    message: str
    channel: str
    sent_at: datetime

    model_config = {"from_attributes": True}


class StatsResponse(BaseModel):
    total: int
    critical: int
    high: int
    medium: int
    low: int
    active: int
    reviewing: int
    resolved: int


class ModuleScore(BaseModel):
    module: str
    score: float
    threat_count: int


class RiskScoreResponse(BaseModel):
    overall: float
    module_a: ModuleScore
    module_b: ModuleScore
    module_c: ModuleScore
    level: str


class StatusUpdateRequest(BaseModel):
    status: str


SubscriptionStatus = Literal["free", "active", "cancelled"]


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    avatar_url: Optional[str] = None
    subscription_status: SubscriptionStatus
    subscription_tier: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Customer Profile ──────────────────────────────────────────────────────────

class CustomerAliasCreate(BaseModel):
    alias: str
    alias_type: Literal["official", "nickname", "abbreviation", "english"]
    weight: float = 1.0


class CustomerAliasOut(CustomerAliasCreate):
    id: int
    profile_id: int

    model_config = {"from_attributes": True}


class CustomerSocialAccountCreate(BaseModel):
    platform: Literal["instagram", "x", "youtube", "tiktok", "naver"]
    handle: str
    verified: bool = True


class CustomerSocialAccountOut(CustomerSocialAccountCreate):
    id: int
    profile_id: int

    model_config = {"from_attributes": True}


class CustomerExecutiveCreate(BaseModel):
    name: str
    role: str
    photo_url: Optional[str] = None
    priority: int = 2


class CustomerExecutiveOut(CustomerExecutiveCreate):
    id: int
    profile_id: int

    model_config = {"from_attributes": True}


class CustomerProfileCreate(BaseModel):
    profile_type: Literal["company", "individual"]
    display_name: str
    industry: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    dart_corp_code: Optional[str] = None
    wikidata_id: Optional[str] = None


class CustomerProfileOut(CustomerProfileCreate):
    id: int
    user_id: int
    created_at: datetime
    aliases: list[CustomerAliasOut] = []
    social_accounts: list[CustomerSocialAccountOut] = []
    executives: list[CustomerExecutiveOut] = []

    model_config = {"from_attributes": True}


class DartLookupResult(BaseModel):
    corp_name: str
    ceo_name: str
    industry: str
    established_at: Optional[str] = None
    homepage: Optional[str] = None


class WikidataLookupResult(BaseModel):
    wikidata_id: str
    label: str
    logo_url: Optional[str] = None
    instagram_handle: Optional[str] = None
    twitter_handle: Optional[str] = None
    youtube_channel: Optional[str] = None


class EntityResolverResult(BaseModel):
    relevance_score: float
    matched_aliases: list[str]
    matched_accounts: list[str]
    is_relevant: bool
    confidence: Literal["high", "medium", "low"]


# ── Organization ──────────────────────────────────────────────────────────────

class OrgCreate(BaseModel):
    name: str
    description: Optional[str] = None
    invite_mode: str = "approval"


class OrgOut(BaseModel):
    id: int
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    owner_user_id: int
    invite_mode: str
    subscription_tier: str
    subscription_status: str
    created_at: datetime
    my_role: Optional[str] = None
    member_count: Optional[int] = None
    member_limit: Optional[int] = None
    white_label_enabled: bool = False
    white_label_brand_name: Optional[str] = None
    white_label_color: Optional[str] = None
    white_label_sidebar_color: Optional[str] = None
    white_label_logo_url: Optional[str] = None
    slack_webhook_url: Optional[str] = None

    model_config = {"from_attributes": True}


class JoinRequest(BaseModel):
    code: str


class RoleUpdate(BaseModel):
    role: str
