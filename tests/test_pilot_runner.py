from datetime import datetime, timezone
import pytest
from app.pilot_runner import prepare_review_packet

def evidence():
    return [{"id":1,"source_kind":"actual_post","source_url":"https://example.org/business/post/1",
             "observed_at":datetime.now(timezone.utc).isoformat(),"verified_by":"human-reviewer",
             "collection_permission":"public and permitted terms","text":"وصف مختصر للمنتج"}]

def fake(mode,merchant,e):
    return {"summary":"الدليل محدود","recommendations":[{"problem":"المنتج يفتقر لشرح كاف","action":"إضافة وصف أوضح للمنتج والخدمات",
        "rationale":"نص المنشور المقدم","evidence_ids":[1],"priority":"medium"}]}

def test_evidence_driven_review_packet_is_never_approved():
    packet=prepare_review_packet({"name":"مشروع اختباري"},evidence(),runner=fake)
    assert packet["status"]=="pending_independent_human_review"
    assert packet["claims"][0]["human_label"] is None
    assert packet["sample_origin"]=="unverified_until_human_review"
    assert packet["reviewer_id"] is None

def test_directory_record_is_not_evidence():
    e=evidence()
    e[0]["source_kind"]="public_directory_listing"
    with pytest.raises(ValueError,match="Directory"):
        prepare_review_packet({"name":"مشروع اختباري"},e,runner=fake)

def test_no_permission_no_inference():
    e=evidence();e[0]["collection_permission"]=""
    called=[]
    def must_not_run(*args):
        called.append(1)
        return fake(*args)
    with pytest.raises(ValueError,match="permission"):
        prepare_review_packet({"name":"مشروع اختباري"},e,runner=must_not_run)
    assert called==[]

def test_unknown_evidence_citation_does_not_produce_packet():
    with pytest.raises(ValueError,match="No evidence-linked"):
        prepare_review_packet({"name":"مشروع اختباري"},evidence(),
            runner=lambda *a:{"summary":"none","recommendations":[{"problem":"توصية غير مدعومة","action":"عمل توصية تسويقية",
                        "rationale":"مصدر غير موجود","evidence_ids":[9999]}]})
