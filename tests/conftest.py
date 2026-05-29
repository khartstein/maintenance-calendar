"""Shared pytest fixtures. Subagents add to this as needed."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  ensure model modules register on Base.metadata
from app.db import Base


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine, expire_on_commit=False, class_=Session)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
