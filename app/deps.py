from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.services.auth import unsign_session
from app.settings import settings

SESSION_COOKIE_NAME = "session"


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    user = get_optional_user(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def get_optional_user(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    raw = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw:
        return None
    user_id = unsign_session(raw, settings.session_secret)
    if user_id is None:
        return None
    return db.get(User, user_id)
