"""Offline marketing-pilot orchestrator. Requires explicitly supplied post evidence.

No web scraping, outreach, fake merchant data, or automatic approval.
"""
from datetime import datetime, timezone
import hashlib
import json
from . import agent

def prepare_review_packet(merchant,evidence,mode="content",runner=None):
    if not isinstance(merchant,dict) or not merchant.get("name"):
        raise ValueError("Named merchant required")
    if mode not in agent.TASKS:
        raise ValueError("Unsupported mode")
    if not isinstance(evidence,list) or not evidence:
        raise ValueError("Actual documented source evidence required")
    checked=[]
    ids=set()
    for row in evidence:
        if not isinstance(row,dict) or type(row.get("id")) is not int or row["id"] in ids:
            raise ValueError("Evidence ID missing or duplicated")
        if row.get("source_kind") not in ("actual_post","actual_merchant_page","actual_competitor_post"):
            raise ValueError("Directory listings alone are not valid post evidence")
        if not row.get("verified_by") or not row.get("collection_permission"):
            raise ValueError("Source verification and authorized collection attestation required")
        observed=row.get("observed_at")
        if not observed:
            raise ValueError("Observation timestamp required")
        try: stamp=datetime.fromisoformat(observed.replace("Z","+00:00"))
        except (ValueError,AttributeError) as exc:raise ValueError("Invalid observation timestamp") from exc
        if stamp.tzinfo is None or stamp>datetime.now(timezone.utc):
            raise ValueError("Timestamp missing timezone or in future")
        if not row.get("source_url","").startswith("https://"):
            raise ValueError("HTTPS source URL required")
        if not (row.get("text") or "").strip():
            raise ValueError("No observable content to analyze")
        ids.add(row["id"])
        checked.append(row)
    inference=runner or agent.run_model
    raw=inference(mode,merchant,checked)
    draft=agent.validate_draft(raw,checked)
    if not draft["recommendations"]:
        raise ValueError("No evidence-linked recommendations were generated; do not manufacture outputs")
    digest=hashlib.sha256(json.dumps({"merchant":merchant,"evidence":checked,"mode":mode},
                   ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    claims=[]
    for i,item in enumerate(draft["recommendations"],1):
        claims.append({"claim_id":f"{digest[:12]}-{i}","text":item["problem"]+" — "+item["action"],
                       "evidence_ids":[str(i) for i in item["evidence_ids"]],
                       "human_label":None,"reviewer_notes":None})
    return {"case_id":digest,"merchant_name":merchant["name"],"mode":mode,"model_name":"local-ollama-or-injected",
            "sample_origin":"unverified_until_human_review","source_verified":False,
            "created_by":"operator-to-fill","reviewer_id":None,"reviewed_at":None,
            "evidence":[{"id":str(r["id"]),"source_url":r["source_url"],
                         "observed_at":r["observed_at"],"verified_by":r["verified_by"]} for r in checked],
            "claims":claims,"summary":draft["summary"],
            "status":"pending_independent_human_review",
            "notice":"Human reviewer must inspect actual sources, enter real_consented status and labels; no outreach."}
