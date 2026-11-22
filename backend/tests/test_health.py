from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_api_and_db_ok():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "db": "ok"}


def test_docs_disabled_by_default():
    # DEBUG defaults to false, so the interactive API docs must not be exposed.
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
