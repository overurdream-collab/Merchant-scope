import os
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
os.environ["MERCHANTSCOPE_ADMIN_TOKEN"]="test-secret"
from app.main import app
from app import agent
H={"X-Admin-Token":"test-secret"}

@pytest.fixture
def client(tmp_path,monkeypatch):
    import app.main as m
    monkeypatch.setattr(m,"DB",tmp_path/"agent.db")
    m.init_db()
    return TestClient(app)

def seed(c):
    mid=c.post("/api/merchants",headers=H,json={"name":"متجر العنبر","city":"صنعاء"}).json()["id"]
    r=c.post(f"/api/merchants/{mid}/evidence",headers=H,json={"platform":"facebook","source_url":"https://example.org/post/123","observed_at":datetime.now(timezone.utc).isoformat(),"text":"عرض منتجات وخصومات"})
    assert r.status_code==201,r.text
    return mid,r.json()["id"]

def test_draft_without_model_is_unavailable(client,monkeypatch):
    mid,_=seed(client)
    monkeypatch.delenv("MERCHANTSCOPE_OLLAMA_MODEL",raising=False)
    r=client.post(f"/api/merchants/{mid}/agent-draft",headers=H,json={"mode":"content"})
    assert r.status_code==503

def test_model_draft_is_pending_review_only(client,monkeypatch):
    mid,eid=seed(client)
    monkeypatch.setenv("MERCHANTSCOPE_OLLAMA_MODEL","test-model")
    def fake(mode,m,e):
        return {"summary":"ملخص غير معتمد","recommendations":[{"problem":"ضعف وصف المنتجات المعروضة","action":"تجربة منشورات تتضمن معلومات المنتج والسعر","rationale":"العينة المنشورة","priority":"high","evidence_ids":[eid]}]}
    monkeypatch.setattr(agent,"run_model",fake)
    r=client.post(f"/api/merchants/{mid}/agent-draft",headers=H,json={"mode":"content"})
    assert r.status_code==200,r.text
    assert r.json()["status"]=="pending_review"
    detail=client.get(f"/api/merchants/{mid}",headers=H).json()
    assert detail["recommendations"][0]["status"]=="pending_review"
    assert str(eid) in detail["recommendations"][0]["evidence_ids"]
    assert client.get(f"/api/merchants/{mid}/proposal",headers=H).json()["status"]=="not_ready"
    assert len(client.get(f"/api/merchants/{mid}/agent-history",headers=H).json())==1

def test_hallucinated_evidence_cannot_create_draft(client,monkeypatch):
    mid,_=seed(client)
    monkeypatch.setattr(agent,"run_model",lambda *a:{"summary":"fake","recommendations":[{"problem":"مشكلة غير موثقة","action":"إجراء غير موثق","evidence_ids":[999999],"priority":"high"}]})
    r=client.post(f"/api/merchants/{mid}/agent-draft",headers=H,json={"mode":"content"})
    assert r.status_code==422
    assert client.get(f"/api/merchants/{mid}/agent-history",headers=H).json()==[]

def test_skill_manifest_is_pinned():
    assert len(agent.UPSTREAM_REVISION)==40
    assert agent.SKILL_REFERENCES["prospecting"]=="find-local-clients"
