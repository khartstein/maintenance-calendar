from __future__ import annotations

from contextlib import suppress

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import SESSION_COOKIE_NAME
from app.services.auth import (
    MagicLinkError,
    issue_magic_link,
    sign_session,
    verify_magic_link,
)
from app.services.email_sender import EmailSender, build_email_sender
from app.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

_SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30
_REQUEST_SENT_HTML = (
    '<div class="auth-result">Check your email for the link.</div>'
)


def _email_sender() -> EmailSender:
    return build_email_sender(
        settings.email_backend,
        api_key=settings.resend_api_key,
        from_addr=settings.email_from,
    )


def _cookie_secure() -> bool:
    return settings.app_env.lower() != "dev"


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/login.html", {})


@router.post("/request", response_class=HTMLResponse)
def request_link(
    email: str = Form(...),
    db: Session = Depends(get_db),
    sender: EmailSender = Depends(_email_sender),
) -> HTMLResponse:
    normalized = email.strip().lower()
    if normalized:
        raw_token, _ = issue_magic_link(db, normalized)
        link = f"{settings.magic_link_base_url}/auth/verify?token={raw_token}"
        with suppress(Exception):
            sender.send_magic_link(to=normalized, link=link)
    return HTMLResponse(_REQUEST_SENT_HTML)


@router.get("/verify")
def verify(
    request: Request, token: str = "", db: Session = Depends(get_db)
) -> Response:
    try:
        user = verify_magic_link(db, token)
    except MagicLinkError as exc:
        return templates.TemplateResponse(
            request,
            "auth/verify_failed.html",
            {"reason": exc.reason},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        sign_session(user.id, settings.session_secret),
        max_age=_SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
        path="/",
    )
    return response


@router.post("/logout")
def logout() -> Response:
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response
