from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone

from icalendar import Calendar as ICalCalendar

from app.models.household import Household
from app.models.item import Item
from app.models.maintenance_task import MaintenanceTask
from app.services.ics import build_calendar


def _household(name: str = "Default") -> Household:
    return Household(id=uuid.uuid4(), name=name, calendar_token="tok-" + uuid.uuid4().hex)


def _item(household: Household, name: str = "Espresso Machine") -> Item:
    return Item(id=uuid.uuid4(), household_id=household.id, name=name, summary="")


def _task(
    item: Item,
    title: str = "Descale",
    dtstart: date = date(2026, 6, 1),
    rrule: str = "FREQ=MONTHLY;INTERVAL=2",
    description: str = "Run descaling routine",
    supplies: list[dict[str, object]] | None = None,
    videos: list[dict[str, object]] | None = None,
    enabled: bool = True,
) -> MaintenanceTask:
    return MaintenanceTask(
        id=uuid.uuid4(),
        item_id=item.id,
        title=title,
        description=description,
        dtstart=dtstart,
        rrule=rrule,
        supplies=supplies or [],
        videos=videos or [],
        enabled=enabled,
    )


def test_empty_task_list_yields_valid_calendar_with_no_events() -> None:
    household = _household()
    text = build_calendar(household, [])
    cal = ICalCalendar.from_ical(text)
    assert cal.get("VERSION") == "2.0"
    assert str(cal.get("PRODID")) == "-//maintenance-calendar//EN"
    events = [c for c in cal.walk("VEVENT")]
    assert events == []


def test_single_all_day_monthly_task_roundtrips() -> None:
    household = _household()
    item = _item(household, name="Espresso Machine")
    supplies = [
        {"label": "Descaler", "url": "https://example.com/descaler"},
        {"label": "Backflush detergent", "url": "https://example.com/backflush"},
    ]
    videos = [
        {"title": "How to descale", "url": "https://youtube.com/watch?v=abc"},
        {"title": "Backflush tips", "url": "https://youtube.com/watch?v=xyz"},
    ]
    task = _task(item, supplies=supplies, videos=videos)

    text = build_calendar(household, [(item, task)])
    cal = ICalCalendar.from_ical(text)
    events = list(cal.walk("VEVENT"))
    assert len(events) == 1
    ev = events[0]

    assert str(ev["UID"]) == f"{task.id}@maintenance-calendar"
    assert ev["DTSTART"].dt == date(2026, 6, 1)
    assert ev["DTEND"].dt == date(2026, 6, 2)

    summary = str(ev["SUMMARY"])
    assert "Espresso Machine" in summary
    assert "Descale" in summary

    rrule = ev["RRULE"]
    assert rrule["FREQ"] == ["MONTHLY"]
    assert rrule["INTERVAL"] == [2]

    description = str(ev["DESCRIPTION"])
    for entry in supplies:
        assert entry["label"] in description
        assert entry["url"] in description
    for entry in videos:
        assert entry["title"] in description
        assert entry["url"] in description


def test_disabled_tasks_are_skipped() -> None:
    household = _household()
    item = _item(household)
    enabled_task = _task(item, title="Enabled")
    disabled_task = _task(item, title="Disabled", dtstart=date(2026, 7, 1), enabled=False)

    text = build_calendar(household, [(item, enabled_task), (item, disabled_task)])
    cal = ICalCalendar.from_ical(text)
    events = list(cal.walk("VEVENT"))
    assert len(events) == 1
    assert "Enabled" in str(events[0]["SUMMARY"])


def test_multiple_tasks_yield_stable_order() -> None:
    household = _household()
    item = _item(household, name="Mower")
    later = _task(item, title="Sharpen", dtstart=date(2026, 8, 1))
    earlier = _task(item, title="Oil change", dtstart=date(2026, 7, 15))
    same_day_b = _task(item, title="Battery", dtstart=date(2026, 7, 15))

    text = build_calendar(
        household, [(item, later), (item, earlier), (item, same_day_b)]
    )
    cal = ICalCalendar.from_ical(text)
    events = list(cal.walk("VEVENT"))
    dates_and_titles = [(ev["DTSTART"].dt, str(ev["SUMMARY"])) for ev in events]
    assert dates_and_titles[0][0] == date(2026, 7, 15)
    assert "Battery" in dates_and_titles[0][1]
    assert dates_and_titles[1][0] == date(2026, 7, 15)
    assert "Oil change" in dates_and_titles[1][1]
    assert dates_and_titles[2][0] == date(2026, 8, 1)
    assert "Sharpen" in dates_and_titles[2][1]


def test_description_omits_empty_sections() -> None:
    household = _household()
    item = _item(household)
    task = _task(item, description="Just the description", supplies=[], videos=[])

    text = build_calendar(household, [(item, task)])
    cal = ICalCalendar.from_ical(text)
    ev = next(iter(cal.walk("VEVENT")))
    description = str(ev["DESCRIPTION"])
    assert "Just the description" in description
    assert "Supplies:" not in description
    assert "How-to videos:" not in description


def test_dtend_is_dtstart_plus_one_day() -> None:
    household = _household()
    item = _item(household)
    task = _task(item, dtstart=date(2026, 12, 31))

    text = build_calendar(household, [(item, task)])
    cal = ICalCalendar.from_ical(text)
    ev = next(iter(cal.walk("VEVENT")))
    assert ev["DTEND"].dt - ev["DTSTART"].dt == timedelta(days=1)


def test_calname_includes_household_name_when_non_default() -> None:
    household = _household(name="Smith Family")
    text = build_calendar(household, [])
    cal = ICalCalendar.from_ical(text)
    assert "Smith Family" in str(cal.get("X-WR-CALNAME"))


_DTSTAMP_RE = re.compile(r"^\d{8}T\d{6}Z$")


def test_every_vevent_has_dtstamp_in_basic_utc_format() -> None:
    household = _household()
    item = _item(household, name="Mower")
    tasks = [
        (item, _task(item, title="Sharpen", dtstart=date(2026, 8, 1))),
        (item, _task(item, title="Oil change", dtstart=date(2026, 7, 15))),
    ]

    text = build_calendar(household, tasks)
    dtstamp_lines = [
        line for line in text.splitlines() if line.startswith("DTSTAMP:")
    ]
    assert len(dtstamp_lines) == 2
    for line in dtstamp_lines:
        assert _DTSTAMP_RE.match(line.split(":", 1)[1])

    cal = ICalCalendar.from_ical(text)
    events = list(cal.walk("VEVENT"))
    assert len(events) == 2
    for ev in events:
        assert ev.get("DTSTAMP") is not None


def test_dtstamp_is_overridable_for_deterministic_output() -> None:
    household = _household()
    item = _item(household)
    task = _task(item)
    fixed = datetime(2026, 5, 29, 19, 30, 45, tzinfo=timezone.utc)

    text = build_calendar(household, [(item, task)], now=fixed)
    assert "DTSTAMP:20260529T193045Z" in text
