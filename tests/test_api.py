import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app


@pytest_asyncio.fixture(scope="module")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_stats(client):
    res = await client.get("/api/dashboard/stats")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "critical" in data


@pytest.mark.asyncio
async def test_risk_score(client):
    res = await client.get("/api/dashboard/risk-score")
    assert res.status_code == 200
    data = res.json()
    assert "overall" in data
    assert "level" in data
    assert data["level"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW")


@pytest.mark.asyncio
async def test_threats_list(client):
    res = await client.get("/api/dashboard/threats")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_threats_severity_filter(client):
    res = await client.get("/api/dashboard/threats?severity=critical")
    assert res.status_code == 200
    data = res.json()
    assert all(t["severity"] == "critical" for t in data["items"])


@pytest.mark.asyncio
async def test_alerts(client):
    res = await client.get("/api/dashboard/alerts")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_status_update(client):
    threats = (await client.get("/api/dashboard/threats")).json()
    threat_id = threats["items"][0]["id"]

    res = await client.patch(
        f"/api/dashboard/threats/{threat_id}/status",
        json={"status": "reviewing"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "reviewing"


@pytest.mark.asyncio
async def test_status_update_invalid(client):
    threats = (await client.get("/api/dashboard/threats")).json()
    threat_id = threats["items"][0]["id"]

    res = await client.patch(
        f"/api/dashboard/threats/{threat_id}/status",
        json={"status": "invalid_status"},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_threat_not_found(client):
    res = await client.patch(
        "/api/dashboard/threats/99999/status",
        json={"status": "resolved"},
    )
    assert res.status_code == 404
