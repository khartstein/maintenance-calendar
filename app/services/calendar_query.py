from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.household import Household
from app.models.item import Item
from app.models.maintenance_task import MaintenanceTask


def household_by_token(db: Session, token: str) -> Household | None:
    stmt = select(Household).where(Household.calendar_token == token)
    return db.execute(stmt).scalar_one_or_none()


def enabled_tasks_for_household(
    db: Session, household_id: UUID
) -> list[tuple[Item, MaintenanceTask]]:
    stmt = (
        select(MaintenanceTask)
        .join(Item, MaintenanceTask.item_id == Item.id)
        .where(Item.household_id == household_id)
        .where(MaintenanceTask.enabled.is_(True))
        .options(joinedload(MaintenanceTask.item))
        .order_by(MaintenanceTask.dtstart, MaintenanceTask.title)
    )
    tasks = db.execute(stmt).scalars().all()
    return [(task.item, task) for task in tasks]
