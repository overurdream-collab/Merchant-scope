import pytest
from datetime import datetime, timezone
from app.evaluation import evaluate, seal_report
from app.commercial import build_quote

def case(n,label="supported",ids=None):
    return {"case_id":f"case-{n}","reviewer_id":f"reviewer-{n%3}",
      "reviewed_at":datetime.now(timezone.utc).isoformat(),
      "sample_origin":"synthetic","source_verified":False,"created_by":"analyst-fixture",
      "evidence":[{"id":f"source-{n}","source_url":f"https://example.org/{n}"}],
      "claims":[{"text":"The example copy includes a product description.","evidence_ids":ids if ids is not None else [f"source-{n}"],"human_label":label}]}

def test_small_sample_cannot_be_marked_accepted():
    r=evaluate([case(1)])
    assert r["cases"]==1 and r["eligible_for_release_evaluation"] is False
    assert r["acceptance_pass"] is False

def test_thirty_synthetic_cases_cannot_pass_release_gate():
    r=evaluate([case(n) for n in range(30)])
    assert r["citation_validity"]==1 and r["acceptance_pass"] is False
    assert r["real_verified_independent_cases"]==0
    assert seal_report(r)["sha256"]==seal_report(r)["sha256"]

def test_unknown_citation_and_hallucination_block_acceptance():
    items=[case(n) for n in range(30)]
    items[0]["claims"][0]["evidence_ids"]=["not-present"]
    items[1]["claims"][0]["human_label"]="unsupported"
    r=evaluate(items)
    assert not r["acceptance_pass"] and len([f for f in r["findings"] if "claim_index" in f])==2
    assert r["human_unsupported"]==1
    assert r["citation_validity"]<1

def test_review_identity_and_time_are_required():
    item=case(1);item["reviewer_id"]=""
    with pytest.raises(ValueError):evaluate([item])
    item=case(1);item["reviewed_at"]="2099-01-01T00:00:00+00:00"
    with pytest.raises(ValueError):evaluate([item])

def test_approved_services_only_and_no_auto_outreach():
    service={"title":"إعادة صياغة محتوى المنتجات","quantity":"3","unit_price":"20.00",
             "review_status":"approved","evidence_ids":["source-1"],"deliverables":"3 drafts"}
    quote=build_quote({"name":"تاجر اصطناعي"},[service],currency="USD")
    assert quote["total"]=="60.00"
    assert quote["sent"] is False and quote["approved_for_sending"] is False
    assert quote["status"]=="draft_requires_human_pricing_and_delivery_approval"
    with pytest.raises(ValueError):
        build_quote({"name":"تاجر اصطناعي"},[{**service,"review_status":"pending_review"}])
    with pytest.raises(ValueError):
        build_quote({"name":"تاجر اصطناعي"},[{**service,"evidence_ids":[]}])
    with pytest.raises(ValueError):
        build_quote({"name":"تاجر اصطناعي"},[{**service,"unit_price":"-5"}])
    with pytest.raises(ValueError):
        build_quote({"name":"تاجر اصطناعي"},[service],currency="USD+YER")

def test_attested_real_independent_cases_are_eligible_for_math_gate():
    sample=[{**case(n),"sample_origin":"real_consented","source_verified":True} for n in range(30)]
    r=evaluate(sample)
    assert r["eligible_for_release_evaluation"] and r["acceptance_pass"]
    sample[0]["reviewer_id"]=sample[0]["created_by"]
    assert evaluate(sample)["acceptance_pass"] is False
