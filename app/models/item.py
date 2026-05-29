from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.household import Household
    from app.models.maintenance_task import MaintenanceTask


class Item(Base):
    __tablename__ = "item"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(), sa.ForeignKey("household.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(sa.String(), nullable=False)
    amazon_url: Mapped[str | None] = mapped_column(sa.String(), nullable=True)
    asin: Mapped[str | None] = mapped_column(sa.String(), nullable=True, index=True)
    summary: Mapped[str] = mapped_column(sa.Text(), nullable=False, default="")
    notes: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    household: Mapped[Household] = relationship(back_populates="items")
    tasks: Mapped[list[MaintenanceTask]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )
