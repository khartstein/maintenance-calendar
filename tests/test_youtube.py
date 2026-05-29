from __future__ import annotations

from typing import Any

import pytest

from app.services.youtube import YouTubeClient


class _FakeRequest:
    def __init__(self, response: dict[str, Any], captured: dict[str, Any]) -> None:
        self._response = response
        self._captured = captured

    def execute(self) -> dict[str, Any]:
        self._captured["executed"] = True
        return self._response


class _FakeSearch:
    def __init__(self, response: dict[str, Any], captured: dict[str, Any]) -> None:
        self._response = response
        self._captured = captured

    def list(self, **kwargs: Any) -> _FakeRequest:
        self._captured["list_kwargs"] = kwargs
        return _FakeRequest(self._response, self._captured)


class _FakeService:
    def __init__(self, response: dict[str, Any], captured: dict[str, Any]) -> None:
        self._response = response
        self._captured = captured

    def search(self) -> _FakeSearch:
        return _FakeSearch(self._response, self._captured)


def test_top_videos_maps_response_to_video_suggestions() -> None:
    response = {
        "items": [
            {
                "id": {"videoId": "abc123"},
                "snippet": {"title": "How to descale", "channelTitle": "CoffeeCo"},
            },
            {
                "id": {"videoId": "def456"},
                "snippet": {"title": "Espresso care", "channelTitle": "BaristaTV"},
            },
        ]
    }
    captured: dict[str, Any] = {}
    client = YouTubeClient(api_key="fake-key")
    client._build_service = lambda: _FakeService(response, captured)  # type: ignore[method-assign]

    videos = client.top_videos("descale espresso machine", max_results=2)

    assert captured["list_kwargs"]["q"] == "descale espresso machine"
    assert captured["list_kwargs"]["maxResults"] == 2
    assert captured["list_kwargs"]["part"] == "snippet"
    assert captured["list_kwargs"]["type"] == "video"
    assert captured["list_kwargs"]["safeSearch"] == "moderate"
    assert len(videos) == 2
    assert videos[0].title == "How to descale"
    assert str(videos[0].url) == "https://www.youtube.com/watch?v=abc123"
    assert videos[0].channel == "CoffeeCo"
    assert str(videos[1].url) == "https://www.youtube.com/watch?v=def456"


def test_top_videos_skips_items_missing_required_fields() -> None:
    response = {
        "items": [
            {"id": {}, "snippet": {"title": "No id", "channelTitle": "X"}},
            {"id": {"videoId": "ok1"}, "snippet": {"channelTitle": "Y"}},
            {"id": {"videoId": "ok2"}, "snippet": {"title": "Good", "channelTitle": "Z"}},
        ]
    }
    captured: dict[str, Any] = {}
    client = YouTubeClient(api_key="fake-key")
    client._build_service = lambda: _FakeService(response, captured)  # type: ignore[method-assign]

    videos = client.top_videos("anything")
    assert len(videos) == 1
    assert videos[0].title == "Good"


def test_empty_api_key_raises() -> None:
    client = YouTubeClient(api_key="")
    with pytest.raises(RuntimeError, match="YOUTUBE_API_KEY not set"):
        client.top_videos("anything")


def test_default_max_results_is_three() -> None:
    captured: dict[str, Any] = {}
    client = YouTubeClient(api_key="fake-key")
    client._build_service = lambda: _FakeService({"items": []}, captured)  # type: ignore[method-assign]
    client.top_videos("query")
    assert captured["list_kwargs"]["maxResults"] == 3
