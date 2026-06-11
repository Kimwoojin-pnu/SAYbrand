import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app


@pytest_asyncio.fixture(scope="module")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.parametrize("path", [
    "/products/module-a",
    "/products/module-b",
    "/products/module-c",
    "/products/threat-map",
    "/products/pipeline",
])
@pytest.mark.asyncio
async def test_product_page_returns_200(client, path):
    res = await client.get(path)
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
