"""MerchantScope local pilot: manual merchant/evidence intake, explainable analysis, review and audit."""
import os, json, sqlite3, secrets, csv, io, re
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Literal
from fastapi import FastAPI, HTTPException, Header, UploadFile, File
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel, Field
from .scoring import assess, recommend

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get("MERCHANTSCOPE_DB", str(ROOT.parent / "merchant_scope.db")))
TOKEN = os.environ.get("MERCHANTSCOPE_ADMIN_TOKEN", "")
app = FastAPI(title="MerchantScope | مرصد التجار", version="0.1.0")

def now(): return datetime.now(timezone.utc).isoformat()
def normalized(s): return " ".join(s.lower().replace("أ","ا").replace("إ","ا").replace("آ","ا").split())
def require(token):
    if not TOKEN: raise HTTPException(503, "Set MERCHANTSCOPE_ADMIN_TOKEN to enable local pilot")
    if not token or not secrets.compare_digest(token, TOKEN): raise HTTPException(401, "Invalid local admin token")
def check_url(value):
    p = urlparse(value)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise HTTPException(422, "A valid http(s) source URL is required")
    return value
@contextmanager
def conn():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
        c.commit()
    finally: c.close()
def rows(c, sql, args=()): return [dict(r) for r in c.execute(sql, args)]
def merchant(c, mid):
    result = c.execute("SELECT * FROM merchants WHERE id=?", (mid,)).fetchone()
    if not result: raise HTTPException(404, "Merchant not found")
    return dict(result)
def audit(c, action, entity, entity_id, details=None):
    c.execute("INSERT INTO audit(action,entity,entity_id,details,at) VALUES(?,?,?,?,?)", (action,entity,entity_id,json.dumps(details or {},ensure_ascii=False),now()))
