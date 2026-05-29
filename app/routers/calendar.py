from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.calendar_query import enabled_tasks_for_household, household_by_token
from app.services.ics import build_calendar

router = APIRouter(tags=["calendar"])


@router.get("/cal/{token}.ics")
def calendar_feed(token: str, db: Session = Depends(get_db)) -> Response:
    household = household_by_token(db, token)
    if household is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    tasks = enabled_tasks_for_household(db, household.id)
    ics_text = build_calendar(household, tasks)
    return Response(
        content=ics_text,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'inline; filename="maintenance.ics"',
            "Cache-Control": "no-cache, private",
        },
    )
