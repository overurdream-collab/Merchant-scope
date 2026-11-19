"""PostgreSQL RLS acceptance tests. Executed by the dedicated PG CI job."""
import os
from pathlib import Path
from uuid import uuid4
import pytest

@pytest.fixture(scope="module")
def pg():
    dsn=os.environ.get("PG_TEST_DSN")
    if not dsn: pytest.skip("PostgreSQL service not configured")
    psycopg=pytest.importorskip("psycopg")
    with psycopg.connect(dsn,autocommit=True) as c:
        c.execute((Path(__file__).parents[1]/"db"/"postgres"/"001_init.sql").read_text(encoding="utf-8"))
        c.execute((Path(__file__).parents[1]/"db"/"postgres"/"002_identity.sql").read_text(encoding="utf-8"))
        org_a,org_b,analyst,reviewer,other=[uuid4() for _ in range(5)]
        for org,name in ((org_a,"Team A"),(org_b,"Team B")):
            c.execute("INSERT INTO ms.organizations(id,name) VALUES (%s,%s)",(org,name))
        for org,user,role in ((org_a,analyst,"analyst"),(org_a,reviewer,"reviewer"),(org_b,other,"analyst")):
            c.execute("INSERT INTO ms.memberships(org_id,user_id,role) VALUES(%s,%s,%s)",(org,user,role))
        m1,m2=uuid4(),uuid4()
        for mid,org,name,creator in ((m1,org_a,"A merchant",analyst),(m2,org_b,"B merchant",other)):
            c.execute("INSERT INTO ms.merchants(id,org_id,name,normalized_name,city,created_by) VALUES(%s,%s,%s,%s,%s,%s)",
                      (mid,org,name,name.lower(),"Sanaa",creator))
        yield dict(db=c,org_a=org_a,org_b=org_b,analyst=analyst,reviewer=reviewer,other=other,m1=m1,m2=m2)

def assume(c,user,org):
    c.execute("SET ROLE merchant_runtime")
    c.execute("SELECT set_config('app.user_id',%s,false)",(str(user),))
    c.execute("SELECT set_config('app.org_id',%s,false)",(str(org),))

def unassume(c):
    c.execute("RESET ROLE")
    c.execute("RESET app.user_id")
    c.execute("RESET app.org_id")

def test_rls_blocks_other_tenant(pg):
    c=pg["db"]
    assume(c,pg["analyst"],pg["org_a"])
    try:
        names=[x[0] for x in c.execute("SELECT name FROM ms.merchants").fetchall()]
        assert names==["A merchant"]
        assert c.execute("SELECT count(*) FROM ms.merchants WHERE id=%s",(pg["m2"],)).fetchone()[0]==0
    finally:unassume(c)

def test_reviewer_read_only_on_merchants(pg):
    c=pg["db"]
    assume(c,pg["reviewer"],pg["org_a"])
    try:
        assert c.execute("SELECT count(*) FROM ms.merchants").fetchone()[0]==1
        outcome=c.execute("UPDATE ms.merchants SET name='tampered' WHERE id=%s",(pg["m1"],))
        assert outcome.rowcount==0
    finally:unassume(c)

def test_independent_reviewer_and_source_evidence_required(pg):
    c=pg["db"]
    rec_id=uuid4()
    c.execute("INSERT INTO ms.recommendations(id,org_id,merchant_id,problem,action,created_by) VALUES(%s,%s,%s,%s,%s,%s)",
              (rec_id,pg["org_a"],pg["m1"],"Missing product details","Test clearer descriptions",pg["analyst"]))
    assume(c,pg["reviewer"],pg["org_a"])
    try:
        with pytest.raises(Exception):
            c.execute("UPDATE ms.recommendations SET status='approved' WHERE id=%s",(rec_id,))
    finally:unassume(c)
    evidence_id=uuid4()
    c.execute("INSERT INTO ms.evidence(id,org_id,merchant_id,platform,source_url,observed_at,created_by) VALUES(%s,%s,%s,%s,%s,now(),%s)",
              (evidence_id,pg["org_a"],pg["m1"],"website","https://example.org/p",pg["analyst"]))
    c.execute("INSERT INTO ms.recommendation_evidence(org_id,recommendation_id,evidence_id) VALUES(%s,%s,%s)",
              (pg["org_a"],rec_id,evidence_id))
    assume(c,pg["analyst"],pg["org_a"])
    try:
        with pytest.raises(Exception):
            c.execute("UPDATE ms.recommendations SET status='approved' WHERE id=%s",(rec_id,))
    finally:unassume(c)
    assume(c,pg["reviewer"],pg["org_a"])
    try:
        outcome=c.execute("UPDATE ms.recommendations SET status='approved' WHERE id=%s",(rec_id,))
        assert outcome.rowcount==1
        assert c.execute("SELECT status::text FROM ms.recommendations WHERE id=%s",(rec_id,)).fetchone()[0]=="approved"
    finally:unassume(c)

