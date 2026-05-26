import os
from pydantic_settings import BaseSettings


def _db_url() -> str:
    if os.environ.get("VERCEL"):
        return "sqlite+aiosqlite:////tmp/brandguard.db"
    return os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./brandguard.db")


class Settings(BaseSettings):
    app_name: str = "SAYbrand"
    app_env: str = "development"

    # DB — Vercel 환경에서는 /tmp 경로 사용
    database_url: str = _db_url()

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # 환경 식별
    is_vercel: bool = False
    is_railway: bool = False

    @property
    def is_production(self) -> bool:
        return self.is_vercel or self.is_railway

    @property
    def is_local(self) -> bool:
        return not self.is_production

    @property
    def can_run_workers(self) -> bool:
        """Celery 워커 실행 가능 여부"""
        return self.is_railway or self.is_local

    @property
    def db_url_safe(self) -> str:
        """환경에 맞는 DB URL 반환 (로컬에 PostgreSQL 없으면 SQLite 폴백)"""
        if self.is_local and "postgresql" in self.database_url:
            return "sqlite+aiosqlite:///./brandguard.db"
        return self.database_url

    # AI API
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    google_vision_api_key: str = ""
    hyperclova_api_key: str = ""
    hyperclova_gateway_key: str = ""

    # YouTube
    youtube_api_key: str = ""

    # SMTP 이메일 알림
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_from_email: str = "alert@saybrand.ai"

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/callback"
    session_secret_key: str = "dev-secret-change-in-production"

    # Polar.sh
    polar_access_token: str = ""
    polar_webhook_secret: str = ""
    polar_product_id: str = ""

    # DART
    dart_api_key: str = ""

    # Naver Search API
    naver_client_id: str = ""
    naver_client_secret: str = ""

    # X (Twitter) API v2
    x_bearer_token: str = ""

    rate_limit_per_minute: int = 60

    # 데모 모드 — Google OAuth 없이 seed 유저로 자동 로그인
    demo_mode: bool = False

    class Config:
        env_file = ".env"


settings = Settings()

TIER_LIMITS: dict[str, dict[str, int]] = {
    "free":       {"members": 1,   "keywords": 3,  "platforms": 1},
    "starter":    {"members": 3,   "keywords": 10, "platforms": 3},
    "pro":        {"members": 10,  "keywords": 50, "platforms": 5},
    "enterprise": {"members": -1,  "keywords": -1, "platforms": -1},
}
