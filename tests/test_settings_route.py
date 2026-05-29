from __future__ import annotations

from fastapi.testclient import TestClient

from app.models import Household, User


def test_settings_requires_auth(ui_client: TestClient) -> None:
    r = ui_client.get("/settings")
    assert r.status_code == 401


def test_settings_shows_webcal_url_and_email(
    signed_in: tuple[Household, User, TestClient],
) -> None:
    household, user, client = signed_in
    r = client.get("/settings")
    assert r.status_code == 200
    body = r.text
    assert user.email in body
    assert household.calendar_token in body
    assert "webcal://" in body
