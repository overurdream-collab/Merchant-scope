"""Offline regression checks for independent PostgreSQL disaster-recovery rehearsal.

These checks validate CI wiring, not actual database recovery. Live acceptance
requires a successful PostgreSQL workflow run on the same commit.
"""
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/postgres-rls.yml"


def _independent_step() -> str:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    marker = "- name: Rehearse restore on independent PostgreSQL cluster with global roles"
    assert workflow.count(marker) == 1, "independent-cluster rehearsal must run exactly once"
    return workflow.split(marker, 1)[1].split("\n      - name:", 1)[0]


def test_independent_restore_uses_fresh_cluster_and_restores_global_roles():
    step = _independent_step()
    assert 'docker run -d --name "$target_container"' in step
    assert "postgres:16" in step
    assert "pg_dumpall -U postgres --globals-only" in step
    assert "pg_dump -U postgres -d merchantscope_test -n ms -Fc" in step
    assert "pg_restore --exit-on-error" in step
    assert "--no-acl" not in step
    assert "--no-owner" not in step
    assert "ON_ERROR_STOP=1" in step
    assert "trap 'docker rm -f" in step


def test_independent_restore_fails_closed_on_security_drift():
    step = _independent_step()
    for role in ("merchant_auth", "merchant_runtime"):
        assert role in step
    for property_name in ("rolcanlogin", "rolsuper", "rolbypassrls"):
        assert property_name in step
    for predicate in (
        "relrowsecurity",
        "NOT has_function_privilege('merchant_runtime'",
        "has_function_privilege('merchant_auth'",
        "ms.login_account(text,uuid)",
        "ms.lookup_session(bytea)",
    ):
        assert predicate in step
    assert 'test "$actual" = t ||' in step
    assert 'test -n "$source_role" && test "$source_role" = "$target_role" ||' in step


def test_independent_restore_checks_full_tenant_data_integrity():
    """Require every tenant table's row contents to match on the fresh cluster."""
    step = _independent_step()
    assert 'test -n "$source_inventory" && test "$source_inventory" = "$target_inventory"' in step
    assert 'for table in "${restored_tables[@]}"; do' in step
    assert "to_jsonb(t)::text" in step
    assert 'test "$source_digest" = "$target_digest"' in step
    assert "SECURITY FAILURE: independent cluster row digest differs" in step
