"""Offline regression for independent-cluster SECURITY DEFINER privileges.

This is a workflow wiring test, not a substitute for live PostgreSQL execution.
"""
from pathlib import Path


def test_independent_restore_enforces_catalog_wide_definer_acl():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "postgres-rls.yml").read_text(encoding="utf-8")
    start = workflow.index("name: Rehearse restore on independent PostgreSQL cluster with global roles")
    end = workflow.index("name: Upload secure synthetic UI screenshots", start)
    independent = workflow[start:end]
    assert "definer_public_sql=" in independent
    assert "definer_runtime_sql=" in independent
    assert "n.nspname='ms' AND p.prosecdef" in independent
    assert "has_function_privilege('PUBLIC', p.oid, 'EXECUTE')" in independent
    assert "has_function_privilege('merchant_runtime', p.oid, 'EXECUTE')" in independent
    assert 'for cluster_db in "$source_container:merchantscope_test" "$target_container:merchantscope_restore"' in independent
    assert 'test -z "$exposed"' in independent
    assert 'test "$allowed" = "ms.has_role(ms.member_role),ms.is_member()"' in independent
    assert "SECURITY FAILURE: independent cluster PUBLIC SECURITY DEFINER exposure" in independent
    assert "SECURITY FAILURE: independent cluster runtime SECURITY DEFINER allowlist drift" in independent
