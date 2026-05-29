from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.contracts import MaintenanceTaskDraft
from app.models import Item, MaintenanceTask


def list_items(db: Session, household_id: UUID) -> list[Item]:
    stmt = (
        select(Item)
        .where(Item.household_id == household_id)
        .order_by(Item.created_at.desc(), Item.name)
    )
    return list(db.execute(stmt).scalars().all())


def get_item(db: Session, household_id: UUID, item_id: UUID) -> Item | None:
    stmt = select(Item).where(Item.id == item_id, Item.household_id == household_id)
    return db.execute(stmt).scalar_one_or_none()


def create_item(
    db: Session,
    household_id: UUID,
    name: str,
    amazon_url: str | None,
    asin: str | None,
    summary: str,
) -> Item:
    item = Item(
        household_id=household_id,
        name=name,
        amazon_url=amazon_url or None,
        asin=asin or None,
        summary=summary,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, household_id: UUID, item_id: UUID) -> bool:
    item = get_item(db, household_id, item_id)
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True


def _rrule_for_cadence(draft: MaintenanceTaskDraft) -> tuple[str, str]:
    cadence = draft.cadence
    if cadence.months is not None:
        return f"FREQ=MONTHLY;INTERVAL={cadence.months}", ""
    if cadence.years is not None:
        return f"FREQ=YEARLY;INTERVAL={cadence.years}", ""
    if cadence.hours_of_use is not None:
        note = (
            f"Recommended every {cadence.hours_of_use} hours of use; "
            "usage tracking not implemented yet, defaulting to every 6 months."
        )
        return "FREQ=MONTHLY;INTERVAL=6", note
    return "FREQ=MONTHLY;INTERVAL=6", ""


def save_tasks_for_item(
    db: Session,
    item: Item,
    drafts: list[MaintenanceTaskDraft],
    default_start: date,
) -> list[MaintenanceTask]:
    db.execute(delete(MaintenanceTask).where(MaintenanceTask.item_id == item.id))
    db.flush()

    persisted: list[MaintenanceTask] = []
    for draft in drafts:
        rrule, note = _rrule_for_cadence(draft)
        description = draft.description
        if note:
            description = f"{description}\n\n{note}" if description else note
        supplies = [
            {"label": s.label, "url": str(s.amazon_url) if s.amazon_url else ""}
            for s in draft.supplies
        ]
        videos = [
            {"title": v.title, "url": str(v.url), "channel": v.channel or ""}
            for v in draft.videos
        ]
        task = MaintenanceTask(
            item_id=item.id,
            title=draft.title,
            description=description,
            dtstart=default_start,
            rrule=rrule,
            supplies=supplies,
            videos=videos,
            enabled=True,
        )
        db.add(task)
        persisted.append(task)

    db.commit()
    for task in persisted:
        db.refresh(task)
    return persisted
