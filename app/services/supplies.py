from __future__ import annotations

from urllib.parse import quote_plus

from pydantic import HttpUrl, TypeAdapter

from app.contracts import SupplySuggestion

_AMAZON_SEARCH_BASE = "https://www.amazon.com/s?k="
_http_url_adapter: TypeAdapter[HttpUrl] = TypeAdapter(HttpUrl)


def amazon_search_url(query: str) -> str:
    return _AMAZON_SEARCH_BASE + quote_plus(query)


def attach_amazon_urls(supplies: list[SupplySuggestion]) -> list[SupplySuggestion]:
    result: list[SupplySuggestion] = []
    for supply in supplies:
        if supply.amazon_url is not None:
            result.append(supply)
            continue
        url = _http_url_adapter.validate_python(amazon_search_url(supply.search_query))
        result.append(supply.model_copy(update={"amazon_url": url}))
    return result
