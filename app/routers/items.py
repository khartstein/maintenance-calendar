from __future__ import annotations

from datetime import date
from uuid import UUID

from anthropic import Anthropic
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.contracts import (
    Cadence,
    ItemResearch,
    MaintenanceTaskDraft,
    SupplySuggestion,
    VideoSuggestion,
)
from app.db import get_db
from app.deps import get_current_user, get_optional_user
from app.models import MaintenanceTask, User
from app.services.items import (
    create_item,
    delete_item,
    get_item,
    list_items,
    save_tasks_for_item,
)
from app.services.research import ResearchService
from app.services.youtube import YouTubeClient
from app.settings import settings

router = APIRouter(tags=["items"])
templates = Jinja2Templates(directory="app/templates")


def build_research_service() -> ResearchService:
    return ResearchService(
        anthropic_client=Anthropic(api_key=settings.anthropic_api_key),
        youtube=YouTubeClient(api_key=settings.youtube_api_key),
    )


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    if user is None:
        return templates.TemplateResponse(
            request, "index.html", {"user": None, "items": []}
        )
    items = list_items(db, user.household_id)
    return templates.TemplateResponse(
        request, "index.html", {"user": user, "items": items}
    )


@router.get("/items/new", response_class=HTMLResponse)
def new_item_form(
    request: Request, user: User = Depends(get_current_user)
) -> HTMLResponse:
    return templates.TemplateResponse(request, "items/new.html", {"user": user})


@router.post("/items/new", response_class=HTMLResponse)
def create_item_and_draft(
    request: Request,
    name: str = Form(...),
    amazon_url: str = Form(""),
    asin: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    research: ResearchService = Depends(build_research_service),
) -> HTMLResponse:
    clean_name = name.strip()
    clean_url = amazon_url.strip() or None
    clean_asin = asin.strip() or None
    if not clean_name:
        raise HTTPException(status_code=400, detail="name is required")

    result: ItemResearch = research.research_item(
        name=clean_name, amazon_url=clean_url, asin=clean_asin
    )
    item = create_item(
        db,
        household_id=user.household_id,
        name=clean_name,
        amazon_url=clean_url,
        asin=clean_asin,
        summary=result.item_summary,
    )
    return templates.TemplateResponse(
        request,
        "items/draft.html",
        {
            "user": user,
            "item": item,
            "tasks": result.tasks,
            "form_action": f"/items/{item.id}/tasks",
            "is_edit": False,
        },
    )


