from __future__ import annotations

import json
from typing import Any, cast

from anthropic import Anthropic
from pydantic import ValidationError

from app.contracts import ItemResearch, MaintenanceTaskDraft, VideoSuggestion
from app.services.supplies import attach_amazon_urls
from app.services.youtube import YouTubeClient

WEB_SEARCH_TOOL_TYPE = "web_search_20250305"

_SYSTEM_PROMPT = """You research consumer products to produce maintenance schedules.

For the item the user names, identify the routine maintenance tasks an owner should
perform. For each task, give a realistic recurrence cadence based on manufacturer
guidance and common practice (e.g. descaling espresso machines every 1-3 months
depending on water hardness; lawnmower oil yearly or per ~50 hours of use; HVAC
air filters per spec, typically every 1-3 months). Set exactly one of
cadence.months, cadence.years, or cadence.hours_of_use per task.

For each task, populate `supplies` with the consumables/parts needed (label +
plain-language search_query suitable for an Amazon search; do not invent URLs;
leave amazon_url unset). Populate `video_search_queries` with up to 3 short
YouTube-style search strings for how-to videos. Leave `videos` as an empty list -
a separate step resolves them.

Use the web_search tool to verify cadences and supply specifics when unsure.

Respond with a SINGLE JSON object matching this schema and nothing else - no prose,
no markdown fence:

%s
"""


class ResearchValidationError(Exception):
    def __init__(self, message: str, raw_text: str) -> None:
        super().__init__(message)
        self.raw_text = raw_text


class ResearchService:
    def __init__(
        self,
        anthropic_client: Anthropic,
        youtube: YouTubeClient,
        model: str = "claude-opus-4-7",
    ) -> None:
        self._client = anthropic_client
        self._youtube = youtube
        self._model = model

    def _system_blocks(self) -> list[dict[str, Any]]:
        schema_json = json.dumps(ItemResearch.model_json_schema(), indent=2)
        return [
            {
                "type": "text",
                "text": _SYSTEM_PROMPT % schema_json,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def _user_text(self, name: str, amazon_url: str | None, asin: str | None) -> str:
        lines = [f"Item: {name}"]
        if amazon_url:
            lines.append(f"Amazon URL: {amazon_url}")
        if asin:
            lines.append(f"ASIN: {asin}")
        lines.append("")
        lines.append(
            "Research routine maintenance for this item and respond with the JSON object."
        )
        return "\n".join(lines)

    def _run_messages_loop(self, user_text: str) -> str:
        tools: list[dict[str, Any]] = [
            {"type": WEB_SEARCH_TOOL_TYPE, "name": "web_search"}
        ]
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_text}
        ]

        while True:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=8192,
                system=cast(Any, self._system_blocks()),
                tools=cast(Any, tools),
                messages=cast(Any, messages),
            )
            stop_reason = getattr(response, "stop_reason", None)
            content = self._content_to_list(response)

            if stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": content})
                tool_results = self._server_tool_results(content)
                if not tool_results:
                    return self._final_text(content)
                messages.append({"role": "user", "content": tool_results})
                continue

            return self._final_text(content)

    @staticmethod
    def _content_to_list(response: Any) -> list[dict[str, Any]]:
        raw = getattr(response, "content", [])
        out: list[dict[str, Any]] = []
        for block in raw:
            if isinstance(block, dict):
                out.append(block)
            else:
                dump = getattr(block, "model_dump", None)
                out.append(dump() if callable(dump) else dict(block))
        return out

    @staticmethod
    def _server_tool_results(content: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for block in content:
            if block.get("type") == "tool_use" and block.get("name") == "web_search":
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.get("id", ""),
                        "content": "no result",
                    }
                )
        return results

    @staticmethod
    def _final_text(content: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for block in content:
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts).strip()

    def research_item(
        self,
        name: str,
        amazon_url: str | None = None,
        asin: str | None = None,
    ) -> ItemResearch:
        raw_text = self._run_messages_loop(self._user_text(name, amazon_url, asin))
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ResearchValidationError(
                f"Claude response was not valid JSON: {exc}", raw_text
            ) from exc
        try:
            research = ItemResearch.model_validate(data)
        except ValidationError as exc:
            raise ResearchValidationError(
                f"Claude response did not match ItemResearch schema: {exc}", raw_text
            ) from exc

        enriched_tasks = [self._enrich_task(task) for task in research.tasks]
        return research.model_copy(update={"tasks": enriched_tasks})

    def _enrich_task(self, task: MaintenanceTaskDraft) -> MaintenanceTaskDraft:
        videos: list[VideoSuggestion] = list(task.videos)
        seen_urls = {str(v.url) for v in videos}
        for query in task.video_search_queries:
            if len(videos) >= 3:
                break
            for video in self._youtube.top_videos(query, max_results=2):
                url_str = str(video.url)
                if url_str in seen_urls:
                    continue
                seen_urls.add(url_str)
                videos.append(video)
                if len(videos) >= 3:
                    break
        supplies = attach_amazon_urls(list(task.supplies))
        return task.model_copy(update={"videos": videos[:3], "supplies": supplies})
