import os
import sys
os.environ["PYTHONUNBUFFERED"] = "1"  # Vercel stdout 즉시 flush
sys.stdout.reconfigure(line_buffering=True)
from backend.version import VERSION, BUILD_DATE
print(f"[STARTUP] SAYbrand {VERSION} ({BUILD_DATE}) | DB: {os.environ.get('DATABASE_URL', 'NOT SET')[:30]}")

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from backend.config import settings
from backend.middleware.rate_limiter import rate_limit_middleware
from backend.routers import dashboard
from backend.routers import activity, auth, billing, orgs, profile, keywords, reports, assistant, webhooks, competitor_keywords


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.db.database import engine
    if engine is not None:
        db_url = os.environ.get("DATABASE_URL", "")
        if "postgresql" in db_url or "postgres" in db_url:
            from sqlalchemy import text
            _migrations = [
                "ALTER TABLE threats ADD COLUMN IF NOT EXISTS resolution_type VARCHAR(50)",
                "ALTER TABLE threats ADD COLUMN IF NOT EXISTS resolution_method VARCHAR(200)",
                "ALTER TABLE threats ADD COLUMN IF NOT EXISTS resolution_note TEXT",
                "CREATE TABLE IF NOT EXISTS dismissed_urls (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id), org_id INTEGER REFERENCES organizations(id), source_url VARCHAR(500), content_hash VARCHAR(64), dismissed_at TIMESTAMP DEFAULT NOW())",
                "CREATE TABLE IF NOT EXISTS archived_threats (id SERIAL PRIMARY KEY, org_id INTEGER REFERENCES organizations(id), original_threat_id INTEGER, resolved_by_user_id INTEGER REFERENCES users(id), resolved_by_name VARCHAR(200) DEFAULT '', severity VARCHAR(20), threat_type VARCHAR(100), platform VARCHAR(50), source_account VARCHAR(200), source_url VARCHAR(500), content_preview TEXT, risk_score INTEGER, action_taken TEXT, resolution_note TEXT, original_detected_at TIMESTAMP, archived_at TIMESTAMP DEFAULT NOW(), expires_at TIMESTAMP)",
                "CREATE TABLE IF NOT EXISTS activity_logs (id SERIAL PRIMARY KEY, org_id INTEGER REFERENCES organizations(id), user_id INTEGER REFERENCES users(id), user_name VARCHAR(200) DEFAULT '', action_type VARCHAR(50), action_detail TEXT, target_id INTEGER, target_type VARCHAR(50), created_at TIMESTAMP DEFAULT NOW(), expires_at TIMESTAMP)",
            ]
            try:
                async with engine.begin() as conn:
                    for stmt in _migrations:
                        await conn.execute(text(stmt))
            except Exception as e:
                print(f"[MIGRATION] skipped: {e}")
    yield


app = FastAPI(title="SAYbrand", lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)
app.add_middleware(BaseHTTPMiddleware, dispatch=rate_limit_middleware)

app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")

app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(orgs.router)
app.include_router(profile.router)
app.include_router(dashboard.router)
app.include_router(keywords.router)
app.include_router(reports.router)
app.include_router(assistant.router)
app.include_router(webhooks.router)
app.include_router(competitor_keywords.router)
app.include_router(activity.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/saybrand-logo.png")
async def saybrand_logo():
    return FileResponse("saybrand-logo.png", media_type="image/png")


@app.get("/saybrand-logo2.png")
async def saybrand_logo2():
    return FileResponse("saybrand-logo2.png", media_type="image/png")


@app.get("/")
async def root():
    return FileResponse("frontend/pages/landing.html")


@app.get("/login")
async def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/dashboard")
    return FileResponse("frontend/pages/login.html")


@app.get("/dashboard")
async def dashboard_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login")
    return FileResponse("frontend/pages/dashboard.html")


@app.get("/settings")
async def settings_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login")
    return FileResponse("frontend/pages/settings.html")


@app.get("/threats")
async def threats_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login")
    return FileResponse("frontend/pages/threats.html")


@app.get("/actions")
async def actions_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login")
    return FileResponse("frontend/pages/actions.html")


@app.get("/brand-image")
async def brand_image_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login")
    return FileResponse("frontend/pages/brand-image.html")


@app.get("/negative-mentions")
async def negative_mentions_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login")
    return FileResponse("frontend/pages/negative-mentions.html")


@app.get("/reports")
async def reports_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login")
    return FileResponse("frontend/pages/reports.html")


@app.get("/history")
async def history_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login")
    return FileResponse("frontend/pages/history.html")


@app.get("/onboarding")
async def onboarding_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login")
    return FileResponse("frontend/pages/onboarding.html")


@app.get("/orgs/new")
async def new_org_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login")
    return FileResponse("frontend/pages/org_create.html")


@app.get("/orgs/join")
async def join_org_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login")
    return FileResponse("frontend/pages/join.html")
