import os
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
import pytest
os.environ["MERCHANTSCOPE_ADMIN_TOKEN"]="test-secret"
from app.main import app
H={"X-Admin-Token":"test-secret"}

@pytest.fixture
def client(tmp_path,monkeypatch):
    import app.main as m
    monkeypatch.setattr(m,"DB",tmp_path/"idempotence.db")
    m.init_db()
    return TestClient(app)

def test_repeating_analysis_is_idempotent(client):
    mid=client.post("/api/merchants",headers=H,json={"name":"محل النجوم","city":"صنعاء"}).json()["id"]
    at=datetime.now(timezone.utc)
    for offset in (1,19,38):
        stamp=(at-timedelta(days=offset)).isoformat()
        r=client.post(f"/api/merchants/{mid}/evidence",headers=H,json={
            "platform":"web","source_url":f"https://example.org/p/{offset}",
            "observed_at":stamp,"published_at":stamp,"text":"عرض قصير"
        })
        assert r.status_code==201,r.text
    first=client.post(f"/api/merchants/{mid}/analyze",headers=H)
    assert first.status_code==200,first.text
    one=first.json()
    assert one["reused"] is False
    assert one["recommendations_created"]>0
    second=client.post(f"/api/merchants/{mid}/analyze",headers=H)
    assert second.status_code==200,second.text
    two=second.json()
    assert two["reused"] is True
    assert two["assessment_id"]==one["assessment_id"]
    assert two["recommendations_created"]==0
    detail=client.get(f"/api/merchants/{mid}",headers=H).json()
    assert len(detail["assessments"])==1
    assert len(detail["recommendations"])==one["recommendations_created"]
    r=client.post(f"/api/merchants/{mid}/evidence",headers=H,json={
        "platform":"web","source_url":"https://example.org/p/new",
        "observed_at":at.isoformat(),"published_at":at.isoformat(),"text":"محتوى جديد"
    })
    assert r.status_code==201
    third=client.post(f"/api/merchants/{mid}/analyze",headers=H).json()
    assert third["reused"] is False
    assert third["assessment_id"]!=one["assessment_id"]
    detail=client.get(f"/api/merchants/{mid}",headers=H).json()
    assert len(detail["assessments"])==2

def test_empty_evidence_reuses_non_score(client):
    mid=client.post("/api/merchants",headers=H,json={"name":"شركة جود","city":"إب"}).json()["id"]
    one=client.post(f"/api/merchants/{mid}/analyze",headers=H).json()
    two=client.post(f"/api/merchants/{mid}/analyze",headers=H).json()
    assert one["assessment"]["score"] is None
    assert two["reused"] is True