def test_audit_is_not_user_writable(pg):
    c=pg["db"]
    assume(c,pg["analyst"],pg["org_a"])
    try:
        with pytest.raises(Exception):
            c.execute("DELETE FROM ms.audit_events")
        assert c.execute("SELECT count(*) FROM ms.audit_events").fetchone()[0]>0
    finally:unassume(c)

def test_runtime_cannot_read_accounts_or_sessions(pg):
    c=pg["db"]
    assume(c,pg["analyst"],pg["org_a"])
    try:
        with pytest.raises(Exception): c.execute("SELECT * FROM ms.user_accounts")
        with pytest.raises(Exception): c.execute("SELECT * FROM ms.sessions")
    finally:unassume(c)

def test_user_session_and_tenant_transaction(pg):
    from app.pg_identity import bootstrap_admin,login,resolve_session,revoke_session,tenant_transaction
    from uuid import uuid4
    dsn=os.environ["PG_TEST_DSN"]
    suffix=uuid4().hex[:8]
    details=bootstrap_admin(dsn,"Test Organization "+suffix,"test"+suffix+"@example.org","strong test password 12345")
    tok=login(dsn,"test"+suffix+"@example.org","strong test password 12345",details["org_id"])
    assert tok and len(tok)>30
    assert login(dsn,"test"+suffix+"@example.org","wrong pass",details["org_id"]) is None
    identity=resolve_session(dsn,tok)
    assert str(identity["user_id"])==details["user_id"]
    with tenant_transaction(dsn,identity) as db:
        db.execute("INSERT INTO ms.merchants(org_id,name,normalized_name,city,created_by) VALUES(%s,%s,%s,%s,%s)",
             (details["org_id"],"Sample Brand","sample brand","Sanaa",details["user_id"]))
        assert db.execute("SELECT count(*) FROM ms.merchants").fetchone()[0]==1
    assert revoke_session(dsn,tok)
    assert resolve_session(dsn,tok) is None

def test_secure_api_full_merchant_review_cycle(pg,monkeypatch):
    from fastapi.testclient import TestClient
    from app.pg_api import app
    from app.pg_identity import bootstrap_admin,hash_password
    from uuid import uuid4
    from datetime import datetime,timezone
    dsn=os.environ["PG_TEST_DSN"]
    monkeypatch.setenv("MERCHANTSCOPE_AUTH_DSN",dsn)
    monkeypatch.setenv("MERCHANTSCOPE_DATA_DSN",dsn)
    suffix=uuid4().hex[:8]
    email="analyst"+suffix+"@example.org"
    details=bootstrap_admin(dsn,"Marketing "+suffix,email,"complex password string 123456")
    reviewer=uuid4()
    pg["db"].execute("INSERT INTO ms.user_accounts(id,email,password_hash) VALUES(%s,%s,%s)",
         (reviewer,"reviewer"+suffix+"@example.org",hash_password("reviewer secret password 123456")))
    pg["db"].execute("INSERT INTO ms.memberships(org_id,user_id,role) VALUES(%s,%s,'reviewer')",
         (details["org_id"],reviewer))
    with TestClient(app) as c:
        shell=c.get("/")
        assert shell.status_code==200 and 'مرصد التجار' in shell.text
        assert 'id="loginForm"' in shell.text
        res=c.post("/api/v2/login",json={"email":email,"password":"complex password string 123456","org_id":details["org_id"]})
        assert res.status_code==200,res.text
        token=res.json()["access_token"]
        H={"Authorization":"Bearer "+token}
        assert c.get("/api/v2/me",headers=H).json()["role"]=="admin"
        merchant=c.post("/api/v2/merchants",headers=H,json={"name":"المتجر التجريبي","city":"صنعاء","category":"تجزئة"})
        assert merchant.status_code==201,merchant.text
        mid=merchant.json()["id"]
        for n in range(3):
            at=datetime.now(timezone.utc).isoformat()
            ev=c.post(f"/api/v2/merchants/{mid}/evidence",headers=H,json={"platform":"facebook","source_url":f"https://example.org/post/{n}","observed_at":at,"text":"منتج تجريبي"})
            assert ev.status_code==201,ev.text
        a=c.post(f"/api/v2/merchants/{mid}/analyze",headers=H)
        assert a.status_code==200,a.text
        assert len(a.json()["pending_recommendations"])>=1
        rid=a.json()["pending_recommendations"][0]
        assert c.post(f"/api/v2/recommendations/{rid}/review",headers=H,json={"decision":"approved","notes":"المراجعة"}).status_code==403
        reviewer_token=c.post("/api/v2/login",json={"email":"reviewer"+suffix+"@example.org","password":"reviewer secret password 123456","org_id":details["org_id"]}).json()["access_token"]
        R={"Authorization":"Bearer "+reviewer_token}
        assert c.get("/api/v2/merchants",headers=R).status_code==200
        assert c.post("/api/v2/merchants",headers=R,json={"name":"غير مسموح","city":"صنعاء"}).status_code==403
        reviewed=c.post(f"/api/v2/recommendations/{rid}/review",headers=R,json={"decision":"approved","notes":"فحص الأدلة"})
        assert reviewed.status_code==200,reviewed.text
        assert c.get("/api/v2/merchants",headers=H).json()["merchants"]
        assert c.post("/api/v2/logout",headers=H).json()["revoked"] is True
        assert c.get("/api/v2/me",headers=H).status_code==401

