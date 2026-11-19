"""Validate the sourced Sana'a research candidate list; no fabricated marketing analytics."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from datetime import date

MANIFEST=Path(__file__).parents[1]/"research"/"sanaa_30_candidates_2026-11-19.json"

def test_exactly_30_unique_unverified_directories():
    sample=json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows=sample["records"]
    assert len(rows)==30
    assert len({row["source_url"] for row in rows})==30
    assert len({row["name"].casefold().strip() for row in rows})==30
    assert date.fromisoformat(sample["collected_on"]) <= date.today()
    for row in rows:
        assert row["city"]=="صنعاء"
        assert row["country"]=="اليمن"
        assert row["verification_status"]=="unverified"
        assert row["marketing_analysis_status"]=="not_assessed"
        assert row["consent_to_outreach"] is False
        assert row["source_kind"]=="public_directory_listing"
        url=urlsplit(row["source_url"])
        assert url.scheme=="https"
        assert url.hostname in {"happynew.day","eatoutmap.com"}
        assert url.path.startswith("/vendor/") or url.path.startswith("/en/yemen/sanaa/")
        assert all(k not in row for k in (
            "likes","comments","followers","revenue","phone","email","score",
            "marketing_budget","review_count","sentiment","predicted_sales"))

def test_candidate_manifest_is_not_misrepresented_as_live_campaign():
    content=json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert content["status"]=="candidates_unverified"
    assert "No outreach" in content["purpose"]
    assert any("eatoutmap.com" in row["source_url"] for row in content["records"])
    assert any("happynew.day" in row["source_url"] for row in content["records"])
