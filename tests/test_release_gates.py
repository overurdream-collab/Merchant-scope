import pytest
from app.release_gates import GATES,evaluate_release

SHA="a"*40

def test_empty_gate_evidence_fails_closed():
    result=evaluate_release({"target_sha":SHA,"gates":{}})
    assert result["release_decision"]=="HOLD"
    assert result["blocked_count"]==len(GATES)
    assert result["never_auto_deploy"] is True

def test_missing_reviewer_cannot_be_passed():
    obj={"target_sha":SHA,"gates":{"ci_current_commit":{"status":"passed","evidence_urls":["https://example.org/test"],"verified_by":""}}}
    assert evaluate_release(obj)["results"]["ci_current_commit"]["status"]=="blocked"

def test_attested_gates_still_require_final_signoff():
    evidence={k:{"status":"passed","evidence_urls":["https://example.org/independent-test"],"verified_by":"independent-human"}
              for k in GATES}
    result=evaluate_release({"target_sha":SHA,"gates":evidence})
    assert result["blocked_count"]==0
    assert result["release_decision"]=="REQUIRES_FINAL_OWNER_SIGNOFF"

def test_no_short_sha_accepted():
    with pytest.raises(ValueError):evaluate_release({"target_sha":"abc","gates":{}})
