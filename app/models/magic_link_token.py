from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MagicLinkToken(Base):
    __tablename__ = "magic_link_token"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(sa.String(), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(
        sa.String(), unique=True, index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, index=True
    )
    used_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
