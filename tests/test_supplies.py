from __future__ import annotations

from app.contracts import SupplySuggestion
from app.services.supplies import amazon_search_url, attach_amazon_urls


def test_amazon_search_url_encodes_spaces() -> None:
    url = amazon_search_url("descaling solution")
    assert url == "https://www.amazon.com/s?k=descaling+solution"


def test_amazon_search_url_encodes_special_chars() -> None:
    url = amazon_search_url("café & filter (size 4)")
    assert url.startswith("https://www.amazon.com/s?k=")
    assert "%26" in url
    assert "%28" in url
    assert "%29" in url
    assert "+" in url


def test_amazon_search_url_handles_empty_string() -> None:
    assert amazon_search_url("") == "https://www.amazon.com/s?k="


def test_attach_amazon_urls_populates_missing() -> None:
    supplies = [
        SupplySuggestion(label="Descaler", search_query="espresso descaler"),
        SupplySuggestion(label="Cleaner", search_query="group head cleaner"),
    ]
    result = attach_amazon_urls(supplies)
    assert len(result) == 2
    assert result[0].amazon_url is not None
    assert str(result[0].amazon_url).startswith("https://www.amazon.com/s?k=espresso+descaler")
    assert result[1].amazon_url is not None
    assert "group+head+cleaner" in str(result[1].amazon_url)


def test_attach_amazon_urls_preserves_existing() -> None:
    existing = "https://example.com/preset-product"
    supply = SupplySuggestion(
        label="Filter", search_query="hepa filter", amazon_url=existing  # type: ignore[arg-type]
    )
    result = attach_amazon_urls([supply])
    assert result[0].amazon_url is not None
    assert str(result[0].amazon_url).rstrip("/") == existing.rstrip("/")


def test_attach_amazon_urls_returns_new_list() -> None:
    supplies = [SupplySuggestion(label="X", search_query="x")]
    result = attach_amazon_urls(supplies)
    assert result is not supplies
    assert supplies[0].amazon_url is None
