"""테스트 세션 전 DB 테이블 생성 + 시드 데이터 삽입"""
import asyncio
import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    async def _init():
        from backend.db.database import engine, Base
        from backend.db.seed import seed_mock_data
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await seed_mock_data()

    asyncio.run(_init())
