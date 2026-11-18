import os
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
os.environ["MERCHANTSCOPE_ADMIN_TOKEN"] = "test-secret"
from app.main import app
H={"X-Admin-Token":"test-secret"}
R={"X-Admin-Token":"reviewer-secret"}

@pytest.fixture
def client(tmp_path,monkeypatch):
    import app.main as m
    monkeypatch.setattr(m,"DB",tmp_path/"security.db")
    monkeypatch.setenv("MERCHANTSCOPE_REVIEWER_TOKEN","reviewer-secret")
    m.init_db()
    return TestClient(app)

def create(c,name):
    r=c.post("/api/merchants",headers=H,json={"name":name,"city":"صنعاء"})
    assert r.status_code==201,r.text
    return r.json()["id"]

def test_review_requires_separate_token(client):
    mid=create(client,"متجر الفجر")
    body={"approved":True,"notes":"تمت المراجعة"}
    assert client.post(f"/api/merchants/{mid}/outreach-approval",headers=H,json=body).status_code==403
    assert client.post(f"/api/merchants/{mid}/outreach-approval",headers=R,json=body).status_code==200

def test_observation_date_is_not_publication_date(client):
    mid=create(client,"متجر الضياء")
    for d in (4,14,26):
        at=(datetime.now(timezone.utc)-timedelta(days=d)).isoformat()
        r=client.post(f"/api/merchants/{mid}/evidence",headers=H,json={"platform":"facebook","source_url":f"https://example.com/{d}","observed_at":at,"text":"منشور جديد"})
        assert r.status_code==201,r.text
    assessment=client.post(f"/api/merchants/{mid}/analyze",headers=H).json()["assessment"]
    assert assessment["dimensions"]["consistency"] is None

def test_documented_publication_dates_allow_consistency(client):
    mid=create(client,"متجر الأصيل")
    for d in (5,15,25):
        now=datetime.now(timezone.utc)
        r=client.post(f"/api/merchants/{mid}/evidence",headers=H,json={"platform":"facebook","source_url":f"https://example.com/post/{d}","observed_at":now.isoformat(),"published_at":(now-timedelta(days=d)).isoformat(),"text":"منشور"})
        assert r.status_code==201,r.text
    assessment=client.post(f"/api/merchants/{mid}/analyze",headers=H).json()["assessment"]
    assert assessment["dimensions"]["consistency"] is not None

def test_future_publication_is_rejected(client):
    mid=create(client,"مقهى المدينة")
    before=datetime.now(timezone.utc)-timedelta(days=2)
    after=datetime.now(timezone.utc)-timedelta(days=1)
    r=client.post(f"/api/merchants/{mid}/evidence",headers=H,json={"platform":"web","source_url":"https://example.com/p","observed_at":before.isoformat(),"published_at":after.isoformat()})
    assert r.status_code==422
