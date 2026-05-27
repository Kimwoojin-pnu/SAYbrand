import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./saybrand.db")

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Vercel 서버리스에서는 NullPool 필수
# 커넥션 풀링이 serverless 환경과 충돌함
if "sqlite" in DATABASE_URL:
    engine = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_async_engine(
        DATABASE_URL,
        poolclass=NullPool,  # ← 핵심 수정
        connect_args={
            "ssl": "require",      # Railway는 SSL 필요
            "server_settings": {
                "application_name": "saybrand_vercel",
            }
        }
    )

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
