"""Evidence-gated, transparent heuristics; missing data is never scored as zero."""
from datetime import datetime, timezone
from statistics import mean, pstdev

WEIGHTS = {"content": 25, "consistency": 15, "engagement": 20, "brand": 15, "presence": 15, "competitors": 10}

def assess(merchant, evidence, channels):
    dimensions = {k: None for k in WEIGHTS}
    reasons = {}
    posts = [e for e in evidence if e.get("text")]
    if len(posts) >= 3:
        calls = sum(any(w in p["text"].lower() for w in ("اطلب", "تواصل", "احجز", "اتصل", "order", "call")) for p in posts)
        detailed = sum(len(p["text"]) >= 45 for p in posts)
        dimensions["content"] = round(50 * (calls + detailed) / len(posts))
        reasons["content"] = "Text-only CTA and length heuristic; not a visual quality rating"
    dates = sorted({p["observed_at"][:10] for p in evidence})
    if len(dates) >= 3:
        days = [datetime.fromisoformat(d).date().toordinal() for d in dates]
        gaps = [b-a for a, b in zip(days, days[1:])]
        avg = mean(gaps)
        dimensions["consistency"] = round(100 * max(0, 1 - min(1, pstdev(gaps) / avg))) if avg else None
        reasons["consistency"] = "Based only on observed evidence dates, not all posts"
    views = [p for p in evidence if p.get("views") and p.get("likes") is not None and p.get("comments") is not None]
    if len(views) >= 3:
        rate = mean((p["likes"] + p["comments"]) / p["views"] for p in views)
        dimensions["engagement"] = min(100, round(rate * 1000))
        reasons["engagement"] = "Indicative scaled engagements/views, not conversion rate"
    presence = len({c["platform"] for c in channels}) + bool(merchant.get("website"))
    if presence:
        dimensions["presence"] = min(100, presence * 25)
        reasons["presence"] = "Number of recorded channels, not verified quality"
    if len(posts) >= 3 and presence:
        word = merchant["name"].split()[0].lower()
        dimensions["brand"] = round(100 * sum(word in p["text"].lower() for p in posts) / len(posts))
        reasons["brand"] = "Brand name frequency; does not assess visual identity"
    # Competition unavailable until comparable verified competitor metrics exist.
    observed_weight = sum(w for k, w in WEIGHTS.items() if dimensions[k] is not None)
    coverage = observed_weight
    score = round(sum(dimensions[k] * w for k, w in WEIGHTS.items() if dimensions[k] is not None) / observed_weight) if coverage >= 50 else None
    confidence = min(100, round(coverage * .7 + min(len(evidence), 15) * 1.5))
    return dict(dimensions=dimensions, reasons=reasons, coverage=coverage, score=score, confidence=confidence, evidence_ids=[e["id"] for e in evidence], analyzed_at=datetime.now(timezone.utc).isoformat())

TEMPLATES = {
    "content": ("ضعف وضوح الرسائل في العينة", "اختبار نصوص منتجات واضحة مع دعوة للإجراء"),
    "consistency": ("تفاوت مواعيد المحتوى المرصود", "تجربة جدول نشر أربعة أسابيع وقياس الانتظام"),
    "engagement": ("ضعف التفاعل المرصود", "اختبار أنواع محتوى مختلفة ومقارنة نسب التفاعل"),
    "presence": ("محدودية القنوات المعروفة", "التحقق من القنوات الرسمية وتحديد جدوى تطويرها"),
    "brand": ("ضعف حضور اسم العلامة", "مراجعة اتساق الرسائل والاسم التجاري"),
}

def recommend(assessment):
    return [{"dimension": k, "problem": TEMPLATES[k][0], "action": TEMPLATES[k][1],
             "evidence_ids": assessment["evidence_ids"], "rationale": assessment["reasons"].get(k, ""),
             "priority": "high" if value < 30 else "medium"}
            for k, value in assessment["dimensions"].items()
            if value is not None and value < 55 and k in TEMPLATES]
