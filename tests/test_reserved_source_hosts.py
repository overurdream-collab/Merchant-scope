"""Regression checks for non-public DNS provenance (no network or database)."""
import pytest
from fastapi import HTTPException
from app.pg_api import valid_url


@pytest.mark.parametrize("url", [
    "https://merchant.test/listing",
    "https://merchant.invalid/listing",
    "https://merchant.onion/listing",
    "https://router.home.arpa/listing",
    "https://merchant.TEST/listing",
    "https://merchant.invalid./listing",
])
def test_reserved_nonpublic_source_hosts_rejected(url):
    with pytest.raises(HTTPException) as exc:
        valid_url(url)
    assert exc.value.status_code == 422


@pytest.mark.parametrize("url", [
    "https://www.openstreetmap.org/node/123",
    "https://example.com/public-source",
])
def test_public_source_hosts_still_accepted(url):
    assert valid_url(url) == url
