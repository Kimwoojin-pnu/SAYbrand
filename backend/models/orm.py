from datetime import datetime, date
from sqlalchemy import Integer, String, Float, Boolean, Text, DateTime, Date, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    company: Mapped[str] = mapped_column(String(200), default="")
    user_type: Mapped[str] = mapped_column(String(50), default="google")
    google_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    polar_customer_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    subscription_status: Mapped[str] = mapped_column(String(20), default="free")
    subscription_tier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Threat(Base):
    __tablename__ = "threats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    org_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    module: Mapped[str] = mapped_column(String(1))
    threat_type: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(20))
    platform: Mapped[str] = mapped_column(String(50))
    source_account: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str] = mapped_column(String(500))
    content_preview: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    risk_score: Mapped[int] = mapped_column(Integer)
    ai_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_response_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    bot_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_organized: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    emotion: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reach_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    region: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    resolution_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resolution_method: Mapped[str | None] = mapped_column(String(200), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    post_published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    engagements_per_hour: Mapped[float] = mapped_column(Float, default=0.0)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    threat_id: Mapped[int] = mapped_column(Integer, ForeignKey("threats.id"))
    severity: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(50))
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    org_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    keyword: Mapped[str] = mapped_column(String(200))
    platforms: Mapped[list] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    org_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    profile_type: Mapped[str] = mapped_column(String(20))       # "company" | "individual"
    display_name: Mapped[str] = mapped_column(String(200))
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dart_corp_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    wikidata_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CustomerAlias(Base):
    __tablename__ = "customer_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer_profiles.id"))
    alias: Mapped[str] = mapped_column(String(200))
    alias_type: Mapped[str] = mapped_column(String(50))  # official|nickname|abbreviation|english
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class CustomerSocialAccount(Base):
    __tablename__ = "customer_social_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer_profiles.id"))
    platform: Mapped[str] = mapped_column(String(50))   # instagram|x|youtube|tiktok|naver
    handle: Mapped[str] = mapped_column(String(200))
    verified: Mapped[bool] = mapped_column(Boolean, default=True)


class CustomerExecutive(Base):
    __tablename__ = "customer_executives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer_profiles.id"))
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(100))      # CEO|CFO|임원|...
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=2)  # 1=CEO, 2=임원, 3=일반


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    profile_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("customer_profiles.id"), nullable=True)
    model: Mapped[str] = mapped_column(String(50))   # "hyperclova"|"gemini"|"mock"|"claude"
    layer: Mapped[str] = mapped_column(String(20))   # "L2_text"|"L2_image"|"L3"
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FeedbackLog(Base):
    __tablename__ = "feedback_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    threat_id: Mapped[int] = mapped_column(Integer, ForeignKey("threats.id"))
    original_verdict: Mapped[str] = mapped_column(String(100))  # "organized_attack" 등
    actual_verdict: Mapped[str] = mapped_column(String(100))    # "false_positive" 등
    marked_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    marked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    invite_mode: Mapped[str] = mapped_column(String(20), default="approval")
    subscription_tier: Mapped[str] = mapped_column(String(20), default="free")
    subscription_status: Mapped[str] = mapped_column(String(20), default="active")
    grace_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    polar_subscription_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    slack_webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    white_label_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    white_label_logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    white_label_brand_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    white_label_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(20), default="member")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    invited_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("org_id", "user_id"),)


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"))
    code: Mapped[str] = mapped_column(String(20), unique=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    role_to_assign: Mapped[str] = mapped_column(String(20), default="member")
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    max_uses: Mapped[int] = mapped_column(Integer, default=0)
    uses_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CompetitorKeyword(Base):
    __tablename__ = "competitor_keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    keyword: Mapped[str] = mapped_column(String(200))
    competitor_name: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CompetitorMention(Base):
    __tablename__ = "competitor_mentions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    competitor_name: Mapped[str] = mapped_column(String(200))
    platform: Mapped[str] = mapped_column(String(50))
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    content_preview: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class HashtagTrend(Base):
    __tablename__ = "hashtag_trends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    hashtag: Mapped[str] = mapped_column(String(200))
    platform: Mapped[str] = mapped_column(String(50))
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    trend_date: Mapped[date] = mapped_column(Date)


class OutboundWebhook(Base):
    __tablename__ = "outbound_webhooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    url: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(String(200), default="")
    events: Mapped[str] = mapped_column(Text, default="[]")
    secret: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DismissedUrl(Base):
    """경미 처리된 콘텐츠 — 재스캔 차단용"""
    __tablename__ = "dismissed_urls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    org_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dismissed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ArchivedThreat(Base):
    """조치완료 위협 보관 — 최대 30일"""
    __tablename__ = "archived_threats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=True)
    original_threat_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolved_by_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    resolved_by_name: Mapped[str] = mapped_column(String(200), default="")
    severity: Mapped[str] = mapped_column(String(20))
    threat_type: Mapped[str] = mapped_column(String(100))
    platform: Mapped[str] = mapped_column(String(50))
    source_account: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_preview: Mapped[str] = mapped_column(Text)
    risk_score: Mapped[int] = mapped_column(Integer)
    action_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_detected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class SupportPost(Base):
    """고객센터 Q&A 게시판"""
    __tablename__ = "support_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    user_name: Mapped[str] = mapped_column(String(200), default="")
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|answered
    admin_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_reply_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ActivityLog(Base):
    """팀 활동 내역 — 최대 7일, 오너만 삭제 가능"""
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    user_name: Mapped[str] = mapped_column(String(200), default="")
    action_type: Mapped[str] = mapped_column(String(50))
    action_detail: Mapped[str] = mapped_column(Text)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
