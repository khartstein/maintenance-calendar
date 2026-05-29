from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.item import Item
    from app.models.user import User


class Household(Base):
    __tablename__ = "household"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(), nullable=False)
    calendar_token: Mapped[str] = mapped_column(
        sa.String(),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: secrets.token_urlsafe(24),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    users: Mapped[list[User]] = relationship(
        back_populates="household", cascade="all, delete-orphan"
    )
    items: Mapped[list[Item]] = relationship(
        back_populates="household", cascade="all, delete-orphan"
    )
