from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Household, MagicLinkToken, User
from app.services.auth import (
    ExpiredMagicLinkError,
    InvalidMagicLinkError,
    MagicLinkError,
    UsedMagicLinkError,
    hash_token,
    issue_magic_link,
    sign_session,
    unsign_session,
    verify_magic_link,
)
from app.services.email_sender import ConsoleEmailSender


def test_hash_token_is_deterministic() -> None:
    a = hash_token("hello")
    b = hash_token("hello")
    c = hash_token("hello!")
    assert a == b
    assert a != c
    assert len(a) == 64


def test_issue_magic_link_persists_and_hashes(db_session: Session) -> None:
    raw, row = issue_magic_link(db_session, "Jane@Example.com")
    assert raw
    assert row.token_hash == hash_token(raw)
    assert row.email == "jane@example.com"
    fetched = db_session.execute(
        select(MagicLinkToken).where(MagicLinkToken.id == row.id)
    ).scalar_one()
    assert fetched.token_hash == hash_token(raw)
    expires_at = fetched.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    assert expires_at > datetime.now(timezone.utc)


def test_verify_magic_link_creates_household_and_user(db_session: Session) -> None:
    raw, _ = issue_magic_link(db_session, "first@example.com")
    user = verify_magic_link(db_session, raw)
    assert user.email == "first@example.com"
    households = db_session.execute(select(Household)).scalars().all()
    assert len(households) == 1
    assert households[0].name == "Household"
    assert user.household_id == households[0].id

    raw2, _ = issue_magic_link(db_session, "second@example.com")
    user2 = verify_magic_link(db_session, raw2)
    households_after = db_session.execute(select(Household)).scalars().all()
    assert len(households_after) == 1
    assert user2.household_id == households[0].id
    users = db_session.execute(select(User)).scalars().all()
    assert {u.email for u in users} == {"first@example.com", "second@example.com"}


def test_verify_magic_link_rejects_used_token(db_session: Session) -> None:
    raw, _ = issue_magic_link(db_session, "user@example.com")
    verify_magic_link(db_session, raw)
    with pytest.raises(UsedMagicLinkError) as exc:
        verify_magic_link(db_session, raw)
    assert exc.value.reason == "used"


def test_verify_magic_link_rejects_expired_token(db_session: Session) -> None:
    raw, row = issue_magic_link(db_session, "user@example.com")
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.add(row)
    db_session.commit()
    with pytest.raises(ExpiredMagicLinkError) as exc:
        verify_magic_link(db_session, raw)
    assert exc.value.reason == "expired"


def test_verify_magic_link_rejects_unknown_token(db_session: Session) -> None:
    with pytest.raises(InvalidMagicLinkError) as exc:
        verify_magic_link(db_session, "nope-not-real")
    assert exc.value.reason == "invalid"
    assert isinstance(exc.value, MagicLinkError)


def test_session_round_trip() -> None:
    secret = "test-secret"
    uid = uuid4()
    token = sign_session(uid, secret)
    assert unsign_session(token, secret) == uid

    tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    assert unsign_session(tampered, secret) is None

    assert unsign_session(token, "other-secret") is None


def test_session_expired_token_returns_none() -> None:
    # itsdangerous truncates the signed timestamp to whole seconds, so a 1.1s
    # sleep with max_age=1 can read as age=1 (1 > 1 is False, not expired).
    # Sleep through two integer boundaries to be deterministic.
    secret = "test-secret"
    uid = uuid4()
    token = sign_session(uid, secret)
    time.sleep(2.1)
    assert unsign_session(token, secret, max_age_seconds=1) is None


def test_console_email_sender_does_not_raise(capsys: pytest.CaptureFixture[str]) -> None:
    sender = ConsoleEmailSender()
    sender.send_magic_link(to="user@example.com", link="http://localhost/x?token=abc")
    captured = capsys.readouterr()
    assert "user@example.com" in captured.out
    assert "http://localhost/x?token=abc" in captured.out
