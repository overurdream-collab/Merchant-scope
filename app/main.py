"""MerchantScope local pilot: manual merchant/evidence intake, explainable analysis, review and audit."""
import os, json, sqlite3, secrets, csv, io, re, hashlib
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Literal
from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel, Field
from .scoring import assess, recommend
from . import agent, osm, reporting

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get("MERCHANTSCOPE_DB", str(ROOT.parent / "merchant_scope.db")))
TOKEN = os.environ.get("MERCHANTSCOPE_ADMIN_TOKEN", "")
app = FastAPI(title="MerchantScope | مرصد التجار", version="0.1.0")

def now(): return datetime.now(timezone.utc).isoformat()
def normalized(s): return " ".join(s.lower().replace("أ","ا").replace("إ","ا").replace("آ","ا").split())
def require(token, role="analyst"):
    reviewer = os.environ.get("MERCHANTSCOPE_REVIEWER_TOKEN", "")
    if not TOKEN: raise HTTPException(503, "Set MERCHANTSCOPE_ADMIN_TOKEN to enable local pilot")
    if reviewer and secrets.compare_digest(reviewer, TOKEN):
        raise HTTPException(503, "Reviewer and analyst keys must be different")
    allowed = (TOKEN, reviewer) if role == "viewer" else ((reviewer,) if role == "reviewer" and reviewer else (TOKEN,))
    if not token or not any(s and secrets.compare_digest(token, s) for s in allowed):
        raise HTTPException(403 if role == "reviewer" and reviewer else 401, "Access denied")

