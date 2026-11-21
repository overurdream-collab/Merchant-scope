"""Regression checks for ambiguous control characters in provenance URLs.

These checks use synthetic URLs only; no external network or merchant data.
"""
import pytest
from fastapi import HTTPException
from app.pg_api import valid_url


@pytest.mark.parametrize("character", [
    "\x00", "\x01", "\x1f", "\x7f", "\x80", "\x9f",
    "\u200b", "\u200c", "\u200d", "\u2060", "\ufeff",
])
def test_source_url_rejects_invisible_or_control_characters(character):
    with pytest.raises(HTTPException) as error:
        valid_url("https://example.org/a" + character + "b")
    assert error.value.status_code == 422


@pytest.mark.parametrize("url", [
    "https://example.org/public-source",
    "https://www.openstreetmap.org/node/123456",
])
def test_source_url_accepts_public_unambiguous_urls(url):
    assert valid_url(url) == url
