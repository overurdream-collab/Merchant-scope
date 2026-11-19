"""PostgreSQL-backed API v2. Separate from local SQLite demo.
Run only after PostgreSQL 001+002 migrations, an offline bootstrap and audited deployment.
"""
import os
import uuid
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import HTMLResponse
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Literal
from psycopg.rows import dict_row
from psycopg import IntegrityError, Error
from .pg_identity import login, resolve_session, revoke_session, tenant_transaction
from .scoring import assess, recommend
from . import osm, agent

app=FastAPI(title="MerchantScope Secure API v2",version="0.2.0")
def auth_dsn():return os.environ.get("MERCHANTSCOPE_AUTH_DSN","")
def data_dsn():return os.environ.get("MERCHANTSCOPE_DATA_DSN","")
def ensure_db():
    if not auth_dsn() or not data_dsn():raise HTTPException(503,"Database not configured")
def current(authorization:str|None=Header(None)):
    ensure_db()
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401,"Authentication required")
    identity=resolve_session(auth_dsn(),authorization[7:])
    if not identity:raise HTTPException(401,"Session invalid or expired")
    return identity
def valid_url(s:str):
    u=urlsplit(s)
    if u.scheme not in ("https","http") or not u.hostname or u.username or u.password:
        raise HTTPException(422,"Invalid source URL")
    return s
def norm(s:str):return " ".join(s.strip().lower().replace("أ","ا").replace("إ","ا").replace("آ","ا").split())
def as_dict(conn,sql,args=()):
    conn.row_factory=dict_row
    return conn.execute(sql,args).fetchall()
def one(conn,sql,args=()):
    conn.row_factory=dict_row
    return conn.execute(sql,args).fetchone()
def must_merchant(conn,id:str):
    record=one(conn,"SELECT * FROM ms.merchants WHERE id=%s",(id,))
    if not record:raise HTTPException(404,"Merchant not found")
    return record
@app.middleware("http")
async def headers(req:Request,call_next):
    if req.url.scheme != "https" and (req.client is not None and req.client.host not in ("127.0.0.1","::1","localhost","testclient")):
        from fastapi.responses import JSONResponse
        return JSONResponse({"error":"HTTPS required"},status_code=400)
    response=await call_next(req)
    response.headers["Cache-Control"]="no-store"
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="no-referrer"
    return response
class LoginBody(BaseModel):
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=1,max_length=1024)
    org_id:uuid.UUID
@app.post("/api/v2/login")
def sign_in(body:LoginBody):
    ensure_db()
    token=login(auth_dsn(),body.email,body.password,str(body.org_id))
    if not token:raise HTTPException(401,"Invalid credentials")
    return {"access_token":token,"token_type":"bearer","expires_in_seconds":28800}
@app.get("/api/v2/me")
def me(authorization:str|None=Header(None)):
    identity=current(authorization)
    return {"user_id":str(identity["user_id"]),"org_id":str(identity["org_id"]),"role":str(identity["role"])}
@app.post("/api/v2/logout")
def logout(authorization:str|None=Header(None)):
    current(authorization)
    return {"revoked":revoke_session(auth_dsn(),authorization[7:])}
class MerchantIn(BaseModel):
    name:str=Field(min_length=2,max_length=200)
    city:str=Field(min_length=1,max_length=100)
    category:str|None=None
    market:str|None=None
    governorate:str|None=None
    website:str|None=None
class EvidenceIn(BaseModel):
    platform:str=Field(min_length=2,max_length=70)
    source_url:str
    observed_at:datetime
    published_at:datetime|None=None
    text:str|None=Field(default=None,max_length=10000)
    likes:int|None=Field(default=None,ge=0)
    comments:int|None=Field(default=None,ge=0)
    views:int|None=Field(default=None,ge=0)
class ReviewIn(BaseModel):
    decision:Literal["approved","rejected","changes_requested"]
    notes:str=Field(min_length=3,max_length=2000)

@app.get("/api/v2/merchants")
def merchants(authorization:str|None=Header(None)):
    ident=current(authorization)
    with tenant_transaction(data_dsn(),ident) as c:
        data=as_dict(c,"SELECT id,name,city,category,market,governorate,website,created_at FROM ms.merchants ORDER BY created_at DESC")
        return {"merchants":data}
