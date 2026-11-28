"""Regression tests for unambiguous provenance URLs (no network or database)."""
import pytest
from fastapi import HTTPException
from app.pg_api import valid_url


@pytest.mark.parametrize("url", [
    "https://example.com/path with space",
    "https://example.com/path\tvalue",
    "https://example.com/path\nvalue",
    "https://example.com/path\\\\segment",
    "https://example.com/\u00a0segment",
    "https://example.com/\u2003segment",
])
def test_source_url_rejects_whitespace_and_backslashes(url):
    with pytest.raises(HTTPException) as error:
        valid_url(url)
    assert error.value.status_code == 422


@pytest.mark.parametrize("url", [
    "https://www.openstreetmap.org/node/123",
    "https://example.com/path%20with%20encoded%20spaces",
])
def test_source_url_allows_unambiguous_public_urls(url):
    assert valid_url(url) == url
