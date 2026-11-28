"""Offline regression: global multicast is not a public unicast source."""
import pytest
from fastapi import HTTPException
from app.pg_api import valid_url


@pytest.mark.parametrize("url", [
    "https://224.0.0.1/source",
    "https://239.255.255.250/source",
    "https://[ff02::1]/source",
    "https://[ff0e::1]/source",
    "https://240.0.0.1/source",
    "https://127.0.0.1/source",
    "https://127.1/source",
    "https://0177.0.0.1/source",
    "https://0x7f.0.0.1/source",
    "https://2130706433/source",
    "https://8.8.8.8./source",
])
def test_non_unicast_source_rejected(url):
    with pytest.raises(HTTPException) as error:
        valid_url(url)
    assert error.value.status_code == 422


@pytest.mark.parametrize("url", [
    "https://8.8.8.8/source",
    "https://1.1.1.1:443/source",
    "https://[2606:4700:4700::1111]/source",
    "https://example.org/source",
])
def test_public_unicast_source_accepted(url):
    assert valid_url(url) == url
