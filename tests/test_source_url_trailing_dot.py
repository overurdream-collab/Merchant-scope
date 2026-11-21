"""Regression tests for local DNS names with an absolute trailing dot."""
import pytest
from fastapi import HTTPException
from app.pg_api import valid_url


@pytest.mark.parametrize("url", [
    "https://localhost./",
    "https://LOCALHOST./",
    "https://api.localhost./evidence",
    "https://service.local./",
    "https://private.internal./path",
    "http://LOCALHOST.../",
])
def test_absolute_local_hostnames_rejected(url):
    with pytest.raises(HTTPException) as exc:
        valid_url(url)
    assert exc.value.status_code == 422


@pytest.mark.parametrize("url", [
    "https://www.openstreetmap.org/node/123",
    "https://example.org./evidence",
])
def test_public_hostname_accepted(url):
    assert valid_url(url) == url
