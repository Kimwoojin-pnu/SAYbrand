from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from backend.config import settings
from backend.db.database import engine, Base
from backend.db.seed import seed_mock_data
from backend.middleware.rate_limiter import rate_limit_middleware
from backend.routers import dashboard
from backend.routers import auth, billing, orgs, profile, keywords, reports, assistant, webhooks, competitor_keywords


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_mock_data()
    # 90일 초과 데이터 자동 삭제 (개인정보보호법)
    try:
        from backend.db.database import AsyncSessionLocal
        from backend.services.data_retention import purge_expired_data
        async with AsyncSessionLocal() as db:
            await purge_expired_data(db)
    except Exception:
        pass  # 시작 실패가 서버 기동을 막지 않도록
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
