import os
import pytest
from fastapi.testclient import TestClient
os.environ["MERCHANTSCOPE_ADMIN_TOKEN"]="test-secret"
from app.main import app
from app import osm
H={"X-Admin-Token":"test-secret"}

@pytest.fixture
def client(tmp_path,monkeypatch):
    import app.main as m
    monkeypatch.setattr(m,"DB",tmp_path/"osm.db")
    m.init_db()
    return TestClient(app)

def test_osm_preview_and_confirmation(client,monkeypatch):
    sample={"results":[{"name":"متجر السلام","category":"supermarket","source_url":"https://www.openstreetmap.org/node/123","lat":15.3,"lon":44.2}],"source":"OpenStreetMap"}
    monkeypatch.setattr(osm,"discover",lambda *args:sample)
    r=client.post("/api/discovery/osm",headers=H,json={"lat":15.3,"lon":44.2,"radius_m":1000,"category":"shop"})
    assert r.status_code==200 and r.json()["results"][0]["name"]=="متجر السلام"
    body={"confirm":True,"merchants":[{"name":"متجر السلام","city":"صنعاء","category":"supermarket","source_url":"https://www.openstreetmap.org/node/123"}]}
    assert client.post("/api/discovery/osm/commit",headers=H,json={"confirm":False,"merchants":body["merchants"]}).status_code==422
    assert client.post("/api/discovery/osm/commit",headers=H,json=body).json()["imported"]==1
    assert client.post("/api/discovery/osm/commit",headers=H,json=body).json()["imported"]==0
    mid=client.get("/api/merchants",headers=H).json()[0]["id"]
    channels=client.get(f"/api/merchants/{mid}",headers=H).json()["channels"]
    assert channels[0]["platform"]=="openstreetmap"

def test_osm_blocks_unverified_urls(client):
    data={"confirm":True,"merchants":[{"name":"متجر الصباح","city":"تعز","source_url":"https://example.org/node/1"}]}
    assert client.post("/api/discovery/osm/commit",headers=H,json=data).status_code==422

def test_osm_requires_auth(client):
    assert client.post("/api/discovery/osm",json={"lat":15,"lon":44,"category":"shop"}).status_code==401

def test_osm_parameter_validation(client):
    assert client.post("/api/discovery/osm",headers=H,json={"lat":190,"lon":44}).status_code==422

def test_osm_csv_export_retains_attribution(client):
    payload={"confirm":True,"merchants":[{"name":"متجر الواحة","city":"صنعاء","source_url":"https://www.openstreetmap.org/way/1234"}]}
    assert client.post("/api/discovery/osm/commit",headers=H,json=payload).status_code==200
    exported=client.get("/api/export.csv",headers=H)
    assert exported.status_code==200
    assert "osm_source" in exported.text
    assert "OpenStreetMap contributors" in exported.text
    assert "https://www.openstreetmap.org/way/1234" in exported.text
