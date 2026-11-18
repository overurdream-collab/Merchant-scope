import os
from datetime import datetime,timezone,timedelta
import pytest
from fastapi.testclient import TestClient
os.environ["MERCHANTSCOPE_ADMIN_TOKEN"]="test-secret"
from app.main import app
H={"X-Admin-Token":"test-secret"}

@pytest.fixture
def client(tmp_path,monkeypatch):
    import app.main as m
    monkeypatch.setattr(m,"DB",tmp_path/"revisions.db")
    monkeypatch.delenv("MERCHANTSCOPE_REVIEWER_TOKEN",raising=False)
    m.init_db()
    return TestClient(app)

def merchant(c,name):
    r=c.post("/api/merchants",headers=H,json={"name":name,"city":"صنعاء"})
    assert r.status_code==201,r.text
    return r.json()["id"]

def pending(c,mid):
    for n in (2,20,39):
        at=(datetime.now(timezone.utc)-timedelta(days=n)).isoformat()
        r=c.post(f"/api/merchants/{mid}/evidence",headers=H,json={"platform":"web","source_url":f"https://example.org/{n}","observed_at":at,"published_at":at,"text":"محتوى قصير"})
        assert r.status_code==201,r.text
    analysis=c.post(f"/api/merchants/{mid}/analyze",headers=H)
    assert analysis.status_code==200,analysis.text
    recs=c.get("/api/reviews",headers=H).json()
    assert recs
    return recs[0]

def test_revision_roundtrip_with_audit(client):
    mid=merchant(client,"متجر المراجعة")
    r=pending(client,mid)
    rid=r["id"]
    assert client.post(f"/api/recommendations/{rid}/review",headers=H,json={"decision":"changes_requested","notes":"تحديد نتيجة قابلة للقياس"}).status_code==200
    requests=client.get("/api/recommendations/changes",headers=H).json()
    assert any(x["id"]==rid for x in requests)
    ids=__import__('json').loads(r["evidence_ids"])
    update={"problem":"معلومات المنتج غير كافية في عينة المنشورات","action":"اختبار عرض مواصفات المنتج وقياس استجابة المتابعين","rationale":"ثلاثة منشورات موثقة","priority":"high","evidence_ids":ids}
    res=client.post(f"/api/recommendations/{rid}/resubmit",headers=H,json=update)
    assert res.status_code==200,res.text
    assert res.json()["status"]=="pending_review"
    assert client.post(f"/api/recommendations/{rid}/review",headers=H,json={"decision":"approved","notes":"تحققت الأدلة"}).status_code==200
    assert client.post(f"/api/recommendations/{rid}/resubmit",headers=H,json=update).status_code==409
    audit=client.get("/api/audit",headers=H).json()
    entry=next(x for x in audit if x["action"]=="resubmission")
    details=__import__('json').loads(entry["details"])
    assert details["before"]["status"]=="changes_requested"
    assert details["before"]["review_notes"]=="تحديد نتيجة قابلة للقياس"
    assert details["after"]["action"]==update["action"]

def test_cannot_cite_evidence_from_another_merchant(client):
    mid=merchant(client,"مؤسسة الأولى")
    r=pending(client,mid)
    rid=r["id"]
    assert client.post(f"/api/recommendations/{rid}/review",headers=H,json={"decision":"changes_requested","notes":"دليل أوضح"}).status_code==200
    other=merchant(client,"مؤسسة الثانية")
    response=client.post(f"/api/merchants/{other}/evidence",headers=H,json={"platform":"web","source_url":"https://example.org/other","observed_at":datetime.now(timezone.utc).isoformat()})
    assert response.status_code==201,response.text
    body={"problem":"تعديل مع دليل غير متعلق","action":"إجراء تحديث لنشر البيانات","evidence_ids":[response.json()["id"]]}
    assert client.post(f"/api/recommendations/{rid}/resubmit",headers=H,json=body).status_code==422

def test_revision_rejects_unlinked_evidence(client):
    mid=merchant(client,"مؤسسة ثالثة")
    r=pending(client,mid)
    rid=r["id"]
    assert client.post(f"/api/recommendations/{rid}/review",headers=H,json={"decision":"changes_requested","notes":"الرجاء التعديل"}).status_code==200
    payload={"problem":"مشكلة موثقة في العينة","action":"اقتراح تجربة محتوى واضح","evidence_ids":[999999]}
    assert client.post(f"/api/recommendations/{rid}/resubmit",headers=H,json=payload).status_code==422
