from __future__ import annotations

from typing import Any

from googleapiclient.discovery import build
from pydantic import HttpUrl, TypeAdapter

from app.contracts import VideoSuggestion

_http_url_adapter: TypeAdapter[HttpUrl] = TypeAdapter(HttpUrl)


class YouTubeClient:
    def __init__(self, api_key: str, http_client: Any | None = None) -> None:
        self._api_key = api_key
        self._http_client = http_client

    def _build_service(self) -> Any:
        if self._http_client is not None:
            return build("youtube", "v3", developerKey=self._api_key, http=self._http_client)
        return build("youtube", "v3", developerKey=self._api_key)

    def top_videos(self, query: str, max_results: int = 3) -> list[VideoSuggestion]:
        if self._api_key == "":
            raise RuntimeError("YOUTUBE_API_KEY not set")
        service = self._build_service()
        request = service.search().list(
            part="snippet",
            q=query,
            type="video",
            maxResults=max_results,
            safeSearch="moderate",
        )
        response = request.execute()
        suggestions: list[VideoSuggestion] = []
        for item in response.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {})
            title = snippet.get("title")
            channel = snippet.get("channelTitle")
            if not video_id or not title:
                continue
            url = _http_url_adapter.validate_python(
                f"https://www.youtube.com/watch?v={video_id}"
            )
            suggestions.append(VideoSuggestion(title=title, url=url, channel=channel))
        return suggestions
