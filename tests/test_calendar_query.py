from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models import Household, Item, MaintenanceTask
from app.services.calendar_query import enabled_tasks_for_household, household_by_token


def test_household_by_token_unknown_returns_none(db_session: Session) -> None:
    h = Household(name="A")
    db_session.add(h)
    db_session.commit()
    assert household_by_token(db_session, "does-not-exist") is None


def test_household_by_token_returns_matching_household(db_session: Session) -> None:
    h = Household(name="A", calendar_token="known-token")
    db_session.add(h)
    db_session.commit()
    result = household_by_token(db_session, "known-token")
    assert result is not None
    assert result.id == h.id


def test_enabled_tasks_scoped_to_household_and_filtered(db_session: Session) -> None:
    h1 = Household(name="One", calendar_token="t1")
    h2 = Household(name="Two", calendar_token="t2")
    db_session.add_all([h1, h2])
    db_session.flush()

    item1 = Item(household_id=h1.id, name="Item1", summary="")
    item2 = Item(household_id=h2.id, name="Item2", summary="")
    db_session.add_all([item1, item2])
    db_session.flush()

    enabled_task = MaintenanceTask(
        item_id=item1.id,
        title="Enabled",
        dtstart=date(2026, 6, 1),
        rrule="FREQ=MONTHLY",
        enabled=True,
    )
    disabled_task = MaintenanceTask(
        item_id=item1.id,
        title="Disabled",
        dtstart=date(2026, 6, 1),
        rrule="FREQ=MONTHLY",
        enabled=False,
    )
    other_household_task = MaintenanceTask(
        item_id=item2.id,
        title="Other",
        dtstart=date(2026, 6, 1),
        rrule="FREQ=MONTHLY",
        enabled=True,
    )
    db_session.add_all([enabled_task, disabled_task, other_household_task])
    db_session.commit()

    pairs = enabled_tasks_for_household(db_session, h1.id)
    titles = [task.title for _, task in pairs]
    assert titles == ["Enabled"]
    assert pairs[0][0].id == item1.id
