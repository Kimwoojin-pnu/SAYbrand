import os
print(f"[STARTUP] DATABASE_URL prefix: {os.environ.get('DATABASE_URL', 'NOT SET')[:30]}")

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from backend.config import settings
from backend.middleware.rate_limiter import rate_limit_middleware
from backend.routers import dashboard
from backend.routers import auth, billing, orgs, profile, keywords, reports, assistant, webhooks, competitor_keywords, support


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.db.database import engine, Base
    if engine is not None:
        db_url = os.environ.get("DATABASE_URL", "")
        if "postgresql" in db_url or "postgres" in db_url:
            from sqlalchemy import text
            _migrations = [
                "ALTER TABLE threats ADD COLUMN IF NOT EXISTS resolution_type VARCHAR(50)",
                "ALTER TABLE threats ADD COLUMN IF NOT EXISTS resolution_method VARCHAR(200)",
                "ALTER TABLE threats ADD COLUMN IF NOT EXISTS resolution_note TEXT",
                """CREATE TABLE IF NOT EXISTS support_posts (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    user_name VARCHAR(200) DEFAULT '',
                    title VARCHAR(200) NOT NULL,
                    content TEXT NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    admin_reply TEXT,
                    admin_reply_by VARCHAR(200),
                    answered_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )""",
            ]
            async with engine.begin() as conn:
                for stmt in _migrations:
                    await conn.execute(text(stmt))
        else:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
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
app.include_router(support.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/saybrand-logo.png")
async def saybrand_logo():
    return FileResponse("saybrand-logo.png", media_type="image/png")


@app.get("/saybrand-logo2.png")
async def saybrand_logo2():
    return FileResponse("saybrand-logo2.png", media_type="image/png")


@app.get("/manifest.json")
async def pwa_manifest():
    return FileResponse("frontend/manifest.json", media_type="application/manifest+json")


@app.get("/sw.js")
async def pwa_service_worker():
    return FileResponse(
        "frontend/sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


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


@app.get("/products")
async def products_page():
    return FileResponse("frontend/pages/products/index.html")


@app.get("/support")
async def support_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login")
    return FileResponse("frontend/pages/support.html")


@app.get("/about")
async def about_page():
    return FileResponse("frontend/pages/about.html")


@app.get("/careers")
async def careers_page():
    return FileResponse("frontend/pages/careers.html")


@app.get("/blog")
async def blog_page():
    return FileResponse("frontend/pages/blog.html")


@app.get("/press")
async def press_page():
    return FileResponse("frontend/pages/press.html")


@app.get("/terms")
async def terms_page():
    return FileResponse("frontend/pages/terms.html")


@app.get("/privacy")
async def privacy_page():
    return FileResponse("frontend/pages/privacy.html")


@app.get("/cookies")
async def cookies_page():
    return FileResponse("frontend/pages/cookies.html")


@app.get("/security")
async def security_page():
    return FileResponse("frontend/pages/security.html")
