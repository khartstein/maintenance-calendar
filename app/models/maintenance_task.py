from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.item import Item


class MaintenanceTask(Base):
    __tablename__ = "maintenance_task"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(), sa.ForeignKey("item.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(sa.String(), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text(), nullable=False, default="")
    dtstart: Mapped[date] = mapped_column(sa.Date(), nullable=False)
    rrule: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    supplies: Mapped[list[dict[str, Any]]] = mapped_column(
        sa.JSON(), nullable=False, default=list
    )
    videos: Mapped[list[dict[str, Any]]] = mapped_column(sa.JSON(), nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(
        sa.Boolean(), nullable=False, default=True, server_default=sa.true()
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    item: Mapped[Item] = relationship(back_populates="tasks")
