from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
from typing import Any

from ics.grammar.parse import Container, ContentLine
from ics.utils import escape_string

from app.models.household import Household
from app.models.item import Item
from app.models.maintenance_task import MaintenanceTask

_DEFAULT_CALNAME = "Household maintenance"
_DEFAULT_HOUSEHOLD_NAME = "Default"


def build_calendar(
    household: Household,
    tasks: Iterable[tuple[Item, MaintenanceTask]],
) -> str:
    cal = Container("VCALENDAR")
    cal.append(ContentLine("VERSION", value="2.0"))
    cal.append(ContentLine("PRODID", value="-//maintenance-calendar//EN"))
    cal.append(ContentLine("X-WR-CALNAME", value=_calname(household)))
    cal.append(ContentLine("X-WR-TIMEZONE", value="UTC"))

    enabled = [(item, task) for item, task in tasks if task.enabled]
    enabled.sort(key=lambda pair: (pair[1].dtstart, pair[1].title))

    for item, task in enabled:
        cal.append(_event_container(item, task))

    return str(cal) + "\r\n"


def _calname(household: Household) -> str:
    if household.name and household.name != _DEFAULT_HOUSEHOLD_NAME:
        return f"{_DEFAULT_CALNAME} ({household.name})"
    return _DEFAULT_CALNAME


def _event_container(item: Item, task: MaintenanceTask) -> Container:
    event = Container("VEVENT")
    event.append(ContentLine("UID", value=f"{task.id}@maintenance-calendar"))
    event.append(
        ContentLine(
            "DTSTART",
            params={"VALUE": ["DATE"]},
            value=task.dtstart.strftime("%Y%m%d"),
        )
    )
    event.append(
        ContentLine(
            "DTEND",
            params={"VALUE": ["DATE"]},
            value=(task.dtstart + timedelta(days=1)).strftime("%Y%m%d"),
        )
    )
    event.append(
        ContentLine(
            "SUMMARY",
            value=escape_string(f"{item.name} — {task.title}"),
        )
    )
    if task.rrule:
        event.append(ContentLine("RRULE", value=task.rrule))
    description = _build_description(task)
    if description:
        event.append(ContentLine("DESCRIPTION", value=escape_string(description)))
    return event


def _build_description(task: MaintenanceTask) -> str:
    sections: list[str] = []
    if task.description:
        sections.append(task.description)

    supply_lines = _format_links(task.supplies, "label", "url")
    if supply_lines:
        sections.append("Supplies:\n" + "\n".join(supply_lines))

    video_lines = _format_links(task.videos, "title", "url")
    if video_lines:
        sections.append("How-to videos:\n" + "\n".join(video_lines))

    return "\n\n".join(sections)


def _format_links(entries: list[dict[str, Any]], label_key: str, url_key: str) -> list[str]:
    lines: list[str] = []
    for entry in entries:
        label = entry.get(label_key)
        url = entry.get(url_key)
        if not label or not url:
            continue
        lines.append(f"- {label}: {url}")
    return lines