def init_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS merchants(id INTEGER PRIMARY KEY, name TEXT NOT NULL, normalized TEXT NOT NULL, category TEXT, city TEXT, governorate TEXT, market TEXT, website TEXT, public_contact TEXT, created_at TEXT NOT NULL, UNIQUE(normalized,city));
        CREATE TABLE IF NOT EXISTS channels(id INTEGER PRIMARY KEY, merchant_id INTEGER NOT NULL REFERENCES merchants(id), platform TEXT NOT NULL, url TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS evidence(id INTEGER PRIMARY KEY, merchant_id INTEGER NOT NULL REFERENCES merchants(id), platform TEXT NOT NULL, source_url TEXT NOT NULL, observed_at TEXT NOT NULL, text TEXT, likes INTEGER, comments INTEGER, views INTEGER, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS assessments(id INTEGER PRIMARY KEY, merchant_id INTEGER NOT NULL REFERENCES merchants(id), result TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS recommendations(id INTEGER PRIMARY KEY, merchant_id INTEGER NOT NULL REFERENCES merchants(id), assessment_id INTEGER NOT NULL REFERENCES assessments(id), problem TEXT NOT NULL, action TEXT NOT NULL, rationale TEXT, priority TEXT, evidence_ids TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending_review', review_notes TEXT, reviewed_at TEXT);
        CREATE TABLE IF NOT EXISTS leads(merchant_id INTEGER PRIMARY KEY REFERENCES merchants(id), stage TEXT NOT NULL DEFAULT 'new', outreach_approved INTEGER NOT NULL DEFAULT 0, notes TEXT);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, action TEXT NOT NULL, entity TEXT NOT NULL, entity_id INTEGER NOT NULL, details TEXT NOT NULL, at TEXT NOT NULL);
        """)

@app.on_event("startup")
def startup(): init_db()

class Merchant(BaseModel):
    name: str = Field(min_length=2,max_length=200)
    city: str = Field(min_length=1)
    governorate: str|None = None
    category: str|None = None
    market: str|None = None
    website: str|None = None
    public_contact: str|None = None
class Channel(BaseModel):
    platform: str = Field(min_length=2)
    url: str
class Evidence(BaseModel):
    platform: str = Field(min_length=2)
    source_url: str
    observed_at: datetime
    text: str|None = None
    likes: int|None = Field(default=None,ge=0)
    comments: int|None = Field(default=None,ge=0)
    views: int|None = Field(default=None,ge=0)
class Review(BaseModel):
    decision: Literal["approved","rejected","changes_requested"]
    notes: str = Field(min_length=3)
class Lead(BaseModel):
    stage: Literal["new","qualified","contacted","proposal","won","lost"]
    notes: str|None = None
class Outreach(BaseModel):
    approved: bool
    notes: str = Field(min_length=3)

@app.get("/api/health")
def health(): return {"status":"ok","mode":"local_pilot","configured":bool(TOKEN)}
@app.get("/api/merchants")
def list_merchants(q:str="",x_admin_token:str|None=Header(None)):
    require(x_admin_token)
    with conn() as c: return rows(c,"SELECT * FROM merchants WHERE name LIKE ? ORDER BY id DESC", (f"%{q}%",))
@app.post("/api/merchants",status_code=201)
def add_merchant(data: Merchant,x_admin_token:str|None=Header(None)):
    require(x_admin_token)
    if data.website: check_url(data.website)
    with conn() as c:
        try:
            r=c.execute("INSERT INTO merchants(name,normalized,city,governorate,category,market,website,public_contact,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
              (data.name,normalized(data.name),data.city,data.governorate,data.category,data.market,data.website,data.public_contact,now()))
        except sqlite3.IntegrityError: raise HTTPException(409,"Duplicate name in city")
        audit(c,"create","merchant",r.lastrowid)
        return {"id":r.lastrowid}
@app.get("/api/merchants/{mid}")
def details(mid:int,x_admin_token:str|None=Header(None)):
    require(x_admin_token)
    with conn() as c:
        item=merchant(c,mid)
        for table in ("channels","evidence","assessments","recommendations"):
            item[table]=rows(c,f"SELECT * FROM {table} WHERE merchant_id=? ORDER BY id DESC",(mid,))
        return item
@app.post("/api/merchants/{mid}/channels",status_code=201)
def add_channel(mid:int,data: Channel,x_admin_token:str|None=Header(None)):
    require(x_admin_token);check_url(data.url)
    with conn() as c:
        merchant(c,mid)
        try: r=c.execute("INSERT INTO channels(merchant_id,platform,url) VALUES(?,?,?)",(mid,data.platform,data.url))
        except sqlite3.IntegrityError: raise HTTPException(409,"Channel URL is already recorded")
        audit(c,"create","channel",r.lastrowid)
        return {"id":r.lastrowid}
@app.post("/api/merchants/{mid}/evidence",status_code=201)
def add_evidence(mid:int,data:Evidence,x_admin_token:str|None=Header(None)):
    require(x_admin_token);check_url(data.source_url)
    if data.observed_at.replace(tzinfo=data.observed_at.tzinfo or timezone.utc)>datetime.now(timezone.utc):
        raise HTTPException(422,"Future observation not permitted")
    with conn() as c:
        merchant(c,mid)
        r=c.execute("INSERT INTO evidence(merchant_id,platform,source_url,observed_at,text,likes,comments,views,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
             (mid,data.platform,data.source_url,data.observed_at.isoformat(),data.text,data.likes,data.comments,data.views,now()))
        audit(c,"create","evidence",r.lastrowid,{"source_url":data.source_url})
        return {"id":r.lastrowid}
@app.post("/api/merchants/{mid}/analyze")
def analyze(mid:int,x_admin_token:str|None=Header(None)):
    require(x_admin_token)
    with conn() as c:
        m=merchant(c,mid)
        e=rows(c,"SELECT * FROM evidence WHERE merchant_id=?",(mid,))
        channels=rows(c,"SELECT * FROM channels WHERE merchant_id=?",(mid,))
        result=assess(m,e,channels)
        aid=c.execute("INSERT INTO assessments(merchant_id,result,created_at) VALUES(?,?,?)",(mid,json.dumps(result,ensure_ascii=False),now())).lastrowid
        recs=recommend(result)
        for r in recs:
            rid=c.execute("INSERT INTO recommendations(merchant_id,assessment_id,problem,action,rationale,priority,evidence_ids) VALUES(?,?,?,?,?,?,?)",
                (mid,aid,r["problem"],r["action"],r["rationale"],r["priority"],json.dumps(r["evidence_ids"]))).lastrowid
            audit(c,"recommendation_drafted","recommendation",rid)
        audit(c,"analyze","merchant",mid,{"assessment_id":aid,"drafted":len(recs)})
        return {"assessment":result,"recommendations_created":len(recs)}
@app.get("/api/reviews")
def pending_reviews(x_admin_token:str|None=Header(None)):
    require(x_admin_token)
    with conn() as c: return rows(c,"SELECT * FROM recommendations WHERE status='pending_review' ORDER BY id DESC")
@app.post("/api/recommendations/{rid}/review")
def review(rid:int,data:Review,x_admin_token:str|None=Header(None)):
    require(x_admin_token)
    with conn() as c:
        r=c.execute("SELECT status FROM recommendations WHERE id=?",(rid,)).fetchone()
        if not r: raise HTTPException(404,"Recommendation not found")
        if r["status"]!="pending_review": raise HTTPException(409,"Recommendation was already reviewed")
        c.execute("UPDATE recommendations SET status=?,review_notes=?,reviewed_at=? WHERE id=?",(data.decision,data.notes,now(),rid))
        audit(c,data.decision,"recommendation",rid,{"notes":data.notes})
        return {"status":data.decision}
@app.post("/api/merchants/{mid}/outreach-approval")
def outreach(mid:int,data:Outreach,x_admin_token:str|None=Header(None)):
    require(x_admin_token)
    with conn() as c:
        merchant(c,mid)
        c.execute("INSERT INTO leads(merchant_id,outreach_approved,notes) VALUES(?,?,?) ON CONFLICT(merchant_id) DO UPDATE SET outreach_approved=excluded.outreach_approved,notes=excluded.notes",(mid,int(data.approved),data.notes))
        audit(c,"outreach_approved" if data.approved else "outreach_revoked","merchant",mid)
        return {"approved":data.approved}
@app.post("/api/merchants/{mid}/lead")
def update_lead(mid:int,data:Lead,x_admin_token:str|None=Header(None)):
    require(x_admin_token)
    with conn() as c:
        merchant(c,mid)
        old=c.execute("SELECT outreach_approved FROM leads WHERE merchant_id=?",(mid,)).fetchone()
        if data.stage in ("contacted","proposal","won") and (not old or not old["outreach_approved"]):
            raise HTTPException(409,"Outreach requires explicit human approval")
        c.execute("INSERT INTO leads(merchant_id,stage,notes) VALUES(?,?,?) ON CONFLICT(merchant_id) DO UPDATE SET stage=excluded.stage,notes=excluded.notes",(mid,data.stage,data.notes))
        audit(c,"stage_change","merchant",mid,{"stage":data.stage})
        return {"stage":data.stage}
@app.get("/api/audit")
def audit_log(x_admin_token:str|None=Header(None)):
    require(x_admin_token)
    with conn() as c: return rows(c,"SELECT * FROM audit ORDER BY id DESC LIMIT 200")
@app.get("/api/export.csv")
def export_csv(x_admin_token:str|None=Header(None)):
    require(x_admin_token)
    with conn() as c: data=rows(c,"SELECT id,name,city,category,governorate,market,website FROM merchants")
    output=io.StringIO()
    fields=["id","name","city","category","governorate","market","website"]
    writer=csv.DictWriter(output,fieldnames=fields);writer.writeheader()
    for row in data:
        writer.writerow({k: "'"+v if isinstance(v,str) and v.lstrip().startswith(("=","+","-","@")) else v for k,v in row.items()})
    return StreamingResponse(iter([output.getvalue().encode("utf-8-sig")]),media_type="text/csv")
@app.post("/api/import/preview")
async def preview(file:UploadFile=File(...),x_admin_token:str|None=Header(None)):
    require(x_admin_token)
    raw=await file.read(2_000_001)
    if len(raw)>2_000_000: raise HTTPException(413,"CSV too large")
    try: records=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))[:1000]
    except UnicodeDecodeError: raise HTTPException(422,"Use UTF-8 CSV")
    seen=set();result=[]
    with conn() as c:
        for i,r in enumerate(records):
            name=(r.get("name") or "").strip();city=(r.get("city") or "").strip()
            key=(normalized(name),city)
            exists=c.execute("SELECT 1 FROM merchants WHERE normalized=? AND city=?",key).fetchone()
            status="invalid" if not name else "duplicate_in_file" if key in seen else "duplicate_existing" if exists else "new"
            result.append({"row":i+2,"name":name,"city":city,"status":status})
            seen.add(key)
    return {"preview":result,"committed":False}
