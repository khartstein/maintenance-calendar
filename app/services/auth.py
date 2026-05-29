from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Household, MagicLinkToken, User

_SESSION_SALT = "session-v1"


class MagicLinkError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class InvalidMagicLinkError(MagicLinkError):
    def __init__(self) -> None:
        super().__init__("invalid")


class UsedMagicLinkError(MagicLinkError):
    def __init__(self) -> None:
        super().__init__("used")


class ExpiredMagicLinkError(MagicLinkError):
    def __init__(self) -> None:
        super().__init__("expired")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_magic_link(
    db: Session, email: str, *, ttl_minutes: int = 15
) -> tuple[str, MagicLinkToken]:
    raw_token = secrets.token_urlsafe(32)
    row = MagicLinkToken(
        email=email.strip().lower(),
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return raw_token, row


def verify_magic_link(db: Session, raw_token: str) -> User:
    if not raw_token:
        raise InvalidMagicLinkError()
    token_hash = hash_token(raw_token)
    row = db.execute(
        select(MagicLinkToken).where(MagicLinkToken.token_hash == token_hash)
    ).scalar_one_or_none()
    if row is None:
        raise InvalidMagicLinkError()
    if row.used_at is not None:
        raise UsedMagicLinkError()
    expires_at = _as_utc(row.expires_at)
    if expires_at <= datetime.now(timezone.utc):
        raise ExpiredMagicLinkError()

    row.used_at = datetime.now(timezone.utc)

    household = db.execute(select(Household).limit(1)).scalar_one_or_none()
    if household is None:
        household = Household(name="Household")
        db.add(household)
        db.flush()

    email = row.email
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        user = User(household_id=household.id, email=email)
        db.add(user)
        db.flush()

    db.commit()
    db.refresh(user)
    return user


def sign_session(user_id: UUID, secret: str) -> str:
    serializer = URLSafeTimedSerializer(secret, salt=_SESSION_SALT)
    return serializer.dumps(str(user_id))


def unsign_session(
    token: str, secret: str, max_age_seconds: int = 60 * 60 * 24 * 30
) -> UUID | None:
    serializer = URLSafeTimedSerializer(secret, salt=_SESSION_SALT)
    try:
        raw = serializer.loads(token, max_age=max_age_seconds)
    except (SignatureExpired, BadSignature):
        return None
    if not isinstance(raw, str):
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
