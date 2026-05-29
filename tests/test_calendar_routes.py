from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from icalendar import Calendar as ICalCalendar
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_db
from app.models import Household, Item, MaintenanceTask
from app.routers.calendar import router as calendar_router


@pytest.fixture
def cal_client(db_engine: Engine, db_session: Session) -> Iterator[TestClient]:
    app = FastAPI()
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(calendar_router)

    session_factory = sessionmaker(db_engine, expire_on_commit=False, class_=Session)

    def _override_get_db() -> Iterator[Session]:
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_unknown_token_returns_404(cal_client: TestClient) -> None:
    response = cal_client.get("/cal/no-such-token.ics")
    assert response.status_code == 404


def test_real_token_returns_calendar_with_event(
    cal_client: TestClient, db_session: Session
) -> None:
    household = Household(name="Smith", calendar_token="real-token")
    db_session.add(household)
    db_session.flush()
    item = Item(household_id=household.id, name="Espresso Machine", summary="")
    db_session.add(item)
    db_session.flush()
    task = MaintenanceTask(
        item_id=item.id,
        title="Descale",
        description="Run descaling routine",
        dtstart=date(2026, 6, 1),
        rrule="FREQ=MONTHLY;INTERVAL=2",
        supplies=[{"label": "Descaler", "url": "https://example.com/d"}],
        videos=[{"title": "How to", "url": "https://youtube.com/v"}],
    )
    db_session.add(task)
    db_session.commit()

    response = cal_client.get("/cal/real-token.ics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")

    cal = ICalCalendar.from_ical(response.text)
    events = list(cal.walk("VEVENT"))
    assert len(events) == 1
    assert "Espresso Machine" in str(events[0]["SUMMARY"])
    assert "Descale" in str(events[0]["SUMMARY"])
