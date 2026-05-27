import os
from sqlalchemy.ext.asyncio import (
    create_async_engine, AsyncSession, async_sessionmaker
)
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import declarative_base

Base = declarative_base()

_DB_URL = os.environ.get("DATABASE_URL", "")

# postgres:// 또는 postgresql:// → postgresql+asyncpg://
if _DB_URL.startswith("postgres://"):
    _DB_URL = "postgresql+asyncpg://" + _DB_URL[len("postgres://"):]
elif _DB_URL.startswith("postgresql://"):
    _DB_URL = "postgresql+asyncpg://" + _DB_URL[len("postgresql://"):]

print(f"[DB] URL: {_DB_URL[:40] if _DB_URL else 'NOT SET'}")

# asyncpg URL이 있을 때만 engine 생성, 없으면 None
if _DB_URL.startswith("postgresql+asyncpg://"):
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
