"""Regression tests for malformed provenance URLs; no database or network required."""
import pytest
from fastapi import HTTPException
from app.pg_api import valid_url


@pytest.mark.parametrize("url", [
    "https://[broken/path",
    "https://example.org:invalid/source",
    "https://example.org:99999/source",
    "https://user:secret@example.org/source",
    "https://127.0.0.1/source",
    "https://example.org/source\r\nX-Injected: yes",
])
def test_invalid_source_url_returns_422(url):
    with pytest.raises(HTTPException) as error:
        valid_url(url)
    assert error.value.status_code == 422


def test_public_source_url_is_preserved():
    url = "https://www.openstreetmap.org/node/12345"
    assert valid_url(url) == url
