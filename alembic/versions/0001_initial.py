"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-29 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "household",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("calendar_token", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("calendar_token"),
    )
    op.create_index(
        "ix_household_calendar_token", "household", ["calendar_token"], unique=True
    )

    op.create_table(
        "user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_user_household_id", "user", ["household_id"], unique=False)

    op.create_table(
        "item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("amazon_url", sa.String(), nullable=True),
        sa.Column("asin", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_item_household_id", "item", ["household_id"], unique=False)
    op.create_index("ix_item_asin", "item", ["asin"], unique=False)

    op.create_table(
        "maintenance_task",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("dtstart", sa.Date(), nullable=False),
        sa.Column("rrule", sa.Text(), nullable=False),
        sa.Column("supplies", sa.JSON(), nullable=False),
        sa.Column("videos", sa.JSON(), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["item_id"], ["item.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_maintenance_task_item_id", "maintenance_task", ["item_id"], unique=False
    )

    op.create_table(
        "magic_link_token",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_magic_link_token_email", "magic_link_token", ["email"], unique=False
    )
    op.create_index(
        "ix_magic_link_token_token_hash",
        "magic_link_token",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_magic_link_token_expires_at",
        "magic_link_token",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_magic_link_token_expires_at", table_name="magic_link_token")
    op.drop_index("ix_magic_link_token_token_hash", table_name="magic_link_token")
    op.drop_index("ix_magic_link_token_email", table_name="magic_link_token")
    op.drop_table("magic_link_token")

    op.drop_index("ix_maintenance_task_item_id", table_name="maintenance_task")
    op.drop_table("maintenance_task")

    op.drop_index("ix_item_asin", table_name="item")
    op.drop_index("ix_item_household_id", table_name="item")
    op.drop_table("item")

    op.drop_index("ix_user_household_id", table_name="user")
    op.drop_table("user")

    op.drop_index("ix_household_calendar_token", table_name="household")
    op.drop_table("household")