def test_admin_can_provision_independent_reviewer_offline(pg):
    from app.pg_users import create_user
    from app.pg_identity import login, resolve_session
    from uuid import uuid4
    dsn=os.environ["PG_TEST_DSN"]
    suffix=uuid4().hex[:8]
    admin_org=uuid4()
    pg["db"].execute("INSERT INTO ms.organizations(id,name) VALUES(%s,%s)",(admin_org,"Provision Test "+suffix))
    email="reviewer"+suffix+"@example.org"
    identity=create_user(dsn,str(admin_org),email,"strong distinct password 1234","reviewer")
    assert identity["role"]=="reviewer"
    assert identity["org_id"]==str(admin_org)
    token=login(dsn,email,"strong distinct password 1234",str(admin_org))
    assert token
    resolved=resolve_session(dsn,token)
    assert str(resolved["role"])=="reviewer"
    with pytest.raises(ValueError):
        create_user(dsn,str(admin_org),email,"another password string 1234","analyst")
    with pytest.raises(ValueError):
        create_user(dsn,str(admin_org),"bad-email","strong password string 1234","analyst")

def test_secure_portfolio_is_tenant_scoped_and_missing_scores_nullable(pg,monkeypatch):
    from uuid import uuid4
    from app.pg_identity import bootstrap_admin
    from app.pg_api import app
    from fastapi.testclient import TestClient
    dsn=os.environ["PG_TEST_DSN"]
    monkeypatch.setenv("MERCHANTSCOPE_AUTH_DSN",dsn)
    monkeypatch.setenv("MERCHANTSCOPE_DATA_DSN",dsn)
    suffix=uuid4().hex[:8]
    info=bootstrap_admin(dsn,"Scoped Reporting "+suffix,"report"+suffix+"@example.org","high entropy password 12345")
    with TestClient(app) as client:
        result=client.post("/api/v2/login",json={"email":"report"+suffix+"@example.org","password":"high entropy password 12345","org_id":info["org_id"]})
        assert result.status_code==200,result.text
        headers={"Authorization":"Bearer "+result.json()["access_token"]}
        empty=client.get("/api/v2/reports/portfolio",headers=headers)
        assert empty.status_code==200,empty.text
        assert empty.json()["merchant_count"]==0
        assert empty.json()["average_observed_score"] is None
        assert client.get("/api/v2/reports/portfolio").status_code==401
        created=client.post("/api/v2/merchants",headers=headers,json={"name":"مصنع نموذجي","city":"صنعاء","category":"أغذية"})
        assert created.status_code==201,created.text
        portfolio=client.get("/api/v2/reports/portfolio?city=صنعاء",headers=headers)
        assert portfolio.status_code==200,portfolio.text
        data=portfolio.json()
        assert data["merchant_count"]==1
        assert data["without_usable_score"]==1
        assert data["merchants"][0]["name"]=="مصنع نموذجي"
        assert data["merchants"][0]["score"] is None
        other=client.get("/api/v2/reports/portfolio?city=تعز",headers=headers)
        assert other.json()["merchant_count"]==0

