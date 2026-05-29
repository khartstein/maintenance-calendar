from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Household, User
from app.settings import settings as app_settings

router = APIRouter(tags=["settings"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/settings", response_class=HTMLResponse)
def settings_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    household = db.get(Household, user.household_id)
    token = household.calendar_token if household else ""
    household_name = household.name if household else ""
    https_url = f"{app_settings.magic_link_base_url}/cal/{token}.ics"
    webcal_url = https_url.replace("https://", "webcal://").replace(
        "http://", "webcal://"
    )
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "user": user,
            "household_name": household_name,
            "webcal_url": webcal_url,
            "https_url": https_url,
        },
    )
