from fastapi.testclient import TestClient

from app.main import app


def test_healthz() -> None:
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_index_renders() -> None:
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "Maintenance Calendar" in r.text
