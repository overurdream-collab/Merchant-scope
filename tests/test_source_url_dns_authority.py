"""Reject ambiguous DNS authorities without network access or live merchant data."""
import pytest
from fastapi import HTTPException
from app.pg_api import valid_url


@pytest.mark.parametrize("url", [
    "https://127%2e0%2e0%2e1/path",
    "https://local%68ost/path",
    "https://example..org/path",
    "https://-example.org/path",
    "https://example-.org/path",
    "https://intranet/path",
    "https://exämple.org/path",
])
def test_ambiguous_authority_rejected(url):
    with pytest.raises(HTTPException) as error:
        valid_url(url)
    assert error.value.status_code == 422


@pytest.mark.parametrize("url", [
    "https://example.org./path%20ok",
    "https://www.openstreetmap.org/node/123",
    "https://example.com/a?b=c",
])
def test_public_provenance_remains_accepted(url):
    assert valid_url(url) == url
