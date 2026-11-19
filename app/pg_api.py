"""PostgreSQL-backed API v2. Separate from local SQLite demo.
Run only after PostgreSQL 001+002 migrations, an offline bootstrap and audited deployment.
"""
import os
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit
import ipaddress
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import HTMLResponse
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Literal
from psycopg.rows import dict_row
from psycopg import IntegrityError, Error
from .pg_identity import login, resolve_session, revoke_session, tenant_transaction
from .scoring import assess, recommend
from . import osm

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
    try:
        u=urlsplit(s)
        hostname=u.hostname
        port=u.port  # Reject malformed/non-numeric ports before storing provenance.
    except ValueError as exc:
        raise HTTPException(422,"Invalid source URL") from exc
    if (len(s)>2048 or any(ch.isspace() or ord(ch)<32 or 127<=ord(ch)<=159 or ch=="\\" or ch in ("\u200b","\u200c","\u200d","\u2060","\ufeff") for ch in s)
        or u.scheme not in ("https","http") or not u.hostname
        or u.username or u.password or u.fragment):
        raise HTTPException(422,"Invalid source URL")
    try:
        address=ipaddress.ip_address(u.hostname)
    except ValueError:
        address=None
    if address is not None and not address.is_global:
        raise HTTPException(422,"Private or non-public source URL")
    hostname = u.hostname.lower().rstrip(".")
    # A source hostname must be an unambiguous public DNS name or global IP.
    # Reject percent-encoded authority, IDNA ambiguity and malformed DNS labels.
    # The URL is provenance metadata, not a destination we should resolve here.
    if address is None:
        import re
        if (not hostname.isascii() or "%" in hostname or len(hostname)>253
            or "." not in hostname or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                                      for label in hostname.split("."))):
            raise HTTPException(422,"Invalid source hostname")
    # URL consumers may resolve integer, hexadecimal or octal IPv4 spellings
    # (for example 2130706433 or 0x7f000001) to a loopback address.
    # Do not store these ambiguous hostnames as trusted public provenance.
    labels = hostname.split(".")
    numeric_label = lambda label: bool(label) and (label.isascii() and label.isdigit() or label.lower().startswith("0x") and all(c in "0123456789abcdef" for c in label[2:].lower()) and len(label)>2)
    if (hostname in ("localhost",) or hostname.endswith((".localhost",".local",".internal",".test",".invalid",".onion",".home.arpa"))
        or all(numeric_label(label) for label in labels)):
        raise HTTPException(422,"Private or non-public source URL")
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
        return {"pending":as_dict(c,"SELECT * FROM ms.recommendations WHERE status='pending_review' ORDER BY created_at DESC")}
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


@app.get("/api/v2/reports/portfolio")
def secure_portfolio(city:str|None=None,category:str|None=None,authorization:str|None=Header(None)):
    """Tenant-scoped portfolio reporting; no extrapolation to an entire market."""
    ident=current(authorization)
    with tenant_transaction(data_dsn(),ident) as c:
        query="SELECT id,name,city,category FROM ms.merchants WHERE 1=1"
        args=[]
        if city:
            query+=" AND city=%s"
            args.append(city)
        if category:
            query+=" AND category=%s"
            args.append(category)
        query+=" ORDER BY name,id"
        merchants=as_dict(c,query,tuple(args))
        entries=[]
        for m in merchants:
            mid=m["id"]
            evidence_count=one(c,"SELECT count(*) AS n FROM ms.evidence WHERE merchant_id=%s",(mid,))["n"]
            latest=one(c,"SELECT result,created_at FROM ms.assessments WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 1",(mid,))
            review=as_dict(c,"SELECT status::text AS status,count(*) AS n FROM ms.recommendations WHERE merchant_id=%s GROUP BY status",(mid,))
            review_counts={r["status"]:r["n"] for r in review}
            score=latest["result"].get("score") if latest and isinstance(latest["result"],dict) else None
            coverage=latest["result"].get("coverage") if latest and isinstance(latest["result"],dict) else None
            entries.append({"id":str(mid),"name":m["name"],"city":m["city"],"category":m["category"],
                            "evidence_count":evidence_count,"score":score,"coverage":coverage,
                            "review_counts":review_counts})
        assessed=[x["score"] for x in entries if type(x["score"]) in (int,float)]
        totals={}
        for x in entries:
            for status,num in x["review_counts"].items():
                totals[status]=totals.get(status,0)+num
        return {"scope":{"org_id":str(ident["org_id"]),"city":city,"category":category},
                "merchant_count":len(entries),"with_evidence":sum(x["evidence_count"]>0 for x in entries),
                "evidence_count":sum(x["evidence_count"] for x in entries),
                "without_usable_score":len(entries)-len(assessed),
                "average_observed_score":round(sum(assessed)/len(assessed),1) if assessed else None,
                "recommendations":totals,"merchants":entries,
                "caveat":"Registered merchants only. Missing analytics are unavailable and should not be treated as zero."}


