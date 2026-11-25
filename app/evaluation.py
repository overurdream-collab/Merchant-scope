"""Offline, reviewer-labelled evaluation of marketing recommendations.

No network calls, no merchant data download, and no fabricated quality claims.
A model draft is scored only against separately recorded human labels.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ALLOWED={"supported","unsupported","partially_supported"}
def load_jsonl(path):
    output=[]
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip(): output.append(json.loads(line))
    return output

def evaluate(cases, minimum_cases=30):
    if not isinstance(cases,list):raise ValueError("Evaluation records must be a list")
    counts=Counter()
    known=set()
    mistakes=[]
    real_verified=0
    for row in cases:
        case_id=row.get("case_id")
        if not isinstance(case_id,str) or not case_id or case_id in known:
            raise ValueError("case_id missing or duplicated")
        known.add(case_id)
        if not row.get("reviewer_id") or not row.get("reviewed_at"):
            raise ValueError(f"{case_id}: separate reviewer identity and timestamp required")
        try:
            reviewed=datetime.fromisoformat(row["reviewed_at"].replace("Z","+00:00"))
        except (TypeError,ValueError) as exc:
            raise ValueError(f"{case_id}: invalid review timestamp") from exc
        if reviewed.tzinfo is None or reviewed.astimezone(timezone.utc)>datetime.now(timezone.utc):
            raise ValueError(f"{case_id}: future/naive review date")
        # Human provenance attestation is mandatory; software cannot prove its truth.
        real_row=(row.get("sample_origin")=="real_consented" and row.get("source_verified") is True
                  and row.get("created_by") and row["created_by"]!=row["reviewer_id"])
        if real_row:real_verified+=1
        else:mistakes.append({"case_id":case_id,"reason":"non_real_or_unverified_or_non_independent_case"})
        evidence=row.get("evidence")
        claims=row.get("claims")
        if not isinstance(evidence,list) or not isinstance(claims,list) or not claims:
            raise ValueError(f"{case_id}: must provide evidence and at least one claim")
        allowed={e["id"] for e in evidence if isinstance(e,dict) and isinstance(e.get("id"),str)}
        if len(allowed)!=len(evidence):
            raise ValueError(f"{case_id}: duplicate/missing evidence IDs")
        for n,claim in enumerate(claims):
            if not isinstance(claim,dict) or claim.get("human_label") not in ALLOWED:
                raise ValueError(f"{case_id}: claim {n} lacks a valid human label")
            ids=claim.get("evidence_ids")
            if not isinstance(ids,list) or any(not isinstance(i,str) for i in ids):
                raise ValueError(f"{case_id}: bad citation IDs")
            grounded=bool(ids) and all(i in allowed for i in ids)
            label=claim["human_label"]
            if not isinstance(claim.get("text"),str) or len(claim["text"].strip())<8:
                raise ValueError(f"{case_id}: empty claim")
            counts["claims"]+=1
            counts[label]+=1
            if grounded:counts["valid_citations"]+=1
            if not grounded:mistakes.append({"case_id":case_id,"claim_index":n,"reason":"missing_or_unknown_citation"})
            if label!="supported":mistakes.append({"case_id":case_id,"claim_index":n,"reason":"reviewer_"+label})
        counts["cases"]+=1
    ready=counts["cases"]>=minimum_cases and real_verified==counts["cases"]
    n=counts["claims"]
    result={
        "cases":counts["cases"],"real_verified_independent_cases":real_verified,"claims":n,
        "human_supported":counts["supported"],"human_partially_supported":counts["partially_supported"],
        "human_unsupported":counts["unsupported"],
        "citation_validity":round(counts["valid_citations"]/n,4) if n else None,
        "human_supported_rate":round(counts["supported"]/n,4) if n else None,
        "unsupported_claim_rate":round(counts["unsupported"]/n,4) if n else None,
        "eligible_for_release_evaluation":ready,
        "acceptance_pass":bool(ready and n and counts["unsupported"]==0
                               and counts["partially_supported"]==0 and counts["valid_citations"]==n
                               and counts["supported"]/n>=0.90),
        "findings":mistakes,
        "limitations":"Labels are human opinions; accuracy cannot be certified without reviewer independence and real source verification."
    }
    if not ready:
        result["blocker"]=f"Require {minimum_cases} real, source-verified, independently reviewed cases; verified: {real_verified}/{counts['cases']}"
    return result

def seal_report(report):
    canonical=json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return {"report":report,"sha256":hashlib.sha256(canonical).hexdigest()}
