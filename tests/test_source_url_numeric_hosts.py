"""Regression coverage for ambiguous numeric host spellings in source provenance."""
import pytest
from fastapi import HTTPException
from app.pg_api import valid_url


@pytest.mark.parametrize("url", [
    "http://2130706433/secret",  # integer loopback
    "http://0x7f000001/secret",  # hexadecimal loopback
    "http://0177.0.0.1/secret",  # octal-like IPv4
    "https://0x7f.0x0.0x0.0x1/",
    "https://127.1/",
    "https://0xA9FEA9FE/",
])
def test_reject_ambiguous_numeric_hosts(url):
    with pytest.raises(HTTPException) as error:
        valid_url(url)
    assert error.value.status_code == 422


@pytest.mark.parametrize("url", [
    "https://www.openstreetmap.org/node/123",
    "https://example.com/article/2026",
])
def test_preserve_public_domain_sources(url):
    assert valid_url(url) == url
