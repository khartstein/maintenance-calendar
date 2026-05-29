"""SQLAlchemy models. Populated by Phase 1a subagent.

Import every model module here so Alembic autogenerate sees the metadata.
"""

from app.models.household import Household
from app.models.item import Item
from app.models.magic_link_token import MagicLinkToken
from app.models.maintenance_task import MaintenanceTask
from app.models.user import User

__all__ = [
    "Household",
    "Item",
    "MagicLinkToken",
    "MaintenanceTask",
    "User",
]
