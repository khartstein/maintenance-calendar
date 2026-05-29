"""Shared contracts used across the codebase.

Every subagent codes against these shapes. Do not duplicate or redefine them in
your slice — extend here if you need a new field, then notify other subagents.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class Cadence(BaseModel):
    """How often a maintenance task recurs.

    Exactly one of months / years / hours_of_use should be set.
    months and years drive RRULE generation; hours_of_use is informational
    in v1 (no usage tracking yet).
    """

    months: int | None = Field(default=None, ge=1)
    years: int | None = Field(default=None, ge=1)
    hours_of_use: int | None = Field(default=None, ge=1)


class SupplySuggestion(BaseModel):
    """A consumable or part needed for a maintenance task.

    The research pipeline emits search_query; a URL builder turns it into an
    Amazon search URL stored in amazon_url.
    """

    label: str
    search_query: str
    amazon_url: HttpUrl | None = None


class VideoSuggestion(BaseModel):
    """A how-to video resolved from a search query via the YouTube API."""

    title: str
    url: HttpUrl
    channel: str | None = None


class MaintenanceTaskDraft(BaseModel):
    """One maintenance event in the LLM-produced draft for an item."""

    title: str
    description: str
    cadence: Cadence
    supplies: list[SupplySuggestion] = Field(default_factory=list)
    videos: list[VideoSuggestion] = Field(default_factory=list)
    video_search_queries: list[str] = Field(default_factory=list)


class ItemResearch(BaseModel):
    """Full research output for one item, ready for human review."""

    item_summary: str
    tasks: list[MaintenanceTaskDraft]
