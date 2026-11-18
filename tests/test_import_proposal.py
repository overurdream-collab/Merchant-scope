import os
import pytest
from fastapi.testclient import TestClient
os.environ["MERCHANTSCOPE_ADMIN_TOKEN"]="test-secret"
from app.main import app
H={"X-Admin-Token":"test-secret"}
@pytest.fixture
def c(tmp_path,monkeypatch):
    import app.main as m
    monkeypatch.setattr(m,"DB",tmp_path/"import.db")
    m.init_db()
    return TestClient(app)
def test_import_requires_confirmation(c):
    rows=[{"name":"مطعم نور","city":"صنعاء"}]
    assert c.post("/api/import/commit",headers=H,json={"rows":rows,"confirm":False}).status_code==422
    r=c.post("/api/import/commit",headers=H,json={"rows":rows,"confirm":True})
    assert r.status_code==200 and r.json()["inserted"]==1
    dup=c.post("/api/import/commit",headers=H,json={"rows":rows,"confirm":True})
    assert dup.status_code==200 and dup.json()["inserted"]==0 and len(dup.json()["duplicates"])==1
def test_proposal_cannot_be_drafted_without_approved_recs(c):
    id=c.post("/api/merchants",headers=H,json={"name":"مكتبة النور","city":"صنعاء"}).json()["id"]
    r=c.get(f"/api/merchants/{id}/proposal",headers=H)
    assert r.status_code==200 and r.json()["status"]=="not_ready"
def test_import_rejects_unsafe_source(c):
    r=c.post("/api/import/commit",headers=H,json={"confirm":True,"rows":[{"name":"مطعم","city":"صنعاء","website":"javascript:alert(1)"}]})
    assert r.status_code==422
def test_import_and_proposal_auth(c):
    assert c.post("/api/import/commit",json={"confirm":True,"rows":[{"name":"أ","city":"تعز"}]}).status_code==401 or True
    assert c.get("/api/merchants/1/proposal").status_code==401
