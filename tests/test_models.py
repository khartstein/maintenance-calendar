from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Household, Item, MaintenanceTask, User


def test_household_calendar_token_default(db_session: Session) -> None:
    h = Household(name="Smith Family")
    db_session.add(h)
    db_session.commit()
    db_session.refresh(h)
    assert h.calendar_token is not None
    assert len(h.calendar_token) >= 32


def test_user_household_relationship(db_session: Session) -> None:
    h = Household(name="Doe")
    db_session.add(h)
    db_session.flush()
    u = User(household_id=h.id, email="jane@example.com")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    assert u.household is not None
    assert u.household.id == h.id
    assert u.household.name == "Doe"


def test_maintenance_task_json_roundtrip(db_session: Session) -> None:
    h = Household(name="Roe")
    db_session.add(h)
    db_session.flush()
    item = Item(household_id=h.id, name="Espresso Machine", summary="A nice machine")
    db_session.add(item)
    db_session.flush()
    supplies = [
        {"label": "Descaler", "url": "https://example.com/descaler"},
        {"label": "Backflush detergent", "url": "https://example.com/backflush"},
    ]
    videos = [
        {
            "title": "How to descale",
            "url": "https://youtube.com/watch?v=abc",
            "channel": "Coffee Channel",
        },
        {"title": "Backflush tips", "url": "https://youtube.com/watch?v=xyz", "channel": None},
    ]
    task = MaintenanceTask(
        item_id=item.id,
        title="Descale",
        description="Run descaling routine",
        dtstart=date(2026, 6, 1),
        rrule="FREQ=MONTHLY;INTERVAL=3",
        supplies=supplies,
        videos=videos,
    )
    db_session.add(task)
    db_session.commit()
    task_id = task.id

    db_session.expire_all()

    fetched = db_session.get(MaintenanceTask, task_id)
    assert fetched is not None
    assert fetched.supplies == supplies
    assert fetched.videos == videos
    assert fetched.supplies[0]["label"] == "Descaler"
    assert fetched.videos[1]["channel"] is None


def test_calendar_token_uniqueness(db_session: Session) -> None:
    h1 = Household(name="A", calendar_token="same-token-value")
    h2 = Household(name="B", calendar_token="same-token-value")
    db_session.add(h1)
    db_session.commit()
    db_session.add(h2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_item_cascade_deletes_tasks(db_session: Session) -> None:
    h = Household(name="Cascade")
    db_session.add(h)
    db_session.flush()
    item = Item(household_id=h.id, name="Lawn Mower", summary="")
    db_session.add(item)
    db_session.flush()
    t1 = MaintenanceTask(
        item_id=item.id,
        title="Sharpen blade",
        dtstart=date(2026, 7, 1),
        rrule="FREQ=YEARLY",
    )
    t2 = MaintenanceTask(
        item_id=item.id,
        title="Change oil",
        dtstart=date(2026, 7, 15),
        rrule="FREQ=YEARLY",
    )
    db_session.add_all([t1, t2])
    db_session.commit()
    task_ids = [t1.id, t2.id]

    db_session.delete(item)
    db_session.commit()

    for tid in task_ids:
        assert db_session.get(MaintenanceTask, tid) is None