def test_secure_sales_pipeline_requires_independent_outreach_approval(pg,monkeypatch):
    from app.pg_api import app
    from app.pg_identity import bootstrap_admin,hash_password
    from fastapi.testclient import TestClient
    from datetime import datetime,timezone
    from uuid import uuid4
    suffix=uuid4().hex[:9]
    dsn=os.environ["PG_TEST_DSN"]
    monkeypatch.setenv("MERCHANTSCOPE_AUTH_DSN",dsn)
    monkeypatch.setenv("MERCHANTSCOPE_DATA_DSN",dsn)
    admin_email="pipeline"+suffix+"@example.org"
    info=bootstrap_admin(dsn,"Pipeline "+suffix,admin_email,"admin password for test 12345")
    reviewer_email="pipeline-reviewer"+suffix+"@example.org"
    user=uuid4()
    pg["db"].execute("INSERT INTO ms.user_accounts(id,email,password_hash) VALUES(%s,%s,%s)",
            (user,reviewer_email,hash_password("reviewer password for test 12345")))
    pg["db"].execute("INSERT INTO ms.memberships(org_id,user_id,role) VALUES(%s,%s,'reviewer')",(info["org_id"],user))
    with TestClient(app) as c:
        def login(email,password):
            resp=c.post("/api/v2/login",json={"email":email,"password":password,"org_id":info["org_id"]})
            assert resp.status_code==200,resp.text
            return {"Authorization":"Bearer "+resp.json()["access_token"]}
        admin=login(admin_email,"admin password for test 12345")
        reviewer=login(reviewer_email,"reviewer password for test 12345")
        m=c.post("/api/v2/merchants",headers=admin,json={"name":"متجر الفرص","city":"صنعاء"})
        assert m.status_code==201,m.text
        mid=m.json()["id"]
        response=c.get("/api/v2/opportunities",headers=admin)
        assert response.status_code==200,response.text
        assert response.json()["opportunities"][0]["opportunity_score"] is None
        lead=c.post(f"/api/v2/merchants/{mid}/lead",headers=admin,json={"stage":"qualified"})
        assert lead.status_code==200,lead.text
        denied=c.post(f"/api/v2/merchants/{mid}/lead",headers=admin,json={"stage":"contacted"})
        assert denied.status_code==403,denied.text
        assert c.post(f"/api/v2/merchants/{mid}/outreach-approval",headers=admin,json={"approved":True}).status_code==403
        approved=c.post(f"/api/v2/merchants/{mid}/outreach-approval",headers=reviewer,json={"approved":True})
        assert approved.status_code==200,approved.text
        assert approved.json()["outreach_approved"] is True
        contacted=c.post(f"/api/v2/merchants/{mid}/lead",headers=admin,json={"stage":"contacted"})
        assert contacted.status_code==200,contacted.text
        assert contacted.json()["stage"]=="contacted"
        assert c.get(f"/api/v2/merchants/{mid}/proposal",headers=admin).json()["status"]=="not_ready"

def test_secure_competitor_comparison_is_tenant_isolated(pg,monkeypatch):
    from app.pg_api import app
    from app.pg_identity import bootstrap_admin
    from fastapi.testclient import TestClient
    from uuid import uuid4
    suffix=uuid4().hex[:8]
    dsn=os.environ["PG_TEST_DSN"]
    monkeypatch.setenv("MERCHANTSCOPE_AUTH_DSN",dsn)
    monkeypatch.setenv("MERCHANTSCOPE_DATA_DSN",dsn)
    identity=bootstrap_admin(dsn,"Comparison "+suffix,"compare"+suffix+"@example.org","complex test password 12345")
    with TestClient(app) as c:
        auth=c.post("/api/v2/login",json={"email":"compare"+suffix+"@example.org","password":"complex test password 12345","org_id":identity["org_id"]})
        assert auth.status_code==200,auth.text
        headers={"Authorization":"Bearer "+auth.json()["access_token"]}
        ids=[]
        for name in ("تاجر أ","تاجر ب"):
            resp=c.post("/api/v2/merchants",headers=headers,json={"name":name,"city":"صنعاء"})
            assert resp.status_code==201,resp.text
            ids.append(resp.json()["id"])
        result=c.get("/api/v2/compare?ids="+",".join(ids),headers=headers)
        assert result.status_code==200,result.text
        assert len(result.json()["results"])==2
        assert all(x["score"] is None for x in result.json()["results"])
        assert c.get("/api/v2/compare?ids="+ids[0],headers=headers).status_code==422
        assert c.get("/api/v2/compare?ids="+",".join(ids)).status_code==401
        # Merchant from a different organization must never be returned.
        foreign=c.get("/api/v2/compare?ids="+ids[0]+","+str(pg["m1"]),headers=headers)
        assert foreign.status_code==404