@app.middleware("http")
async def local_only_guard(request: Request, call_next):
    host = request.client.host if request.client else ""
    if os.environ.get("MERCHANTSCOPE_LOCAL_ONLY", "1") != "0" and host not in ("127.0.0.1","::1","localhost","testclient"):
        return StreamingResponse(iter([b"Remote access disabled for local pilot"]),status_code=403,media_type="text/plain")
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response
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
        CREATE TABLE IF NOT EXISTS evidence(id INTEGER PRIMARY KEY, merchant_id INTEGER NOT NULL REFERENCES merchants(id), platform TEXT NOT NULL, source_url TEXT NOT NULL, observed_at TEXT NOT NULL, text TEXT, likes INTEGER, comments INTEGER, views INTEGER, created_at TEXT NOT NULL, published_at TEXT);
        CREATE TABLE IF NOT EXISTS assessments(id INTEGER PRIMARY KEY, merchant_id INTEGER NOT NULL REFERENCES merchants(id), result TEXT NOT NULL, created_at TEXT NOT NULL, input_digest TEXT);
        CREATE TABLE IF NOT EXISTS recommendations(id INTEGER PRIMARY KEY, merchant_id INTEGER NOT NULL REFERENCES merchants(id), assessment_id INTEGER NOT NULL REFERENCES assessments(id), problem TEXT NOT NULL, action TEXT NOT NULL, rationale TEXT, priority TEXT, evidence_ids TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending_review', review_notes TEXT, reviewed_at TEXT);
        CREATE TABLE IF NOT EXISTS leads(merchant_id INTEGER PRIMARY KEY REFERENCES merchants(id), stage TEXT NOT NULL DEFAULT 'new', outreach_approved INTEGER NOT NULL DEFAULT 0, notes TEXT);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, action TEXT NOT NULL, entity TEXT NOT NULL, entity_id INTEGER NOT NULL, details TEXT NOT NULL, at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS agent_runs(id INTEGER PRIMARY KEY, merchant_id INTEGER NOT NULL REFERENCES merchants(id), mode TEXT NOT NULL, summary TEXT, model TEXT, created_at TEXT NOT NULL);
        """)
        columns = {x["name"] for x in c.execute("PRAGMA table_info(evidence)")}
        if "published_at" not in columns:
            c.execute("ALTER TABLE evidence ADD COLUMN published_at TEXT")
        assessment_columns = {x["name"] for x in c.execute("PRAGMA table_info(assessments)")}
        if "input_digest" not in assessment_columns:
            c.execute("ALTER TABLE assessments ADD COLUMN input_digest TEXT")
        c.execute("CREATE INDEX IF NOT EXISTS idx_assessments_digest ON assessments(merchant_id,input_digest)")

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
    published_at: datetime|None = None
    text: str|None = None
    likes: int|None = Field(default=None,ge=0)
    comments: int|None = Field(default=None,ge=0)
    views: int|None = Field(default=None,ge=0)
class Review(BaseModel):
    decision: Literal["approved","rejected","changes_requested"]
    notes: str = Field(min_length=3)

class RecommendationRevision(BaseModel):
    problem: str = Field(min_length=5,max_length=300)
    action: str = Field(min_length=5,max_length=1000)
    rationale: str | None = Field(default=None,max_length=1000)
    priority: Literal["high","medium","low"]="medium"
    evidence_ids: list[int] = Field(min_length=1,max_length=20)
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
    require(x_admin_token,role="viewer")
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
    require(x_admin_token,role="viewer")
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
    observed = data.observed_at.replace(tzinfo=data.observed_at.tzinfo or timezone.utc)
    if observed > datetime.now(timezone.utc):
        raise HTTPException(422,"Future observation not permitted")
    if data.published_at:
        published = data.published_at.replace(tzinfo=data.published_at.tzinfo or timezone.utc)
        if published > observed:
            raise HTTPException(422,"Publication cannot be after observation")
    with conn() as c:
        merchant(c,mid)
        r=c.execute("INSERT INTO evidence(merchant_id,platform,source_url,observed_at,text,likes,comments,views,created_at,published_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
             (mid,data.platform,data.source_url,data.observed_at.isoformat(),data.text,data.likes,data.comments,data.views,now(),data.published_at.isoformat() if data.published_at else None))
        audit(c,"create","evidence",r.lastrowid,{"source_url":data.source_url})
        return {"id":r.lastrowid}
@app.post("/api/merchants/{mid}/analyze")
def analyze(mid:int,x_admin_token:str|None=Header(None)):
    require(x_admin_token)
    with conn() as c:
        m=merchant(c,mid)
        e=rows(c,"SELECT * FROM evidence WHERE merchant_id=?",(mid,))
        channels=rows(c,"SELECT * FROM channels WHERE merchant_id=?",(mid,))
        # A deterministic fingerprint ensures rerunning an unchanged analysis cannot
        # create duplicate suggestions. Ignore transient metadata and order differences.
        relevant_merchant={key:m.get(key) for key in ("id","name","city","category","website")}
        inputs={"merchant":relevant_merchant,"evidence":sorted(e,key=lambda x:x["id"]),
                "channels":sorted(channels,key=lambda x:x["id"])}
        digest=hashlib.sha256(json.dumps(inputs,sort_keys=True,ensure_ascii=False,default=str).encode("utf-8")).hexdigest()
        existing=c.execute(
            "SELECT id,result FROM assessments WHERE merchant_id=? AND input_digest=? ORDER BY id DESC LIMIT 1",
            (mid,digest)).fetchone()
        if existing:
            return {"assessment":json.loads(existing["result"]),"assessment_id":existing["id"],
                    "recommendations_created":0,"reused":True}
        result=assess(m,e,channels)
        aid=c.execute("INSERT INTO assessments(merchant_id,result,created_at,input_digest) VALUES(?,?,?,?)",
            (mid,json.dumps(result,ensure_ascii=False),now(),digest)).lastrowid
        recs=recommend(result)
        for r in recs:
            rid=c.execute("INSERT INTO recommendations(merchant_id,assessment_id,problem,action,rationale,priority,evidence_ids) VALUES(?,?,?,?,?,?,?)",
                (mid,aid,r["problem"],r["action"],r["rationale"],r["priority"],json.dumps(r["evidence_ids"]))).lastrowid
            audit(c,"recommendation_drafted","recommendation",rid)
        audit(c,"analyze","merchant",mid,{"assessment_id":aid,"drafted":len(recs)})
        return {"assessment":result,"assessment_id":aid,"recommendations_created":len(recs),"reused":False}
@app.get("/api/reviews")
def pending_reviews(x_admin_token:str|None=Header(None)):
    require(x_admin_token,role="viewer")
    with conn() as c: return rows(c,"SELECT * FROM recommendations WHERE status='pending_review' ORDER BY id DESC")
@app.post("/api/recommendations/{rid}/review")
def review(rid:int,data:Review,x_admin_token:str|None=Header(None)):
    require(x_admin_token,role="reviewer")
    with conn() as c:
        r=c.execute("SELECT status,merchant_id,evidence_ids FROM recommendations WHERE id=?",(rid,)).fetchone()
        if not r: raise HTTPException(404,"Recommendation not found")
        if r["status"]!="pending_review": raise HTTPException(409,"Recommendation was already reviewed")
        if data.decision=="approved":
            try: ids=json.loads(r["evidence_ids"])
            except (TypeError,ValueError): ids=[]
            if not ids or any(type(i) is not int for i in ids):
                raise HTTPException(422,"Evidence citations required before approval")
            known={row["id"] for row in rows(c,"SELECT id FROM evidence WHERE merchant_id=?",(r["merchant_id"],))}
            if not set(ids).issubset(known):
                raise HTTPException(422,"Referenced evidence is not part of this merchant")
        c.execute("UPDATE recommendations SET status=?,review_notes=?,reviewed_at=? WHERE id=?",(data.decision,data.notes,now(),rid))
        audit(c,data.decision,"recommendation",rid,{"notes":data.notes})
        return {"status":data.decision}
@app.post("/api/merchants/{mid}/outreach-approval")
def outreach(mid:int,data:Outreach,x_admin_token:str|None=Header(None)):
    require(x_admin_token,role="reviewer")
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
    require(x_admin_token,role="viewer")
    with conn() as c: return rows(c,"SELECT * FROM audit ORDER BY id DESC LIMIT 200")
@app.get("/api/export.csv")
def export_csv(x_admin_token:str|None=Header(None)):
    require(x_admin_token,role="viewer")
    with conn() as c: data=rows(c,"SELECT m.id,m.name,m.city,m.category,m.governorate,m.market,m.website, (SELECT url FROM channels ch WHERE ch.merchant_id=m.id AND ch.platform='openstreetmap' LIMIT 1) AS osm_source FROM merchants m")
    output=io.StringIO()
    fields=["id","name","city","category","governorate","market","website","osm_source","osm_attribution"]
    writer=csv.DictWriter(output,fieldnames=fields);writer.writeheader()
    for row in data:
        out={**row,"osm_attribution":osm.ATTRIBUTION if row.get("osm_source") else ""}
        writer.writerow({k: "'"+v if isinstance(v,str) and v.lstrip().startswith(("=","+","-","@")) else v for k,v in out.items()})
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


# The local pilot only: no unattended outbound marketing or unauthorized scraping.
class MarketFilter(BaseModel):
    city: str | None = None
    category: str | None = None

@app.get("/api/overview")
def overview(x_admin_token: str | None = Header(None)):
    require(x_admin_token,role="viewer")
    with conn() as c:
        def count(table, where="1=1"):
            return c.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]
        return {"merchants": count("merchants"), "evidence":count("evidence"),
                "assessments":count("assessments"), "pending_reviews":count("recommendations","status='pending_review'"),
                "approved_recommendations":count("recommendations","status='approved'"),
                "leads":count("leads"), "approved_outreach":count("leads","outreach_approved=1"),
                "data_policy":"manually entered sources; no automated social platform access"}

@app.get("/api/market")
def market_overview(city: str | None = None, category: str | None = None,
                    x_admin_token: str | None = Header(None)):
    require(x_admin_token,role="viewer")
    with conn() as c:
        query="SELECT m.*, (SELECT COUNT(*) FROM evidence e WHERE e.merchant_id=m.id) evidence_count, (SELECT COUNT(*) FROM channels ch WHERE ch.merchant_id=m.id) channel_count FROM merchants m WHERE 1=1"
        args=[]
        if city: query+=" AND m.city=?"; args.append(city)
        if category: query+=" AND m.category=?"; args.append(category)
        group=rows(c, query+" ORDER BY m.name",args)
        sectors={}
        places={}
        for m in group:
            sectors[m["category"] or "غير مصنف"]=sectors.get(m["category"] or "غير مصنف",0)+1
            places[m["city"] or "غير محدد"]=places.get(m["city"] or "غير محدد",0)+1
        return {"merchants_count":len(group),"categories":sectors,"cities":places,
                "merchants":group,"caveat":"Descriptive statistics for merchants entered in the local database only; NOT a census or market-share estimate."}

@app.get("/api/compare")
def compare(merchant_ids: str, x_admin_token: str | None = Header(None)):
    require(x_admin_token,role="viewer")
    try: ids=list(dict.fromkeys(int(x) for x in merchant_ids.split(",")))
    except ValueError: raise HTTPException(422,"Comma-separated integer merchant IDs required")
    if not 2 <= len(ids) <= 10: raise HTTPException(422,"Select between 2 and 10 merchants")
    with conn() as c:
        result=[]
        for mid in ids:
            m=merchant(c,mid)
            a=c.execute("SELECT result,created_at FROM assessments WHERE merchant_id=? ORDER BY id DESC LIMIT 1",(mid,)).fetchone()
            latest=json.loads(a["result"]) if a else None
            result.append({"id":mid,"name":m["name"],"category":m["category"],"city":m["city"],
                "assessment":latest,"assessment_at":a["created_at"] if a else None,
                "evidence_count":c.execute("SELECT COUNT(*) FROM evidence WHERE merchant_id=?",(mid,)).fetchone()[0]})
        return {"results":result,"caveat":"Comparisons are directional and only cover collected evidence. Missing assessments are unavailable; do not infer rankings."}

@app.get("/api/opportunities")
def opportunities(x_admin_token: str | None = Header(None)):
    require(x_admin_token,role="viewer")
    with conn() as c:
        merchants=rows(c,"SELECT * FROM merchants ORDER BY id DESC")
        out=[]
        for m in merchants:
            a=c.execute("SELECT result,created_at FROM assessments WHERE merchant_id=? ORDER BY id DESC LIMIT 1",(m["id"],)).fetchone()
            assessed=json.loads(a["result"]) if a else None
            approved=c.execute("SELECT COUNT(*) FROM recommendations WHERE merchant_id=? AND status='approved'",(m["id"],)).fetchone()[0]
            lead=c.execute("SELECT stage,outreach_approved,notes FROM leads WHERE merchant_id=?",(m["id"],)).fetchone()
            # A sales readiness rank is not a claim about revenue or business size.
            score=None; reasons=[]
            if assessed and assessed.get("score") is not None:
                score=min(100,round((100-assessed["score"])*0.5 + assessed["confidence"]*0.2 + min(approved,3)*10))
                reasons=[f"Observed marketing gap: {100-assessed['score']}/100",
                         f"Evidence confidence: {assessed['confidence']}%",
                         f"Approved recommendations: {approved}"]
            out.append({"merchant_id":m["id"],"name":m["name"],"city":m["city"],
                        "category":m["category"],"opportunity_score":score,
                        "reasons":reasons,"lead_stage":lead["stage"] if lead else "new",
                        "outreach_approved":bool(lead["outreach_approved"]) if lead else False})
        out.sort(key=lambda x:(x["opportunity_score"] is None,-(x["opportunity_score"] or 0)))
        return {"opportunities":out,"method":"Transparent heuristic for internal prioritization, not a sales probability."}

@app.get("/api/skills")
def skill_catalog(x_admin_token: str | None = Header(None)):
    require(x_admin_token,role="viewer")
    return {"status":"reference_only_not_executable",
            "source":"https://github.com/boringmarketer/boring-marketing-skills",
            "skills":[{"name":name,"purpose":purpose,"installed":False} for name,purpose in [
                ("find-local-clients","Merchant discovery"),
                ("competitive-intel","Competitor research"),
                ("audience-research","Audience research"),
                ("brand-voice","Brand messaging"),
                ("positioning-angles","Positioning"),
                ("pitch-the-fix","Proposals"),
                ("performance-review","Performance assessment")]],
            "rule":"Review, version-pin and audit each skill and its external calls before enabling execution."}

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard():
    return (ROOT / "dashboard.html").read_text(encoding="utf-8")

class ImportConfirmation(BaseModel):
    # Submitted records are displayed in the UI preview first; a human confirms.
    rows: list[Merchant]
    confirm: bool = False

@app.post("/api/import/commit")
def import_merchants(data: ImportConfirmation, x_admin_token: str | None = Header(None)):
    require(x_admin_token)
    if not data.confirm: raise HTTPException(422, "Explicit manual confirmation is required")
    if not 1 <= len(data.rows) <= 1000: raise HTTPException(422, "Provide 1 to 1000 records")
    inserted=[]; duplicates=[]
    with conn() as c:
        for item in data.rows:
            if item.website: check_url(item.website)
            existing=c.execute("SELECT id FROM merchants WHERE normalized=? AND city=?", (normalized(item.name),item.city)).fetchone()
            if existing:
                duplicates.append({"name":item.name,"city":item.city,"id":existing["id"]})
                continue
            rid=c.execute("INSERT INTO merchants(name,normalized,city,governorate,category,market,website,public_contact,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (item.name,normalized(item.name),item.city,item.governorate,item.category,item.market,item.website,item.public_contact,now())).lastrowid
            inserted.append(rid)
            audit(c,"import","merchant",rid,{"source":"user_reviewed_csv"})
        audit(c,"csv_import_completed","batch",0,{"inserted":len(inserted),"duplicates":len(duplicates)})
    return {"inserted":len(inserted),"ids":inserted,"duplicates":duplicates}

@app.get("/api/merchants/{mid}/proposal")
def marketing_proposal(mid:int,x_admin_token:str|None=Header(None)):
    require(x_admin_token,role="viewer")
    with conn() as c:
        m=merchant(c,mid)
        approved=rows(c,"SELECT * FROM recommendations WHERE merchant_id=? AND status='approved' ORDER BY id",(mid,))
        if not approved:
            return {"status":"not_ready","reason":"A reviewer must approve at least one evidence-based recommendation before a proposal can be drafted.","merchant_id":mid}
        items=[]
        for r in approved:
            try: ids=json.loads(r["evidence_ids"])
            except (TypeError,ValueError): ids=[]
            urls=[]
            for eid in ids[:20]:
                ev=c.execute("SELECT source_url,observed_at FROM evidence WHERE id=? AND merchant_id=?",(eid,mid)).fetchone()
                if ev: urls.append({"url":ev["source_url"],"observed_at":ev["observed_at"]})
            items.append({"problem":r["problem"],"action":r["action"],"rationale":r["rationale"],
                          "priority":r["priority"],"source_evidence":urls})
        return {"status":"draft_for_human_review","merchant":{"id":mid,"name":m["name"],"city":m["city"],"category":m["category"]},
                "summary":"اقتراح خدمات تسويقية لمعالجة فجوات موثقة في العينة المرصودة",
                "services":items,"next_step":"Review, edit, approve outreach separately. No messages are sent.",
                "disclaimer":"Do not promise any uplift, lead count or sales figure without an independent measurement baseline."}

class AgentRequest(BaseModel):
    mode: Literal["content","audience","competition","prospecting","proposal"]

@app.post("/api/merchants/{mid}/agent-draft")
def agent_draft(mid:int, data:AgentRequest, x_admin_token:str|None=Header(None)):
    require(x_admin_token)
    with conn() as c:
        m=merchant(c,mid)
        e=rows(c,"SELECT * FROM evidence WHERE merchant_id=? ORDER BY observed_at DESC LIMIT 20",(mid,))
        if not e:
            raise HTTPException(422,"At least one evidence record is required")
        output=agent.run_model(data.mode,m,e)
        reviewed=agent.validate_draft(output,e)
        if not reviewed["recommendations"]:
            raise HTTPException(422,"Model produced no recommendations backed by evidence")
        assessment=c.execute("SELECT id FROM assessments WHERE merchant_id=? ORDER BY id DESC LIMIT 1",(mid,)).fetchone()
        assessment_id=assessment["id"] if assessment else c.execute("INSERT INTO assessments(merchant_id,result,created_at) VALUES(?,?,?)",(mid,json.dumps({"score":None,"note":"agent draft only"}),now())).lastrowid
        run_id=c.execute("INSERT INTO agent_runs(merchant_id,mode,summary,model,created_at) VALUES(?,?,?,?,?)",
            (mid,data.mode,reviewed["summary"],os.environ.get("MERCHANTSCOPE_OLLAMA_MODEL",""),now())).lastrowid
        rec_ids=[]
        for r in reviewed["recommendations"]:
            rid=c.execute("INSERT INTO recommendations(merchant_id,assessment_id,problem,action,rationale,priority,evidence_ids) VALUES(?,?,?,?,?,?,?)",
                (mid,assessment_id,r["problem"],r["action"],r["rationale"],r["priority"],json.dumps(r["evidence_ids"]))).lastrowid
            rec_ids.append(rid)
            audit(c,"agent_recommendation_pending","recommendation",rid,{"agent_run_id":run_id,"mode":data.mode})
        audit(c,"agent_run","merchant",mid,{"agent_run_id":run_id,"mode":data.mode,"recommendations":len(rec_ids)})
        return {"status":"pending_review","run_id":run_id,"summary":reviewed["summary"],"recommendation_ids":rec_ids,
                "note":"This output is unverified AI-generated analysis. Review evidence and claims manually."}

@app.get("/api/merchants/{mid}/agent-history")
def agent_history(mid:int,x_admin_token:str|None=Header(None)):
    require(x_admin_token,role="viewer")
    with conn() as c:
        merchant(c,mid)
        return rows(c,"SELECT * FROM agent_runs WHERE merchant_id=? ORDER BY id DESC LIMIT 50",(mid,))

class OSMSearch(BaseModel):
    lat: float = Field(ge=-90,le=90)
    lon: float = Field(ge=-180,le=180)
    radius_m: int = Field(default=1200,ge=100,le=3000)
    category: Literal["shop","restaurant","cafe","pharmacy"]="shop"

class OSMChoice(BaseModel):
    name: str = Field(min_length=2,max_length=200)
    city: str = Field(min_length=1,max_length=100)
    category: str|None = None
    source_url: str

class OSMConfirmation(BaseModel):
    confirm: bool=False
    merchants: list[OSMChoice] = Field(min_length=1,max_length=50)

@app.post("/api/discovery/osm")
def osm_discovery(data:OSMSearch,x_admin_token:str|None=Header(None)):
    require(x_admin_token)
    return osm.discover(data.lat,data.lon,data.radius_m,data.category)

@app.post("/api/discovery/osm/commit")
def osm_confirm(data:OSMConfirmation,x_admin_token:str|None=Header(None)):
    require(x_admin_token)
    if not data.confirm: raise HTTPException(422,"Human import confirmation required")
    imported=[];skipped=[]
    with conn() as c:
        for entry in data.merchants:
            if not re.fullmatch(r"https://www\.openstreetmap\.org/(node|way|relation)/[1-9][0-9]*",entry.source_url):
                raise HTTPException(422,"Invalid OSM source URL")
            seen=c.execute("SELECT id FROM merchants WHERE normalized=? AND city=?",(normalized(entry.name),entry.city)).fetchone()
            same_url=c.execute("SELECT merchant_id FROM channels WHERE url=?",(entry.source_url,)).fetchone()
            if seen or same_url:
                skipped.append({"name":entry.name,"reason":"Existing merchant name or OSM identifier"})
                continue
            mid=c.execute("INSERT INTO merchants(name,normalized,city,category,created_at) VALUES(?,?,?,?,?)",
                (entry.name,normalized(entry.name),entry.city,entry.category,now())).lastrowid
            c.execute("INSERT INTO channels(merchant_id,platform,url) VALUES(?,?,?)",(mid,"openstreetmap",entry.source_url))
            audit(c,"osm_import","merchant",mid,{"source_url":entry.source_url,"attribution":osm.ATTRIBUTION})
            imported.append(mid)
    return {"imported":len(imported),"ids":imported,"skipped":skipped,"attribution":osm.ATTRIBUTION,
            "caveat":"Source URL supplied by reviewer; verify its correspondence with the OSM record."}

@app.get("/api/reports/portfolio")
def portfolio_report(city:str|None=None,category:str|None=None,x_admin_token:str|None=Header(None)):
    require(x_admin_token,role="viewer")
    with conn() as c:
        return reporting.portfolio_snapshot(c,city=city,category=category)

@app.get("/api/merchants/{mid}/report")
def merchant_report(mid:int,x_admin_token:str|None=Header(None)):
    require(x_admin_token,role="viewer")
    with conn() as c:
        return reporting.merchant_snapshot(c,merchant(c,mid))

@app.get("/api/recommendations/changes")
def revision_requests(x_admin_token: str|None=Header(None)):
    require(x_admin_token,role="viewer")
    with conn() as c:
        return rows(c, "SELECT * FROM recommendations WHERE status='changes_requested' ORDER BY id DESC")

@app.post("/api/recommendations/{rid}/resubmit")
def resubmit_recommendation(rid:int,data:RecommendationRevision,x_admin_token: str|None=Header(None)):
    require(x_admin_token)
    with conn() as c:
        previous=c.execute("SELECT * FROM recommendations WHERE id=?",(rid,)).fetchone()
        if not previous: raise HTTPException(404,"Recommendation not found")
        if previous["status"] != "changes_requested":
            raise HTTPException(409,"Only changes_requested recommendations may be resubmitted")
        valid={x["id"] for x in rows(c,"SELECT id FROM evidence WHERE merchant_id=?",(previous["merchant_id"],))}
        if not set(data.evidence_ids).issubset(valid):
            raise HTTPException(422,"All evidence IDs must belong to the merchant")
        # Preserve the full previous recommendation and reviewer decision in immutable audit data.
        before={k:previous[k] for k in ("problem","action","rationale","priority","evidence_ids","status","review_notes","reviewed_at")}
        c.execute("""UPDATE recommendations SET problem=?,action=?,rationale=?,priority=?,evidence_ids=?,
                     status='pending_review',review_notes=NULL,reviewed_at=NULL WHERE id=?""",
                  (data.problem,data.action,data.rationale,data.priority,json.dumps(sorted(set(data.evidence_ids))),rid))
        audit(c,"resubmission","recommendation",rid,{"before":before,
              "after":{"problem":data.problem,"action":data.action,"rationale":data.rationale,
                       "priority":data.priority,"evidence_ids":sorted(set(data.evidence_ids))}})
        return {"id":rid,"status":"pending_review","audit_recorded":True}
