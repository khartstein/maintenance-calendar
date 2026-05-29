from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import SESSION_COOKIE_NAME, get_optional_user
from app.models import User
from app.routers.auth import router as auth_router
from app.services.auth import issue_magic_link


def test_request_link_returns_partial(client: TestClient) -> None:
    response = client.post("/auth/request", data={"email": "user@example.com"})
    assert response.status_code == 200
    assert "Check your email" in response.text


def test_verify_redirects_and_sets_cookie(
    client: TestClient, db_session: Session
) -> None:
    raw, _ = issue_magic_link(db_session, "user@example.com")
    response = client.get(f"/auth/verify?token={raw}", follow_redirects=False)
    assert response.status_code in (303, 307)
    assert response.headers["location"] == "/"
    assert SESSION_COOKIE_NAME in response.cookies


@pytest.fixture
def whoami_client(db_session: Session) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(auth_router)

    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    @app.get("/whoami")
    def whoami(user: User | None = Depends(get_optional_user)) -> dict[str, str | None]:
        return {"email": user.email if user else None}

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_session_cookie_round_trips_through_get_optional_user(
    whoami_client: TestClient, db_session: Session
) -> None:
    raw, _ = issue_magic_link(db_session, "round@example.com")
    verify_resp = whoami_client.get(
        f"/auth/verify?token={raw}", follow_redirects=False
    )
    assert SESSION_COOKIE_NAME in verify_resp.cookies
    whoami_resp = whoami_client.get("/whoami")
    assert whoami_resp.status_code == 200
    assert whoami_resp.json() == {"email": "round@example.com"}


def test_verify_failed_renders_reason(client: TestClient) -> None:
    response = client.get("/auth/verify?token=not-a-real-token")
    assert response.status_code == 400
    assert "invalid" in response.text
