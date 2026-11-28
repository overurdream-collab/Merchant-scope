import os
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

os.environ["MERCHANTSCOPE_ADMIN_TOKEN"] = "test-secret"
from app.main import app

HEADERS = {"X-Admin-Token":"test-secret"}

@pytest.fixture
def client(tmp_path,monkeypatch):
    import app.main as m
    monkeypatch.setattr(m,"DB",tmp_path/"reports.db")
    m.init_db()
    return TestClient(app)

def create(client,name,city="صنعاء",category="مطاعم"):
    r=client.post("/api/merchants",headers=HEADERS,json={"name":name,"city":city,"category":category})
    assert r.status_code==201,r.text
    return r.json()["id"]

def test_portfolio_empty_has_no_fake_average(client):
    r=client.get("/api/reports/portfolio",headers=HEADERS)
    assert r.status_code==200
    data=r.json()
    assert data["merchant_count"]==0
    assert data["average_score_observed_sample"] is None
    assert data["average_coverage_assessed_sample"] is None

def test_reports_are_private(client):
    assert client.get("/api/reports/portfolio").status_code==401
    assert client.get("/api/merchants/1/report").status_code==401

def test_portfolio_filters_and_unknown_quality(client):
    m1=create(client,"متجر الفرح")
    m2=create(client,"مطعم اليمن","تعز")
    data=client.get("/api/reports/portfolio?city=صنعاء",headers=HEADERS).json()
    assert data["merchant_count"]==1
    assert data["merchants_without_usable_score"]==1
    assert data["merchants"][0]["id"]==m1
    assert data["average_score_observed_sample"] is None
    assert data["merchants"][0]["pending"]==0
    assert client.get(f"/api/merchants/{m2}/report",headers=HEADERS).status_code==200

def test_report_exposes_source_and_real_publication_date(client):
    mid=create(client,"مطعم الخير")
    observed=datetime.now(timezone.utc)
    published=observed-timedelta(days=4)
    response=client.post(f"/api/merchants/{mid}/evidence",headers=HEADERS,json={
        "source_url":"https://example.org/post/1",
        "platform":"web",
        "observed_at":observed.isoformat(),
        "published_at":published.isoformat(),
        "text":"منشور تجريبي موثق"
    })
    assert response.status_code==201,response.text
    report=client.get(f"/api/merchants/{mid}/report",headers=HEADERS).json()
    assert report["evidence_count"]==1
    assert report["publication_dates_documented"]==1
    assert report["source_evidence"][0]["source_url"]=="https://example.org/post/1"
    assert report["source_evidence"][0]["published_at"]==published.isoformat()
    assert report["score"] is None
    assert report["data_quality_warnings"]

def test_recommendation_review_count_accuracy(client):
    mid=create(client,"مطعم الظلال")
    now=datetime.now(timezone.utc)
    for day in (2,18,35):
        e=client.post(f"/api/merchants/{mid}/evidence",headers=HEADERS,json={
            "source_url":f"https://example.org/post/{day}",
            "platform":"web","observed_at":(now-timedelta(days=day)).isoformat(),
            "published_at":(now-timedelta(days=day)).isoformat(),
            "text":"شراء"
        })
        assert e.status_code==201,e.text
    result=client.post(f"/api/merchants/{mid}/analyze",headers=HEADERS)
    assert result.status_code==200,result.text
    report=client.get(f"/api/merchants/{mid}/report",headers=HEADERS).json()
    assert len(report["recommendations"])==result.json()["recommendations_created"]
    p=client.get("/api/reports/portfolio",headers=HEADERS).json()
    assert p["reviews"].get("pending_review",0)==result.json()["recommendations_created"]
