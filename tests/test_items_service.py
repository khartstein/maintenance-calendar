from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.contracts import Cadence, MaintenanceTaskDraft, SupplySuggestion, VideoSuggestion
from app.models import Household, MaintenanceTask
from app.services.items import (
    create_item,
    delete_item,
    get_item,
    list_items,
    save_tasks_for_item,
)


@pytest.fixture
def household(db_session: Session) -> Household:
    h = Household(name="Household")
    db_session.add(h)
    db_session.commit()
    db_session.refresh(h)
    return h


def test_create_and_list_items(db_session: Session, household: Household) -> None:
    create_item(
        db_session,
        household_id=household.id,
        name="Lawn mower",
        amazon_url=None,
        asin=None,
        summary="Push mower",
    )
    create_item(
        db_session,
        household_id=household.id,
        name="Espresso machine",
        amazon_url="https://www.amazon.com/x",
        asin="B0X",
        summary="Dual boiler",
    )
    items = list_items(db_session, household.id)
    assert {i.name for i in items} == {"Lawn mower", "Espresso machine"}


def test_list_items_scoped_to_household(db_session: Session, household: Household) -> None:
    other = Household(name="Other")
    db_session.add(other)
    db_session.commit()
    create_item(
        db_session, household_id=household.id, name="Mine", amazon_url=None, asin=None, summary=""
    )
    create_item(
        db_session, household_id=other.id, name="Theirs", amazon_url=None, asin=None, summary=""
    )
    assert [i.name for i in list_items(db_session, household.id)] == ["Mine"]


def test_get_item_returns_none_for_wrong_household(
    db_session: Session, household: Household
) -> None:
    item = create_item(
        db_session, household_id=household.id, name="X", amazon_url=None, asin=None, summary=""
    )
    other = Household(name="Other")
    db_session.add(other)
    db_session.commit()
    assert get_item(db_session, other.id, item.id) is None
    assert get_item(db_session, household.id, uuid4()) is None


def test_delete_item(db_session: Session, household: Household) -> None:
    item = create_item(
        db_session, household_id=household.id, name="X", amazon_url=None, asin=None, summary=""
    )
    assert delete_item(db_session, household.id, item.id) is True
    assert delete_item(db_session, household.id, item.id) is False


def _draft(title: str, cadence: Cadence) -> MaintenanceTaskDraft:
    return MaintenanceTaskDraft(
        title=title,
        description=f"Do the {title}",
        cadence=cadence,
        supplies=[
            SupplySuggestion(
                label="Descaler",
                search_query="descaler",
                amazon_url="https://www.amazon.com/s?k=descaler",
            )
        ],
        videos=[
            VideoSuggestion(
                title="How to",
                url="https://www.youtube.com/watch?v=abc",
                channel="Channel",
            )
        ],
        video_search_queries=["how to descale"],
    )


def test_save_tasks_for_item_emits_monthly_rrule(
    db_session: Session, household: Household
) -> None:
    item = create_item(
        db_session, household_id=household.id, name="Espresso", amazon_url=None, asin=None, summary=""
    )
    drafts = [_draft("Descale", Cadence(months=2))]
    tasks = save_tasks_for_item(db_session, item, drafts, default_start=date(2026, 6, 1))
    assert len(tasks) == 1
    assert tasks[0].rrule == "FREQ=MONTHLY;INTERVAL=2"
    assert tasks[0].dtstart == date(2026, 6, 1)
    assert tasks[0].supplies[0]["label"] == "Descaler"
    assert tasks[0].videos[0]["url"] == "https://www.youtube.com/watch?v=abc"


def test_save_tasks_for_item_emits_yearly_rrule(
    db_session: Session, household: Household
) -> None:
    item = create_item(
        db_session, household_id=household.id, name="Mower", amazon_url=None, asin=None, summary=""
    )
    tasks = save_tasks_for_item(
        db_session,
        item,
        [_draft("Oil change", Cadence(years=1))],
        default_start=date(2026, 6, 1),
    )
    assert tasks[0].rrule == "FREQ=YEARLY;INTERVAL=1"


def test_save_tasks_for_item_falls_back_for_hours_of_use(
    db_session: Session, household: Household
) -> None:
    item = create_item(
        db_session, household_id=household.id, name="Mower", amazon_url=None, asin=None, summary=""
    )
    tasks = save_tasks_for_item(
        db_session,
        item,
        [_draft("Air filter", Cadence(hours_of_use=50))],
        default_start=date(2026, 6, 1),
    )
    assert tasks[0].rrule == "FREQ=MONTHLY;INTERVAL=6"
    assert "50 hours of use" in tasks[0].description


def test_save_tasks_for_item_is_idempotent(
    db_session: Session, household: Household
) -> None:
    item = create_item(
        db_session, household_id=household.id, name="Espresso", amazon_url=None, asin=None, summary=""
    )
    save_tasks_for_item(
        db_session,
        item,
        [_draft("Descale", Cadence(months=2)), _draft("Backflush", Cadence(months=1))],
        default_start=date(2026, 6, 1),
    )
    save_tasks_for_item(
        db_session,
        item,
        [_draft("Descale", Cadence(months=3))],
        default_start=date(2026, 7, 1),
    )
    remaining = (
        db_session.query(MaintenanceTask).filter(MaintenanceTask.item_id == item.id).all()
    )
    assert len(remaining) == 1
    assert remaining[0].rrule == "FREQ=MONTHLY;INTERVAL=3"
