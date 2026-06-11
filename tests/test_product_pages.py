import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app


@pytest_asyncio.fixture(scope="module")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_products_page_returns_200(client):
    res = await client.get("/products")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]


@pytest.mark.parametrize("panel_id", [
    "panel-module-a",
    "panel-module-b",
    "panel-module-c",
    "panel-threat-map",
    "panel-pipeline",
])
@pytest.mark.asyncio
async def test_products_page_contains_all_panels(client, panel_id):
    res = await client.get("/products")
    assert res.status_code == 200
    assert f'id="{panel_id}"' in res.text
