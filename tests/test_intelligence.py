import os
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
os.environ["MERCHANTSCOPE_ADMIN_TOKEN"] = "test-secret"
from app.main import app
H={"X-Admin-Token":"test-secret"}

@pytest.fixture
def client(tmp_path, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "DB", tmp_path / "market.db")
    main.init_db()
    return TestClient(app)

def seed(c,name,city="صنعاء",category="مطاعم"):
    r=c.post("/api/merchants",headers=H,json={"name":name,"city":city,"category":category})
    assert r.status_code==201,r.text
    return r.json()["id"]

def test_dashboard_served(client):
    r=client.get("/")
    assert r.status_code==200
    assert "مرصد التجار" in r.text

def test_market_and_coverage(client):
    a=seed(client,"مطعم الصفا")
    b=seed(client,"مطعم الجودة","تعز")
    r=client.get("/api/market?city=صنعاء",headers=H)
    assert r.status_code==200
    assert r.json()["merchants_count"]==1
    assert r.json()["merchants"][0]["id"]==a
    v=client.get(f"/api/compare?merchant_ids={a},{b}",headers=H)
    assert v.status_code==200
    assert all(x["assessment"] is None for x in v.json()["results"])
    assert client.get(f"/api/compare?merchant_ids={a}",headers=H).status_code==422

def test_overview_and_opportunities_missing_evidence(client):
    seed(client,"مؤسسة الشمس")
    s=client.get("/api/overview",headers=H)
    assert s.json()["merchants"]==1
    r=client.get("/api/opportunities",headers=H)
    assert r.status_code==200
    assert r.json()["opportunities"][0]["opportunity_score"] is None

def test_catalog_is_non_executing(client):
    r=client.get("/api/skills",headers=H).json()
    assert r["status"]=="reference_only_not_executable"
    assert len(r["skills"])==7
    assert all(not x["installed"] for x in r["skills"])

def test_new_routes_require_auth(client):
    for path in ("/api/market","/api/overview","/api/opportunities","/api/skills","/api/compare?merchant_ids=1,2"):
        assert client.get(path).status_code==401
