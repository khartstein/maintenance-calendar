from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Household, User
from app.services.items import create_item


def test_index_unauthenticated_shows_sign_in_cta(ui_client: TestClient) -> None:
    r = ui_client.get("/")
    assert r.status_code == 200
    assert "Sign in" in r.text
    assert "/auth/login" in r.text


def test_index_authenticated_no_items_shows_empty_state(
    signed_in: tuple[Household, User, TestClient],
) -> None:
    _, _, client = signed_in
    r = client.get("/")
    assert r.status_code == 200
    assert "Add" in r.text


def test_index_authenticated_lists_items(
    db_session: Session, signed_in: tuple[Household, User, TestClient]
) -> None:
    household, _, client = signed_in
    create_item(
        db_session,
        household_id=household.id,
        name="Espresso machine",
        amazon_url=None,
        asin=None,
        summary="Dual boiler.",
    )
    r = client.get("/")
    assert r.status_code == 200
    assert "Espresso machine" in r.text


def test_new_item_form_requires_auth(ui_client: TestClient) -> None:
    r = ui_client.get("/items/new")
    assert r.status_code == 401


def test_new_item_form_renders_when_signed_in(
    signed_in: tuple[Household, User, TestClient],
) -> None:
    _, _, client = signed_in
    r = client.get("/items/new")
    assert r.status_code == 200
    assert 'name="name"' in r.text


def test_delete_item_route(
    db_session: Session, signed_in: tuple[Household, User, TestClient]
) -> None:
    household, _, client = signed_in
    item = create_item(
        db_session, household_id=household.id, name="X", amazon_url=None, asin=None, summary=""
    )
    r = client.post(f"/items/{item.id}/delete", follow_redirects=False)
    assert r.status_code in (302, 303)
    from app.services.items import get_item

    assert get_item(db_session, household.id, item.id) is None
