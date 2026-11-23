import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)


@pytest.mark.parametrize("value", [None, "", "short", "change-me-generate-with-python-secrets"])
def test_startup_refuses_missing_short_or_placeholder_secret(value):
    with pytest.raises(RuntimeError):
        config.validate_secret("JWT_SECRET", value, debug=False)


def test_debug_replaces_weak_secret_with_random_one():
    a = config.validate_secret("JWT_SECRET", None, debug=True)
    assert len(a) >= config.MIN_SECRET_LENGTH


def test_good_secret_is_accepted():
    good = "x" * 40
    assert config.validate_secret("JWT_SECRET", good, debug=False) == good


def test_security_headers_and_no_store():
    res = client.get("/api/health")
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["referrer-policy"] == "no-referrer"
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["cache-control"] == "no-store"


def test_docs_are_off_by_default():
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_unknown_route_uses_standard_error_shape():
    res = client.get("/api/nope")
    assert res.status_code == 404
    assert res.json() == {"error": "not_found", "message": "Not found."}


def test_unhandled_error_is_generic_500():
    # Same stack as the real app: handlers + middleware, plus a route that blows up.
    from app.main import harden_and_log

    boom = FastAPI()
    boom.middleware("http")(harden_and_log)

    @boom.get("/api/boom")
    def _boom():
        raise RuntimeError("secret internal detail")

    res = TestClient(boom).get("/api/boom")
    assert res.status_code == 500
    assert res.json() == {"error": "server_error", "message": "Something went wrong."}
    assert "secret" not in res.text


def test_liveness_endpoint_reports_api_and_db_ok():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "db": "ok"}