class LeadStageUpdate(BaseModel):
    stage:Literal["new","qualified","contacted","proposal","won","lost"]

class OutreachDecision(BaseModel):
    approved:bool

@app.get("/api/v2/opportunities")
def secure_opportunities(authorization:str|None=Header(None)):
    ident=current(authorization)
    with tenant_transaction(data_dsn(),ident) as c:
        merchants=as_dict(c,"SELECT id,name,city,category FROM ms.merchants ORDER BY name")
        result=[]
        for m in merchants:
            latest=one(c,"SELECT result FROM ms.assessments WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 1",(m["id"],))
            approved=one(c,"SELECT count(*) AS n FROM ms.recommendations WHERE merchant_id=%s AND status='approved'",(m["id"],))["n"]
            lead=one(c,"SELECT stage::text AS stage,outreach_approved FROM ms.leads WHERE merchant_id=%s",(m["id"],))
            assessment=latest["result"] if latest else None
            score=assessment.get("score") if isinstance(assessment,dict) else None
            confidence=assessment.get("confidence") if isinstance(assessment,dict) else None
            readiness=None
            if type(score) in (int,float) and type(confidence) in (int,float):
                readiness=min(100,round((100-score)*0.5 + confidence*0.2 + min(approved,3)*10))
            result.append({"merchant_id":str(m["id"]),"name":m["name"],"city":m["city"],
                           "category":m["category"],"opportunity_score":readiness,
                           "assessment_score":score,"approved_recommendations":approved,
                           "stage":lead["stage"] if lead else "new",
                           "outreach_approved":lead["outreach_approved"] if lead else False})
        result.sort(key=lambda x:(x["opportunity_score"] is None,-(x["opportunity_score"] or 0)))
        return {"opportunities":result,"caveat":"Internal prioritization, not probability of sales or marketing spend."}

@app.post("/api/v2/merchants/{mid}/lead")
def set_lead_stage(mid:uuid.UUID,data:LeadStageUpdate,authorization:str|None=Header(None)):
    ident=current(authorization)
    try:
        with tenant_transaction(data_dsn(),ident) as c:
            must_merchant(c,str(mid))
            lead=one(c,"SELECT id FROM ms.leads WHERE merchant_id=%s",(mid,))
            if not lead:
                lead=one(c,"INSERT INTO ms.leads(org_id,merchant_id,created_by) VALUES(%s,%s,%s) RETURNING id",
                         (ident["org_id"],mid,ident["user_id"]))
            result=one(c,"UPDATE ms.leads SET stage=%s::ms.lead_stage WHERE id=%s RETURNING stage::text AS stage,outreach_approved",
                       (data.stage,lead["id"]))
            return result
    except Error as exc:
        raise HTTPException(403,"Lead stage change denied by independent approval policies") from exc

@app.post("/api/v2/merchants/{mid}/outreach-approval")
def approve_outreach(mid:uuid.UUID,data:OutreachDecision,authorization:str|None=Header(None)):
    ident=current(authorization)
    try:
        with tenant_transaction(data_dsn(),ident) as c:
            must_merchant(c,str(mid))
            result=one(c,"UPDATE ms.leads SET outreach_approved=%s WHERE merchant_id=%s RETURNING outreach_approved,approved_by,approved_at",
                    (data.approved,mid))
            if not result:raise HTTPException(404,"A separate analyst must first create a lead")
            return result
    except Error as exc:
        raise HTTPException(403,"Independent reviewer authorization required") from exc

@app.get("/api/v2/merchants/{mid}/proposal")
def approved_proposal(mid:uuid.UUID,authorization:str|None=Header(None)):
    ident=current(authorization)
    with tenant_transaction(data_dsn(),ident) as c:
        merchant=must_merchant(c,str(mid))
        rows=as_dict(c,"SELECT id,problem,action,rationale FROM ms.recommendations WHERE merchant_id=%s AND status='approved' ORDER BY created_at DESC",(mid,))
        if not rows:
            return {"status":"not_ready","reason":"Only approved evidence-linked recommendations can form a proposal."}
        services=[]
        for r in rows:
            source=as_dict(c,"""SELECT e.source_url,e.observed_at,e.published_at FROM ms.recommendation_evidence re
              JOIN ms.evidence e ON re.evidence_id=e.id AND re.org_id=e.org_id
              WHERE re.recommendation_id=%s AND e.merchant_id=%s""",(r["id"],mid))
            if not source:continue
            services.append({"problem":r["problem"],"action":r["action"],"rationale":r["rationale"],
                             "sources":[{"url":x["source_url"],"observed_at":x["observed_at"].isoformat(),
                                         "published_at":x["published_at"].isoformat() if x["published_at"] else None} for x in source]})
        if not services:return {"status":"not_ready","reason":"Verified linked evidence absent"}
        return {"status":"draft_for_human_review","merchant":{"id":str(mid),"name":merchant["name"]},
                "services":services,"disclaimer":"No sales or growth projections; no messages have been sent."}


