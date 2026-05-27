import os
from sqlalchemy.ext.asyncio import (
    create_async_engine, AsyncSession, async_sessionmaker
)
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# 환경변수에서 직접 읽기
_DB_URL = os.environ.get("DATABASE_URL", "")

# postgresql:// → postgresql+asyncpg:// 변환
if _DB_URL.startswith("postgresql://"):
    _DB_URL = _DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# DATABASE_URL 없으면 /tmp SQLite 사용
if not _DB_URL:
    _DB_URL = "sqlite+aiosqlite:////tmp/saybrand.db"

print(f"[DB] Using: {_DB_URL[:40]}...")

# 엔진 생성
if "sqlite" in _DB_URL:
    engine = create_async_engine(
        _DB_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_async_engine(
        _DB_URL,
        poolclass=NullPool,
    )

AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
