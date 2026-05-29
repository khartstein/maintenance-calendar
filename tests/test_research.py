from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import HttpUrl, TypeAdapter

from app.contracts import VideoSuggestion
from app.services.research import (
    WEB_SEARCH_TOOL_TYPE,
    ResearchService,
    ResearchValidationError,
)
from app.services.youtube import YouTubeClient

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "research" / "espresso_machine.json"
_http_url_adapter: TypeAdapter[HttpUrl] = TypeAdapter(HttpUrl)


def _url(s: str) -> HttpUrl:
    return _http_url_adapter.validate_python(s)


class _FakeMessageResponse:
    def __init__(self, content: list[dict[str, Any]], stop_reason: str = "end_turn") -> None:
        self.content = content
        self.stop_reason = stop_reason


class _FakeMessages:
    def __init__(self, responses: list[_FakeMessageResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeMessageResponse:
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _FakeAnthropic:
    def __init__(self, responses: list[_FakeMessageResponse]) -> None:
        self.messages = _FakeMessages(responses)


class _FakeYouTube(YouTubeClient):
    def __init__(self, by_query: dict[str, list[VideoSuggestion]]) -> None:
        super().__init__(api_key="fake")
        self._by_query = by_query
        self.calls: list[tuple[str, int]] = []

    def top_videos(self, query: str, max_results: int = 3) -> list[VideoSuggestion]:
        self.calls.append((query, max_results))
        return list(self._by_query.get(query, []))[:max_results]


def _load_fixture_text() -> str:
    return FIXTURE_PATH.read_text()


def test_web_search_tool_type_constant() -> None:
    assert WEB_SEARCH_TOOL_TYPE == "web_search_20250305"


def test_research_item_assembles_videos_and_amazon_urls() -> None:
    fixture_text = _load_fixture_text()
    anthropic = _FakeAnthropic(
        [_FakeMessageResponse([{"type": "text", "text": fixture_text}], stop_reason="end_turn")]
    )

    youtube_data = {
        "Breville Barista Express descaling tutorial": [
            VideoSuggestion(
                title="Descale tutorial", url=_url("https://www.youtube.com/watch?v=v1"),
                channel="CoffeeCo",
            ),
            VideoSuggestion(
                title="Another descale", url=_url("https://www.youtube.com/watch?v=v2"),
                channel="BaristaTV",
            ),
        ],
        "how to descale espresso machine at home": [
            VideoSuggestion(
                title="Home descale", url=_url("https://www.youtube.com/watch?v=v3"),
                channel="Home",
            ),
            VideoSuggestion(
                title="Dup", url=_url("https://www.youtube.com/watch?v=v1"), channel="dup",
            ),
        ],
        "Breville Barista Express water filter replacement": [
            VideoSuggestion(
                title="Filter swap", url=_url("https://www.youtube.com/watch?v=v4"),
                channel="X",
            ),
        ],
        "Breville Barista Express backflush tutorial": [
            VideoSuggestion(
                title="Backflush 1", url=_url("https://www.youtube.com/watch?v=v5"),
                channel="X",
            ),
        ],
        "espresso machine group head cleaning": [
            VideoSuggestion(
                title="Group head", url=_url("https://www.youtube.com/watch?v=v6"),
                channel="Y",
            ),
        ],
    }
    youtube = _FakeYouTube(youtube_data)
    service = ResearchService(anthropic_client=anthropic, youtube=youtube)  # type: ignore[arg-type]

    result = service.research_item("Breville Barista Express")

    assert len(result.tasks) == 3
    descale = result.tasks[0]
    assert descale.title == "Descale espresso machine"
    assert len(descale.videos) == 3
    urls = [str(v.url) for v in descale.videos]
    assert urls == [
        "https://www.youtube.com/watch?v=v1",
        "https://www.youtube.com/watch?v=v2",
        "https://www.youtube.com/watch?v=v3",
    ]
    assert all(s.amazon_url is not None for s in descale.supplies)
    assert "espresso+machine+descaler" in str(descale.supplies[0].amazon_url)

    filter_task = result.tasks[1]
    assert len(filter_task.videos) == 1
    assert str(filter_task.videos[0].url) == "https://www.youtube.com/watch?v=v4"
    assert filter_task.supplies[0].amazon_url is not None

    backflush = result.tasks[2]
    assert len(backflush.videos) == 2


def test_research_item_handles_tool_use_loop() -> None:
    fixture_text = _load_fixture_text()
    responses = [
        _FakeMessageResponse(
            [
                {"type": "text", "text": "let me search"},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "web_search",
                    "input": {"query": "espresso descaling"},
                },
            ],
            stop_reason="tool_use",
        ),
        _FakeMessageResponse(
            [{"type": "text", "text": fixture_text}], stop_reason="end_turn"
        ),
    ]
    anthropic = _FakeAnthropic(responses)
    youtube = _FakeYouTube({})
    service = ResearchService(anthropic_client=anthropic, youtube=youtube)  # type: ignore[arg-type]

    result = service.research_item("Breville Barista Express")
    assert result.item_summary.startswith("Breville Barista Express")
    assert len(anthropic.messages.calls) == 2

    first_call = anthropic.messages.calls[0]
    assert first_call["tools"] == [{"type": WEB_SEARCH_TOOL_TYPE, "name": "web_search"}]
    system_block = first_call["system"][0]
    assert system_block["cache_control"] == {"type": "ephemeral"}
    assert "ItemResearch" in system_block["text"] or "item_summary" in system_block["text"]


def test_research_item_passes_amazon_url_and_asin_into_user_message() -> None:
    fixture_text = _load_fixture_text()
    anthropic = _FakeAnthropic(
        [_FakeMessageResponse([{"type": "text", "text": fixture_text}])]
    )
    service = ResearchService(
        anthropic_client=anthropic,  # type: ignore[arg-type]
        youtube=_FakeYouTube({}),
    )
    service.research_item(
        "Breville Barista Express",
        amazon_url="https://www.amazon.com/dp/B00CH9182S",
        asin="B00CH9182S",
    )
    user_msg = anthropic.messages.calls[0]["messages"][0]["content"]
    assert "Breville Barista Express" in user_msg
    assert "B00CH9182S" in user_msg
    assert "https://www.amazon.com/dp/B00CH9182S" in user_msg


def test_research_validation_error_on_bad_json() -> None:
    anthropic = _FakeAnthropic(
        [_FakeMessageResponse([{"type": "text", "text": "not json {"}])]
    )
    service = ResearchService(
        anthropic_client=anthropic,  # type: ignore[arg-type]
        youtube=_FakeYouTube({}),
    )
    with pytest.raises(ResearchValidationError) as excinfo:
        service.research_item("widget")
    assert excinfo.value.raw_text == "not json {"


def test_research_validation_error_on_schema_mismatch() -> None:
    bad = json.dumps({"item_summary": "x"})
    anthropic = _FakeAnthropic([_FakeMessageResponse([{"type": "text", "text": bad}])])
    service = ResearchService(
        anthropic_client=anthropic,  # type: ignore[arg-type]
        youtube=_FakeYouTube({}),
    )
    with pytest.raises(ResearchValidationError) as excinfo:
        service.research_item("widget")
    assert excinfo.value.raw_text == bad