@app.post("/api/v2/merchants",status_code=201)
def create_merchant(body:MerchantIn,authorization:str|None=Header(None)):
    ident=current(authorization)
    if body.website:valid_url(body.website)
    try:
        with tenant_transaction(data_dsn(),ident) as c:
            record=one(c,"""INSERT INTO ms.merchants(org_id,name,normalized_name,city,category,market,governorate,website,created_by)
             VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
             (ident["org_id"],body.name,norm(body.name),body.city,body.category,body.market,body.governorate,body.website,ident["user_id"]))
            return {"id":record["id"]}
    except IntegrityError as ex:
        raise HTTPException(409,"Merchant duplicate or not permitted") from ex
    except Error as ex:
        raise HTTPException(403,"Database policy denied merchant creation") from ex
@app.get("/api/v2/merchants/{mid}")
def dossier(mid:uuid.UUID,authorization:str|None=Header(None)):
    ident=current(authorization)
    with tenant_transaction(data_dsn(),ident) as c:
        m=must_merchant(c,str(mid))
        e=as_dict(c,"SELECT * FROM ms.evidence WHERE merchant_id=%s ORDER BY observed_at DESC",(mid,))
        a=as_dict(c,"SELECT * FROM ms.assessments WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 10",(mid,))
        r=as_dict(c,"SELECT * FROM ms.recommendations WHERE merchant_id=%s ORDER BY created_at DESC",(mid,))
        return {"merchant":m,"evidence":e,"assessments":a,"recommendations":r}
@app.post("/api/v2/merchants/{mid}/evidence",status_code=201)
def evidence(mid:uuid.UUID,body:EvidenceIn,authorization:str|None=Header(None)):
    ident=current(authorization);valid_url(body.source_url)
    observed=body.observed_at if body.observed_at.tzinfo else body.observed_at.replace(tzinfo=timezone.utc)
    published=body.published_at
    if observed>datetime.now(timezone.utc):raise HTTPException(422,"Future observation")
    if published is not None:
        if published.tzinfo is None:published=published.replace(tzinfo=timezone.utc)
        if published>observed:raise HTTPException(422,"Publication after observation")
    try:
        with tenant_transaction(data_dsn(),ident) as c:
            must_merchant(c,str(mid))
            r=one(c,"""INSERT INTO ms.evidence(org_id,merchant_id,platform,source_url,observed_at,published_at,body,likes,comments,views,created_by)
             VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
             (ident["org_id"],mid,body.platform,body.source_url,observed,published,body.text,body.likes,body.comments,body.views,ident["user_id"]))
            return {"id":r["id"]}
    except Error as ex:raise HTTPException(403,"Database policy denied evidence") from ex
