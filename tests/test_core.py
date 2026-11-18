import os
from datetime import datetime,timezone,timedelta
import pytest
from fastapi.testclient import TestClient
os.environ["MERCHANTSCOPE_ADMIN_TOKEN"]="test-secret"
from app.main import app,init_db
from app.scoring import assess,recommend
H={"X-Admin-Token":"test-secret"}

@pytest.fixture
def client(tmp_path,monkeypatch):
    import app.main as main
    monkeypatch.setattr(main,"DB",tmp_path/"test.db")
    main.init_db()
    return TestClient(app)

def add(client):
    response=client.post("/api/merchants",headers=H,json={"name":"متجر الأمل","city":"صنعاء"})
    assert response.status_code==201,response.text
    return response.json()["id"]

def test_auth(client):
    assert client.get("/api/merchants").status_code==401

def test_dedup(client):
    add(client)
    assert client.post("/api/merchants",headers=H,json={"name":"متجر الأمل","city":"صنعاء"}).status_code==409

def test_missing_data_is_not_zero():
    r=assess({"name":"store","website":None},[],[])
    assert r["score"] is None and r["coverage"]==0 and r["dimensions"]["engagement"] is None and recommend(r)==[]

def test_review_flow(client):
    mid=add(client)
    for day in (2,20,40):
        response=client.post(f"/api/merchants/{mid}/evidence",headers=H,json={
          "platform":"facebook","source_url":f"https://example.org/post/{day}",
          "observed_at":(datetime.now(timezone.utc)-timedelta(days=day)).isoformat(),"text":"منشور تجريبي بدون معلومات عن المنتج"})
        assert response.status_code==201
    result=client.post(f"/api/merchants/{mid}/analyze",headers=H).json()
    assert result["recommendations_created"]>0
    rid=client.get("/api/reviews",headers=H).json()[0]["id"]
    assert client.post(f"/api/recommendations/{rid}/review",headers=H,json={"decision":"approved","notes":"تم فحص الأدلة"}).status_code==200
    assert client.post(f"/api/recommendations/{rid}/review",headers=H,json={"decision":"approved","notes":"إعادة"}).status_code==409

def test_outreach_requires_approval(client):
    mid=add(client)
    assert client.post(f"/api/merchants/{mid}/lead",headers=H,json={"stage":"contacted"}).status_code==409
    assert client.post(f"/api/merchants/{mid}/outreach-approval",headers=H,json={"approved":True,"notes":"تمت المراجعة"}).status_code==200
    assert client.post(f"/api/merchants/{mid}/lead",headers=H,json={"stage":"contacted"}).status_code==200

def test_unsafe_link(client):
    mid=add(client)
    assert client.post(f"/api/merchants/{mid}/channels",headers=H,json={"platform":"web","url":"javascript:alert(1)"}).status_code==422

def test_csv_preview(client):
    add(client)
    data=b"name,city\nnew,Aden\nnew,Aden\n"
    response=client.post("/api/import/preview",headers=H,files={"file":("merchants.csv",data,"text/csv")})
    assert [x["status"] for x in response.json()["preview"]]==["new","duplicate_in_file"]
    assert response.json()["committed"] is False
