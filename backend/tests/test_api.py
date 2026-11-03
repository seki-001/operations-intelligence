from fastapi.testclient import TestClient


def test_health_is_public(client):
    assert TestClient(client.app).get("/health").json() == {"status": "ok"}


def test_api_requires_key(client):
    anon = TestClient(client.app)
    assert anon.get("/api/sync/status").status_code == 401
    assert anon.get("/api/sync/status", headers={"X-API-Key": "wrong"}).status_code == 401


def test_endpoints_before_first_sync(client):
    assert client.get("/api/overview").status_code == 409
    assert client.get("/api/sync/status").json()["current"] is None


def test_full_flow(client):
    sync = client.post("/api/sync").json()
    assert sync["attempt"]["status"] == "success"
    assert sync["attempt"]["rows_rejected"] == 5  # the deliberate errors in the synthetic data

    overview = client.get("/api/overview").json()
    statements = " ".join(f["statement"] for f in overview["findings"])
    assert "Lakeshore" in statements and "Market Town" in statements

    dq = client.get("/api/data-quality").json()
    assert {i["severity"] for i in dq["issues"]} == {"error", "warning"}

    trend = client.get("/api/trends", params={"metric": "uptime_pct"}).json()
    assert trend["series"] and "LAK" in trend["series"][-1]
    assert client.get("/api/trends", params={"metric": "nope"}).status_code == 422

    report = client.post("/api/reports/summary", json={"period_days": 7}).json()
    assert report["review_status"] == "pending_review"
    assert report["is_ai_generated"] is False

    reviewed = client.post(f"/api/reports/{report['id']}/review",
                           json={"decision": "approved", "reviewer": "FP&A Lead"}).json()
    assert reviewed["review_status"] == "approved" and reviewed["reviewed_by"] == "FP&A Lead"
    again = client.post(f"/api/reports/{report['id']}/review", json={"decision": "rejected", "reviewer": "X Y"})
    assert again.status_code == 409


def test_failed_sync_keeps_last_good_snapshot(client, monkeypatch):
    first = client.post("/api/sync").json()["attempt"]
    monkeypatch.setenv("CSV_PATH", "/nonexistent/file.csv")
    from app.core.config import get_settings
    get_settings.cache_clear()

    failed = client.post("/api/sync").json()
    assert failed["attempt"]["status"] == "failed"
    assert "not found" in failed["attempt"]["error"]
    assert failed["current"]["id"] == first["id"]  # dashboard still on the good data

    status = client.get("/api/sync/status").json()
    assert status["latest_attempt"]["status"] == "failed"
    assert client.get("/api/overview").status_code == 200


def test_misconfigured_google_source_fails_cleanly(client, monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "google_sheets")
    monkeypatch.setenv("GOOGLE_SHEET_ID", "")
    from app.core.config import get_settings
    get_settings.cache_clear()
    result = client.post("/api/sync").json()
    assert result["attempt"]["status"] == "failed"
    assert "GOOGLE_SHEET_ID" in result["attempt"]["error"]


def test_production_without_key_refuses(client, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("API_KEY", "")
    from app.core.config import get_settings
    get_settings.cache_clear()
    assert TestClient(client.app).get("/api/sync/status").status_code == 503