@router.post("/items/{item_id}/tasks")
async def save_drafted_tasks(
    item_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    item = get_item(db, user.household_id, item_id)
    if item is None:
        raise HTTPException(status_code=404)
    form = await _form_dict(request)
    drafts = _decode_form_drafts(form)
    save_tasks_for_item(db, item, drafts, default_start=date.today())
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/items/{item_id}/edit", response_class=HTMLResponse)
def edit_item_form(
    item_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    item = get_item(db, user.household_id, item_id)
    if item is None:
        raise HTTPException(status_code=404)
    drafts = [_task_to_draft(task) for task in item.tasks]
    return templates.TemplateResponse(
        request,
        "items/edit.html",
        {
            "user": user,
            "item": item,
            "tasks": drafts,
            "form_action": f"/items/{item.id}/edit",
            "is_edit": True,
        },
    )


@router.post("/items/{item_id}/edit")
async def update_item(
    item_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    item = get_item(db, user.household_id, item_id)
    if item is None:
        raise HTTPException(status_code=404)
    form = await _form_dict(request)
    name = _first(form, "name").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    item.name = name
    item.summary = _first(form, "summary")
    db.add(item)
    db.commit()
    db.refresh(item)
    drafts = _decode_form_drafts(form)
    save_tasks_for_item(db, item, drafts, default_start=date.today())
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/items/{item_id}/delete")
def delete_item_route(
    item_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    delete_item(db, user.household_id, item_id)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/items/_partial/supply_row", response_class=HTMLResponse)
def add_supply_row(
    request: Request,
    task_index: int = Form(...),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "items/_supply_row.html",
        {"task_index": task_index, "supply": None, "is_new": True},
    )


@router.post("/items/_partial/video_row", response_class=HTMLResponse)
def add_video_row(
    request: Request,
    task_index: int = Form(...),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "items/_video_row.html",
        {"task_index": task_index, "video": None, "is_new": True},
    )


def _task_to_draft(task: MaintenanceTask) -> MaintenanceTaskDraft:
    if task.rrule.startswith("FREQ=YEARLY"):
        years = _interval_from_rrule(task.rrule, default=1)
        cadence = Cadence(years=years)
    else:
        months = _interval_from_rrule(task.rrule, default=1)
        cadence = Cadence(months=months)

    supplies: list[SupplySuggestion] = []
    for entry in task.supplies:
        label = str(entry.get("label", "")).strip()
        url_raw = str(entry.get("url", "")).strip()
        if not label:
            continue
        if url_raw:
            try:
                supplies.append(
                    SupplySuggestion(label=label, search_query=label, amazon_url=url_raw)
                )
                continue
            except ValidationError:
                pass
        supplies.append(SupplySuggestion(label=label, search_query=label))

    videos: list[VideoSuggestion] = []
    for entry in task.videos:
        title = str(entry.get("title", "")).strip()
        url_raw = str(entry.get("url", "")).strip()
        channel = str(entry.get("channel", "")).strip() or None
        if not title or not url_raw:
            continue
        try:
            videos.append(VideoSuggestion(title=title, url=url_raw, channel=channel))
        except ValidationError:
            continue

    return MaintenanceTaskDraft(
        title=task.title,
        description=task.description,
        cadence=cadence,
        supplies=supplies,
        videos=videos,
        video_search_queries=[],
    )


def _interval_from_rrule(rrule: str, default: int) -> int:
    for part in rrule.split(";"):
        if part.startswith("INTERVAL="):
            try:
                return int(part.split("=", 1)[1])
            except ValueError:
                return default
    return default


async def _form_dict(request: Request) -> dict[str, list[str]]:
    form = await request.form()
    out: dict[str, list[str]] = {}
    for key, value in form.multi_items():
        out.setdefault(key, []).append(str(value))
    return out


def _decode_form_drafts(form: dict[str, list[str]]) -> list[MaintenanceTaskDraft]:
    count_raw = form.get("task_count", ["0"])[0]
    try:
        task_count = int(count_raw)
    except ValueError:
        task_count = 0

    drafts: list[MaintenanceTaskDraft] = []
    for i in range(task_count):
        title = _first(form, f"task_{i}_title").strip()
        if not title:
            continue
        description = _first(form, f"task_{i}_description")
        cadence_unit = _first(form, f"task_{i}_cadence_unit", default="months")
        cadence_value_raw = _first(form, f"task_{i}_cadence_value", default="1")
        try:
            cadence_value = max(1, int(cadence_value_raw))
        except ValueError:
            cadence_value = 1
        if cadence_unit == "years":
            cadence = Cadence(years=cadence_value)
        else:
            cadence = Cadence(months=cadence_value)

        supplies = _decode_supply_rows(
            form, f"task_{i}_supply_label", f"task_{i}_supply_url"
        )
        videos = _decode_video_rows(
            form,
            f"task_{i}_video_title",
            f"task_{i}_video_url",
            f"task_{i}_video_channel",
        )

        drafts.append(
            MaintenanceTaskDraft(
                title=title,
                description=description,
                cadence=cadence,
                supplies=supplies,
                videos=videos,
                video_search_queries=[],
            )
        )
    return drafts


def _first(form: dict[str, list[str]], key: str, default: str = "") -> str:
    values = form.get(key)
    if not values:
        return default
    return values[0]


def _decode_supply_rows(
    form: dict[str, list[str]], label_key: str, url_key: str
) -> list[SupplySuggestion]:
    labels = form.get(label_key, [])
    urls = form.get(url_key, [])
    rows: list[SupplySuggestion] = []
    for idx in range(max(len(labels), len(urls))):
        label = labels[idx].strip() if idx < len(labels) else ""
        url_raw = urls[idx].strip() if idx < len(urls) else ""
        if not label:
            continue
        if url_raw:
            try:
                rows.append(
                    SupplySuggestion(label=label, search_query=label, amazon_url=url_raw)
                )
                continue
            except ValidationError:
                pass
        rows.append(SupplySuggestion(label=label, search_query=label))
    return rows


def _decode_video_rows(
    form: dict[str, list[str]],
    title_key: str,
    url_key: str,
    channel_key: str,
) -> list[VideoSuggestion]:
    titles = form.get(title_key, [])
    urls = form.get(url_key, [])
    channels = form.get(channel_key, [])
    rows: list[VideoSuggestion] = []
    n = max(len(titles), len(urls), len(channels))
    for idx in range(n):
        title = titles[idx].strip() if idx < len(titles) else ""
        url_raw = urls[idx].strip() if idx < len(urls) else ""
        channel = channels[idx].strip() if idx < len(channels) else ""
        if not title or not url_raw:
            continue
        try:
            rows.append(VideoSuggestion(title=title, url=url_raw, channel=channel or None))
        except ValidationError:
            continue
    return rows


__all__ = ["router", "build_research_service"]