@app.get("/api/v2/compare")
def secure_compare(ids:str,authorization:str|None=Header(None)):
    """Compare a bounded list of merchants visible to current tenant only."""
    ident=current(authorization)
    raw=[s.strip() for s in ids.split(",")]
    if not 2<=len(raw)<=10 or not all(raw):
        raise HTTPException(422,"Choose 2–10 merchant IDs")
    try:
        keys=list(dict.fromkeys(uuid.UUID(x) for x in raw))
    except (TypeError,ValueError) as exc:
        raise HTTPException(422,"Invalid merchant UUID") from exc
    if len(keys)<2:
        raise HTTPException(422,"At least two distinct merchants required")
    with tenant_transaction(data_dsn(),ident) as c:
        results=[]
        for mid in keys:
            m=must_merchant(c,str(mid))
            latest=one(c,"SELECT result FROM ms.assessments WHERE merchant_id=%s ORDER BY created_at DESC LIMIT 1",(mid,))
            count=one(c,"SELECT count(*) AS n FROM ms.evidence WHERE merchant_id=%s",(mid,))["n"]
            assessment=latest["result"] if latest else None
            results.append({"merchant_id":str(mid),"name":m["name"],"city":m["city"],
                            "category":m["category"],"evidence_count":count,
                            "score":assessment.get("score") if isinstance(assessment,dict) else None,
                            "coverage":assessment.get("coverage") if isinstance(assessment,dict) else None})
        return {"results":results,"caveat":"Comparison of recorded evidence, not objective market share or competitor revenue."}

class SecureOSMSearch(BaseModel):
    lat:float=Field(ge=-90,le=90)
    lon:float=Field(ge=-180,le=180)
    radius_m:int=Field(default=1200,ge=100,le=3000)
    category:Literal["shop","restaurant","cafe","pharmacy"]="shop"

class SecureOSMChoice(BaseModel):
    name:str=Field(min_length=2,max_length=200)
    city:str=Field(min_length=1,max_length=100)
    category:str|None=None
    source_url:str

class SecureOSMImport(BaseModel):
    confirm:bool=False
    merchants:list[SecureOSMChoice]=Field(min_length=1,max_length=50)

@app.post("/api/v2/discovery/osm")
def secure_osm_preview(body:SecureOSMSearch,authorization:str|None=Header(None)):
    current(authorization)
    return osm.discover(body.lat,body.lon,body.radius_m,body.category)

@app.post("/api/v2/discovery/osm/commit")
def secure_osm_import(body:SecureOSMImport,authorization:str|None=Header(None)):
    ident=current(authorization)
    if not body.confirm:raise HTTPException(422,"Manual confirmation required")
    from re import fullmatch
    for item in body.merchants:
        if not fullmatch(r"https://www\.openstreetmap\.org/(node|way|relation)/[1-9][0-9]*",item.source_url):
            raise HTTPException(422,"Invalid OSM source URL")
    try:
        with tenant_transaction(data_dsn(),ident) as c:
            imported=[];skipped=[]
            for item in body.merchants:
                duplicate=one(c,"SELECT id FROM ms.merchants WHERE normalized_name=%s AND city=%s",(norm(item.name),item.city))
                previous=one(c,"SELECT merchant_id FROM ms.channels WHERE url=%s",(item.source_url,))
                if duplicate or previous:
                    skipped.append({"name":item.name,"reason":"Duplicate name/city or source URL"})
                    continue
                m=one(c,"""INSERT INTO ms.merchants(org_id,name,normalized_name,city,category,created_by)
                         VALUES(%s,%s,%s,%s,%s,%s) RETURNING id""",
                      (ident["org_id"],item.name,norm(item.name),item.city,item.category,ident["user_id"]))
                c.execute("INSERT INTO ms.channels(org_id,merchant_id,platform,url) VALUES(%s,%s,%s,%s)",
                          (ident["org_id"],m["id"],"openstreetmap",item.source_url))
                imported.append(str(m["id"]))
            return {"imported":len(imported),"merchant_ids":imported,"skipped":skipped,
                    "attribution":osm.ATTRIBUTION,
                    "caveat":"OSM coverage may be incomplete; business identity not independently verified."}
    except Error as exc:
        raise HTTPException(403,"Import denied by tenant policy or duplicate constraints") from exc