@app.post("/api/v2/merchants/{mid}/analyze")
def analyze(mid:uuid.UUID,authorization:str|None=Header(None)):
    ident=current(authorization)
    try:
        with tenant_transaction(data_dsn(),ident) as c:
            m=must_merchant(c,str(mid))
            evidence_rows=as_dict(c,"SELECT * FROM ms.evidence WHERE merchant_id=%s ORDER BY observed_at DESC LIMIT 200",(mid,))
            channels=as_dict(c,"SELECT * FROM ms.channels WHERE merchant_id=%s",(mid,))
            normalized_e=[{"id":str(e["id"]),"platform":e["platform"],"source_url":e["source_url"],
                "observed_at":e["observed_at"].isoformat(),
                "published_at":e["published_at"].isoformat() if e["published_at"] else None,
                "text":e["body"],"likes":e["likes"],"comments":e["comments"],"views":e["views"]} for e in evidence_rows]
            result=assess(m,normalized_e,channels)
            a=one(c,"INSERT INTO ms.assessments(org_id,merchant_id,result,created_by) VALUES(%s,%s,%s::jsonb,%s) RETURNING id",
                  (ident["org_id"],mid,__import__("json").dumps(result),ident["user_id"]))
            rec_ids=[]
            for rec in recommend(result):
                x=one(c,"""INSERT INTO ms.recommendations(org_id,merchant_id,assessment_id,problem,action,rationale,created_by)
                VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (ident["org_id"],mid,a["id"],rec["problem"],rec["action"],rec["rationale"],ident["user_id"]))
                rec_ids.append(x["id"])
                for eid in rec["evidence_ids"]:
                    c.execute("INSERT INTO ms.recommendation_evidence(org_id,recommendation_id,evidence_id) VALUES(%s,%s,%s)",(ident["org_id"],x["id"],eid))
            return {"assessment":result,"pending_recommendations":rec_ids}
    except Error as ex:raise HTTPException(403,"Database policy denied analysis") from ex
@app.get("/api/v2/reviews")
def pending(authorization:str|None=Header(None)):
    ident=current(authorization)
    with tenant_transaction(data_dsn(),ident) as c:
        return {"pending":as_dict(c,"""SELECT r.*,COALESCE(
            (SELECT json_agg(json_build_object('url',e.source_url,'observed_at',e.observed_at))
             FROM ms.recommendation_evidence re JOIN ms.evidence e
             ON e.id=re.evidence_id AND e.org_id=re.org_id
             WHERE re.recommendation_id=r.id AND re.org_id=r.org_id),
            '[]'::json) AS sources
            FROM ms.recommendations r WHERE r.status='pending_review' ORDER BY r.created_at DESC""")}
@app.post("/api/v2/recommendations/{rid}/review")
def review(rid:uuid.UUID,body:ReviewIn,authorization:str|None=Header(None)):
    ident=current(authorization)
    try:
        with tenant_transaction(data_dsn(),ident) as c:
            record=one(c,"UPDATE ms.recommendations SET status=%s,review_notes=%s WHERE id=%s AND status='pending_review' RETURNING id,status",(body.decision,body.notes,rid))
            if not record:raise HTTPException(404,"Pending recommendation not found")
            return record
    except Error as ex:raise HTTPException(403,"Independent reviewer with source evidence required") from ex

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def secured_dashboard():
    """Public sign-in shell; API calls require verified per-user bearer token."""
    return (Path(__file__).resolve().parent / "secure_dashboard.html").read_text(encoding="utf-8")


# Secure v2 marketing intelligence: all merchant rows remain scoped to the verified
# user and organization. Open-source discovery is preview-first and not automatically imported.
class OSMDiscoveryIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_m: int = Field(default=1200, ge=100, le=3000)
    category: Literal["shop","restaurant","cafe","pharmacy"] = "shop"

class OSMSelected(BaseModel):
    name: str = Field(min_length=2,max_length=200)
    city: str = Field(min_length=1,max_length=100)
    category: str|None = None
    source_url: str

class OSMImportIn(BaseModel):
    confirm: bool = False
    merchants: list[OSMSelected] = Field(min_length=1,max_length=50)

class AgentDraftIn(BaseModel):
    mode: Literal["content","audience","competition","prospecting","proposal"]

def must_write(ident):
    if ident.get("role") not in ("admin","analyst"):
        raise HTTPException(403,"Marketing analyst role required")

@app.post("/api/v2/discovery/osm")
def discover_osm(data:OSMDiscoveryIn,authorization:str|None=Header(None)):
    identity=current(authorization);must_write(identity)
    # All live network traffic is to the fixed Overpass endpoint and is rate-limited.
    return osm.discover(data.lat,data.lon,data.radius_m,data.category)

@app.post("/api/v2/discovery/osm/confirm")
def confirm_osm(data:OSMImportIn,authorization:str|None=Header(None)):
    identity=current(authorization);must_write(identity)
    if not data.confirm:raise HTTPException(422,"Explicit human confirmation required")
    imported=[];skipped=[]
    try:
        with tenant_transaction(data_dsn(),identity) as c:
            for candidate in data.merchants:
                if not re.fullmatch(r"https://www\.openstreetmap\.org/(node|way|relation)/[1-9][0-9]*",candidate.source_url):
                    raise HTTPException(422,"Source must be a valid OpenStreetMap object URL")
                matched=one(c,"SELECT merchant_id FROM ms.channels WHERE platform='openstreetmap' AND url=%s",(candidate.source_url,))
                if matched:
                    skipped.append({"name":candidate.name,"reason":"Source already imported"})
                    continue
                existing=one(c,"SELECT id FROM ms.merchants WHERE normalized_name=%s AND city=%s",
                    (norm(candidate.name),candidate.city))
                if existing:
                    skipped.append({"name":candidate.name,"reason":"Existing merchant name in city"})
                    continue
                merchant_record=one(c,"""INSERT INTO ms.merchants(org_id,name,normalized_name,city,category,created_by)
                  VALUES(%s,%s,%s,%s,%s,%s) RETURNING id""",
                  (identity["org_id"],candidate.name,norm(candidate.name),candidate.city,candidate.category,identity["user_id"]))
                c.execute("INSERT INTO ms.channels(org_id,merchant_id,platform,url) VALUES(%s,%s,%s,%s)",
                    (identity["org_id"],merchant_record["id"],"openstreetmap",candidate.source_url))
                imported.append(merchant_record["id"])
    except IntegrityError as ex:
        raise HTTPException(409,"Duplicate or conflicting merchant source") from ex
    except Error as ex:
        raise HTTPException(403,"Database policy denied OSM import") from ex
    return {"imported":len(imported),"ids":imported,"skipped":skipped,
            "source":"OpenStreetMap","attribution":osm.ATTRIBUTION,"auto_outreach":False,
            "note":"Selected public listings only; no claim of current ownership or operation."}

@app.post("/api/v2/merchants/{mid}/agent-draft")
def secure_agent_draft(mid:uuid.UUID,data:AgentDraftIn,authorization:str|None=Header(None)):
    identity=current(authorization);must_write(identity)
    with tenant_transaction(data_dsn(),identity) as c:
        merchant_record=must_merchant(c,str(mid))
        source_rows=as_dict(c,"SELECT id,platform,source_url,observed_at,published_at,body,likes,comments,views FROM ms.evidence WHERE merchant_id=%s ORDER BY observed_at DESC LIMIT 20",(mid,))
    if not source_rows:
        raise HTTPException(422,"At least one recorded source is required")
    evidence=[
        {"id":str(e["id"]),"platform":e["platform"],"source_url":e["source_url"],
        "observed_at":e["observed_at"].isoformat(),
        "published_at":e["published_at"].isoformat() if e["published_at"] else None,
        "text":e["body"],"likes":e["likes"],"comments":e["comments"],"views":e["views"]}
        for e in source_rows]
    output=agent.run_model(data.mode,merchant_record,evidence)
    reviewed=agent.validate_draft(output,evidence)
    if not reviewed["recommendations"]:
        raise HTTPException(422,"No recommendations with valid source IDs and safe factual content")
    created=[];duplicate=[]
    try:
        with tenant_transaction(data_dsn(),identity) as c:
            must_merchant(c,str(mid))
            c.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",(str(mid)+":agent-draft",))
            for item in reviewed["recommendations"]:
                source_ids=[uuid.UUID(x) for x in item["evidence_ids"]]
                rows=as_dict(c,"SELECT id FROM ms.evidence WHERE merchant_id=%s AND id=ANY(%s::uuid[])",(mid,source_ids))
                if len(rows)!=len(source_ids):
                    raise HTTPException(409,"Source evidence changed; rerun analysis")
                already=one(c,"SELECT id FROM ms.recommendations WHERE merchant_id=%s AND problem=%s AND action=%s AND status='pending_review'",
                    (mid,item["problem"],item["action"]))
                if already:
                    duplicate.append(already["id"]);continue
                r=one(c,"""INSERT INTO ms.recommendations(org_id,merchant_id,problem,action,rationale,created_by)
                      VALUES(%s,%s,%s,%s,%s,%s) RETURNING id""",
                      (identity["org_id"],mid,item["problem"],item["action"],item["rationale"],identity["user_id"]))
                for eid in source_ids:
                    c.execute("INSERT INTO ms.recommendation_evidence(org_id,recommendation_id,evidence_id) VALUES(%s,%s,%s)",
                        (identity["org_id"],r["id"],eid))
                created.append(r["id"])
    except Error as ex:
        raise HTTPException(403,"Database policy denied AI draft creation") from ex
    return {"status":"pending_review","mode":data.mode,"summary":reviewed["summary"],
            "recommendation_ids":created,"existing_pending_ids":duplicate,
            "note":"AI-generated draft only. Reviewer must independently verify all claims and sources before approving."}

@app.get("/api/v2/market")
def secure_market(city:str|None=None,category:str|None=None,authorization:str|None=Header(None)):
    ident=current(authorization)
    with tenant_transaction(data_dsn(),ident) as c:
        query="SELECT id,name,city,category,market FROM ms.merchants WHERE 1=1"
        args=[]
        if city:query+=" AND city=%s";args.append(city)
        if category:query+=" AND category=%s";args.append(category)
        market_rows=as_dict(c,query+" ORDER BY name LIMIT 500",args)
        total=one(c,"SELECT COUNT(*) AS n FROM ms.merchants")["n"]
    sectors={};cities={}
    for item in market_rows:
        sectors[item["category"] or "غير مصنف"]=sectors.get(item["category"] or "غير مصنف",0)+1
        cities[item["city"]]=cities.get(item["city"],0)+1
    return {"count":len(market_rows),"total_registered_in_organization":total,
        "limit":500,"cities":cities,"categories":sectors,"merchants":market_rows,
        "caveat":"Only registered merchants (sample). Not market share or population size."}

@app.get("/api/v2/opportunities")
def secure_opportunities(authorization:str|None=Header(None)):
    ident=current(authorization)
    with tenant_transaction(data_dsn(),ident) as c:
        rows=as_dict(c,"""SELECT m.id,m.name,m.city,m.category,
             (SELECT a.result FROM ms.assessments a WHERE a.merchant_id=m.id ORDER BY a.created_at DESC LIMIT 1) assessment,
             (SELECT COUNT(*) FROM ms.recommendations r WHERE r.merchant_id=m.id AND r.status='approved') approved_recs
             FROM ms.merchants m ORDER BY m.created_at DESC LIMIT 500""")
    for row in rows:
        a=row.pop("assessment") or {}
        score=a.get("score")
        confidence=a.get("confidence")
        if not isinstance(confidence,(float,int)) or isinstance(confidence,bool):
            confidence=0
        if not isinstance(score,(float,int)) or isinstance(score,bool):
            row["opportunity_score"]=None
            row["reasons"]=["Assessment unavailable or insufficient evidence"]
            continue
        priority=round(max(0,100-score)*.5+max(0,min(100,confidence))*.2+min(row["approved_recs"],3)*10)
        row["opportunity_score"]=min(priority,100)
        row["reasons"]=["Measured marketing gap","Evidence confidence","Approved improvement recommendations"]
    rows.sort(key=lambda r:(r["opportunity_score"] is None,-(r["opportunity_score"] or 0)))
    return {"opportunities":rows,"method":"Evidence-based internal ranking only, not a conversion probability."}

@app.get("/api/v2/merchants/{mid}/proposal")
def secure_proposal(mid:uuid.UUID,authorization:str|None=Header(None)):
    ident=current(authorization)
    with tenant_transaction(data_dsn(),ident) as c:
        merchant_record=must_merchant(c,str(mid))
        approved=as_dict(c,"SELECT id,problem,action,rationale FROM ms.recommendations WHERE merchant_id=%s AND status='approved' ORDER BY created_at DESC",(mid,))
        result=[]
        for rec in approved:
            sources=as_dict(c,"""SELECT e.source_url,e.observed_at,e.published_at FROM ms.recommendation_evidence re
                  JOIN ms.evidence e ON e.id=re.evidence_id AND e.org_id=re.org_id
                  WHERE re.recommendation_id=%s AND e.merchant_id=%s""",(rec["id"],mid))
            if not sources:continue
            result.append({"problem":rec["problem"],"recommendation":rec["action"],"rationale":rec["rationale"],"sources":sources})
    return {"merchant":{"id":mid,"name":merchant_record["name"],"city":merchant_record["city"]},
        "status":"draft_for_human_review" if result else "not_ready",
        "services":result,"disclaimer":"Do not claim sales outcomes without validated baselines.",
        "outreach_sent":False}
