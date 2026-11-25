"""Commercial quote *drafts* from independently approved, evidence-linked services.
Prices are user-provided scope assumptions, never model-inferred market prices.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import date
import re

def _money(value):
    if isinstance(value,bool):raise ValueError("Boolean is not a price")
    try: d=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError) as exc:raise ValueError("Invalid price") from exc
    if not d.is_finite() or d<0 or d.as_tuple().exponent < -2:raise ValueError("Price must be nonnegative with <=2 decimals")
    return d

def build_quote(merchant,services,currency="USD",valid_until=None,terms=None):
    if currency not in {"USD","YER","SAR"}:raise ValueError("Unsupported or mixed currency")
    if not merchant.get("name"):raise ValueError("Merchant name required")
    if not isinstance(services,list) or not services:raise ValueError("Approved services required")
    if valid_until and date.fromisoformat(valid_until)<date.today():raise ValueError("Expired validity date")
    if terms and (not isinstance(terms,str) or len(terms)>1000):raise ValueError("Invalid terms")
    result=[];total=Decimal("0")
    for item in services:
        if item.get("review_status")!="approved":
            raise ValueError("Every quoted service must be approved")
        ids=item.get("evidence_ids")
        if not isinstance(ids,list) or not ids or len(set(ids))!=len(ids):
            raise ValueError("Each service must cite distinct evidence IDs")
        title=item.get("title","")
        if not isinstance(title,str) or not 5<=len(title.strip())<=180:
            raise ValueError("Service title required")
        qty=_money(item.get("quantity"))
        unit=_money(item.get("unit_price"))
        if qty<=0 or qty>10000 or unit>Decimal("1000000000"):
            raise ValueError("Out of bounds quantity or unit price")
        subtotal=(qty*unit).quantize(Decimal(".01"),rounding=ROUND_HALF_UP)
        total+=subtotal
        result.append({"title":title.strip(),"quantity":str(qty),"unit_price":f"{unit:.2f}",
                       "subtotal":f"{subtotal:.2f}","evidence_ids":ids,
                       "deliverables":str(item.get("deliverables") or "")[:600]})
    if total>Decimal("1000000000000"):raise ValueError("Quote exceeds limit")
    return {"status":"draft_requires_human_pricing_and_delivery_approval",
            "merchant":merchant["name"],"currency":currency,
            "line_items":result,"total":f"{total:.2f}","valid_until":valid_until,
            "terms":terms or "النطاق والمدة والضريبة وشروط الدفع تحتاج موافقة بشرية مستقلة.",
            "assumptions":"Prices supplied by the operator; no market price, tax rate, exchange rate, ROI or sales outcome is inferred.",
            "sent":False,"approved_for_sending":False}
