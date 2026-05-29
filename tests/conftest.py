"""Shared pytest fixtures. Subagents add to this as needed."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  ensure model modules register on Base.metadata
from app.db import Base, get_db


@pytest.fixture
def db_engine() -> Iterator[Engine]:
    # StaticPool + check_same_thread=False so the same in-memory DB is visible
    # across threads — required when TestClient drives handlers in a worker.
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    session_factory = sessionmaker(db_engine, expire_on_commit=False, class_=Session)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_engine: Engine, db_session: Session) -> Iterator[TestClient]:
    from fastapi.staticfiles import StaticFiles

    from app.routers.auth import router as auth_router

    app = FastAPI()
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(auth_router)

    session_factory = sessionmaker(db_engine, expire_on_commit=False, class_=Session)

    def _override_get_db() -> Iterator[Session]:
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def ui_client(db_engine: Engine, db_session: Session) -> Iterator[TestClient]:
    from fastapi.staticfiles import StaticFiles

    from app.routers.auth import router as auth_router
    from app.routers.items import router as items_router
    from app.routers.settings import router as settings_router

    app = FastAPI()
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(auth_router)
    app.include_router(items_router)
    app.include_router(settings_router)

    session_factory = sessionmaker(db_engine, expire_on_commit=False, class_=Session)

    def _override_get_db() -> Iterator[Session]:
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def signed_in(
    db_session: Session, ui_client: TestClient
) -> tuple[object, object, TestClient]:
    # Creates a Household + User and sets a valid session cookie on the client.
    from app.deps import SESSION_COOKIE_NAME
    from app.models import Household, User
    from app.services.auth import sign_session
    from app.settings import settings as app_settings

    household = Household(name="Household")
    db_session.add(household)
    db_session.flush()
    user = User(household_id=household.id, email="kev@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(household)
    db_session.refresh(user)

    cookie = sign_session(user.id, app_settings.session_secret)
    ui_client.cookies.set(SESSION_COOKIE_NAME, cookie)
    return household, user, ui_client
