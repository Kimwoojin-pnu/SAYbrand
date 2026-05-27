import os
from sqlalchemy.ext.asyncio import (
    create_async_engine, AsyncSession, async_sessionmaker
)
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import declarative_base

Base = declarative_base()

_DB_URL = os.environ.get("DATABASE_URL", "")

# postgresql:// → postgresql+asyncpg:// 변환
if _DB_URL.startswith("postgresql://"):
    _DB_URL = _DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

print(f"[DB] URL: {_DB_URL[:40] if _DB_URL else 'NOT SET'}")

# DATABASE_URL 없으면 engine=None (SQLite fallback 없음)
if _DB_URL and "postgresql" in _DB_URL:
    engine = create_async_engine(_DB_URL, poolclass=NullPool)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
else:
    engine = None
    AsyncSessionLocal = None


async def get_db():
    if AsyncSessionLocal is None:
        raise RuntimeError("DATABASE_URL not configured")
    async with AsyncSessionLocal() as session:
        yield session
