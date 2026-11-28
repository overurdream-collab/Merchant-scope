"""Conservative gates for numeric and guaranteed AI claims. Synthetic data only."""
from app.agent import validate_draft, requires_fact_check

EVIDENCE=[{"id":1,"text":"عرض اليوم على المنتج فقط","source_url":"https://example.org/1"}]

def rec(action,problem="رسالة المنتج غير واضحة",rationale="عينة منشور واحدة"):
    return {"problem":problem,"action":action,"rationale":rationale,"priority":"high","evidence_ids":[1]}

def test_reject_unsubstantiated_percentages():
    generated={"summary":"تحليل حذر","recommendations":[rec("زيادة المبيعات 65% خلال أسبوع")]}
    assert validate_draft(generated,EVIDENCE)["recommendations"]==[]

def test_reject_guaranteed_outcomes():
    generated={"summary":"تحليل حذر","recommendations":[rec("نضمن مضاعفة الإيرادات خلال شهر")]}
    assert validate_draft(generated,EVIDENCE)["recommendations"]==[]

def test_allow_specific_evidenced_improvement_draft():
    generated={"summary":"المحتوى يحتاج توضيحاً","recommendations":[rec("اختبار كتابة مواصفات المنتج بصورة أكثر وضوحاً")]}
    out=validate_draft(generated,EVIDENCE)
    assert len(out["recommendations"])==1
    assert out["recommendations"][0]["evidence_ids"]==[1]

def test_numeric_summary_is_replaced_if_unsupported():
    generated={"summary":"ستزيد المبيعات 45% تلقائياً","recommendations":[rec("اختبار وصف المنتج")]}
    result=validate_draft(generated,EVIDENCE)
    assert "45%" not in result["summary"]
    assert len(result["recommendations"])==1

def test_supported_source_percentage_is_not_automatically_suppressed():
    sources=[{"id":2,"text":"إعلان التاجر: خصم 20%","source_url":"https://example.org/2"}]
    assert not requires_fact_check("المنشور يذكر خصماً 20%",sources)
    assert requires_fact_check("المنشور يذكر خصماً 30%",sources)
