"""Transparent merchant and portfolio reporting; no inferred market-wide statistics."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone

DIMENSIONS = ("content", "consistency", "engagement", "brand", "presence", "competitors")

def parse_assessment(row):
    if not row:
        return None
    try:
        value = json.loads(row["result"])
    except (ValueError, TypeError, KeyError):
        return None
    return value if isinstance(value, dict) else None

def merchant_snapshot(c, merchant):
    mid = merchant["id"]
    evidence = [dict(x) for x in c.execute(
        "SELECT id, source_url, platform, observed_at, published_at FROM evidence WHERE merchant_id=? ORDER BY observed_at DESC", (mid,)
    )]
    channels = [dict(x) for x in c.execute(
        "SELECT platform, url FROM channels WHERE merchant_id=? ORDER BY platform", (mid,)
    )]
    reviews = [dict(x) for x in c.execute(
        "SELECT id, problem, action, rationale, priority, status, evidence_ids, review_notes, reviewed_at FROM recommendations WHERE merchant_id=? ORDER BY id DESC",(mid,)
    )]
    assessment_row = c.execute(
        "SELECT result, created_at FROM assessments WHERE merchant_id=? ORDER BY id DESC LIMIT 1", (mid,)
    ).fetchone()
    assessment = parse_assessment(assessment_row)
    status_counts = Counter(r["status"] for r in reviews)
    observed = sorted((x["observed_at"] for x in evidence if x.get("observed_at")))
    published = sorted((x["published_at"] for x in evidence if x.get("published_at")))
    lead = c.execute("SELECT stage, outreach_approved FROM leads WHERE merchant_id=?", (mid,)).fetchone()
    return {
        "merchant": {k: merchant.get(k) for k in ("id","name","city","governorate","market","category","website")},
        "coverage": assessment.get("coverage") if assessment else None,
        "confidence": assessment.get("confidence") if assessment else None,
        "score": assessment.get("score") if assessment else None,
        "dimensions": assessment.get("dimensions") if assessment else {x: None for x in DIMENSIONS},
        "assessment_at": assessment_row["created_at"] if assessment_row else None,
        "evidence_count": len(evidence),
        "publication_dates_documented": len({x[:10] for x in published}),
        "observed_first": observed[0] if observed else None,
        "observed_last": observed[-1] if observed else None,
        "source_evidence": evidence,
        "channels": channels,
        "recommendation_counts": dict(status_counts),
        "recommendations": reviews,
        "lead_stage": lead["stage"] if lead else "new",
        "outreach_approved": bool(lead["outreach_approved"]) if lead else False,
        "data_quality_warnings": (
            (["No source evidence exists"] if not evidence else [])
            + (["Posting frequency cannot be verified from observation dates"] if len({x[:10] for x in published}) < 3 else [])
            + (["Insufficient coverage for overall assessment"] if not assessment or assessment.get("score") is None else [])
        ),
        "caveat": "Only recorded evidence is assessed. URLs and metrics supplied by users have not been independently verified."
    }

def portfolio_snapshot(c, city=None, category=None):
    query = "SELECT * FROM merchants WHERE 1=1"
    params = []
    if city:
        query += " AND city=?"; params.append(city)
    if category:
        query += " AND category=?"; params.append(category)
    merchants = [dict(r) for r in c.execute(query+" ORDER BY id", params)]
    items = [merchant_snapshot(c, m) for m in merchants]
    statuses = Counter()
    category_counts = Counter()
    stages = Counter()
    assessed = []
    coverage = []
    incomplete = 0
    for item in items:
        statuses.update(item["recommendation_counts"])
        category_counts[item["merchant"]["category"] or "غير مصنف"] += 1
        stages[item["lead_stage"]] += 1
        if item["score"] is None:
            incomplete += 1
        else:
            assessed.append(item["score"])
        if item["coverage"] is not None:
            coverage.append(item["coverage"])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {"city":city, "category":category, "source":"MerchantScope database only"},
        "merchant_count":len(items),
        "evidence_count":sum(x["evidence_count"] for x in items),
        "merchants_with_evidence":sum(x["evidence_count"]>0 for x in items),
        "merchants_with_assessment":sum(x["assessment_at"] is not None for x in items),
        "merchants_without_usable_score":incomplete,
        "average_score_observed_sample":round(sum(assessed)/len(assessed),1) if assessed else None,
        "average_coverage_assessed_sample":round(sum(coverage)/len(coverage),1) if coverage else None,
        "reviews":dict(statuses),
        "categories":dict(category_counts),
        "lead_stages":dict(stages),
        "outreach_approved":sum(x["outreach_approved"] for x in items),
        "merchants":[{"id":x["merchant"]["id"],"name":x["merchant"]["name"],
                      "city":x["merchant"]["city"],"score":x["score"],
                      "coverage":x["coverage"],"evidence_count":x["evidence_count"],
                      "pending":x["recommendation_counts"].get("pending_review",0),
                      "approved":x["recommendation_counts"].get("approved",0)} for x in items],
        "caveat":"Statistics cover registered merchants and manually or explicitly collected evidence only, not the overall market. No revenue or conversion rates inferred."
    }
