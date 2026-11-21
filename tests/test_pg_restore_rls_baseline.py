"""Read-only RLS baseline gate for source and independently restored PostgreSQL.

This test deliberately does not run migrations or alter the database: restoring
the same insecure schema into a second database must never count as success.
"""
import os

import pytest

CORE_TENANT_TABLES = (
    "organizations", "memberships", "merchants", "channels", "evidence",
    "assessments", "recommendations", "recommendation_evidence",
    "leads", "audit_events", "research_candidates",
)
# Write policies are part of the expected authorization contract, not optional.
# A missing policy may silently disable legitimate workflows even if reads work.
WRITE_POLICY_TABLES = (
    "merchants", "channels", "evidence", "assessments",
    "recommendations", "recommendation_evidence", "leads",
)
UPDATE_POLICY_TABLES = (
    "merchants", "channels", "evidence", "assessments",
    "recommendations", "recommendation_evidence", "leads",
)

REQUIRED_POLICIES = {
    "organizations": {"org_read"},
    "research_candidates": {"research_read", "research_insert", "research_update"},
    "memberships": {"membership_read", "membership_write"},
    **{
        table: {"tenant_read"}
        for table in CORE_TENANT_TABLES
        if table not in ("organizations", "memberships", "research_candidates")
    },
}


def test_core_tenant_rls_and_policy_baseline():
    dsn = os.environ.get("PG_TEST_DSN")
    if not dsn:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pytest.fail("PG_TEST_DSN is required in GitHub Actions; security gate must not skip")
        pytest.skip("PostgreSQL test database is not configured")
    try:
        import psycopg
    except ImportError:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pytest.fail("psycopg is required in GitHub Actions; security gate must not skip")
        pytest.skip("psycopg is not installed for local PostgreSQL testing")
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            """SELECT c.relname, c.relrowsecurity, c.relkind
               FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='ms' AND c.relname = ANY(%s)""",
            (list(CORE_TENANT_TABLES),),
        ).fetchall()
        actual = {name: (enabled, kind) for name, enabled, kind in rows}
        assert set(actual) == set(CORE_TENANT_TABLES), (
            f"Missing core tenant tables: {set(CORE_TENANT_TABLES) - set(actual)}"
        )
        assert all(enabled and kind in ("r", "p") for enabled, kind in actual.values()), (
            f"Core tables without RLS: {[name for name, (enabled, kind) in actual.items() if not enabled or kind not in ('r', 'p')]}"
        )
        policies = conn.execute(
            """SELECT tablename, policyname, cmd, qual, with_check, permissive, roles FROM pg_policies
               WHERE schemaname='ms' AND tablename = ANY(%s)""",
            (list(CORE_TENANT_TABLES),),
        ).fetchall()
        by_table = {table: set() for table in CORE_TENANT_TABLES}
        for table, policy, cmd, qual, with_check, permissive, roles in policies:
            by_table[table].add(policy)
            # A restrictive-only policy does not grant access on its own, while
            # unexpected role targeting changes the tested authorization model.
            assert permissive == 'PERMISSIVE', (
                f'Unexpected restrictive policy {table}.{policy}: {permissive}'
            )
            assert roles == ['public'], (
                f'Unexpected policy role targets {table}.{policy}: {roles}'
            )
            if policy in REQUIRED_POLICIES[table]:
                expected_cmd = {"membership_write": "ALL", "research_insert": "INSERT", "research_update": "UPDATE"}.get(policy, "SELECT")
                assert cmd == expected_cmd, f"Unsafe policy command on {table}.{policy}: {cmd}"
                assert (policy == "research_insert" or (qual and "active_org()" in qual)), (
                    f"Missing tenant scope in {table}.{policy} USING clause: {qual}"
                )
                expected_predicate = (
                    "has_role(" if policy == "membership_write" else
                    "can_write()" if policy in ("research_insert", "research_update") else "is_member()"
                )
                assert expected_predicate in (with_check if policy == "research_insert" else qual), (
                    f"Missing membership/role guard in {table}.{policy}: {qual}"
                )
                if policy in ("membership_write", "research_insert", "research_update"):
                    assert with_check and "active_org()" in with_check and (("has_role(" if policy == "membership_write" else "can_write()") in with_check), (
                        f"Missing tenant/admin WITH CHECK on {table}.{policy}: {with_check}"
                    )
        for table in WRITE_POLICY_TABLES:
            assert "tenant_insert" in by_table[table], (
                f"Missing tenant INSERT policy on {table}"
            )
        for table in UPDATE_POLICY_TABLES:
            assert "tenant_update" in by_table[table], (
                f"Missing tenant UPDATE policy on {table}"
            )
        for table, required in REQUIRED_POLICIES.items():
            assert required <= by_table[table], (
                f"Missing baseline policies on {table}: {required - by_table[table]}"
            )

        # An extra permissive policy can OR past an otherwise correct tenant
        # policy. Inspect every policy, not only the required policy names.
        for table, policy, cmd, qual, with_check, _permissive, _roles in policies:
            if policy in REQUIRED_POLICIES[table]:
                continue
            if policy not in {"tenant_insert", "tenant_update"}:
                raise AssertionError(f"Unexpected tenant policy {table}.{policy}")
            if table not in WRITE_POLICY_TABLES:
                raise AssertionError(f"Unexpected write policy {table}.{policy}")
            expected_cmd = "INSERT" if policy == "tenant_insert" else "UPDATE"
            assert cmd == expected_cmd, f"Unexpected command {table}.{policy}: {cmd}"
            assert with_check and "active_org()" in with_check and "can_write()" in with_check, (
                f"Unscoped write WITH CHECK on {table}.{policy}: {with_check}"
            )
            if policy == "tenant_update":
                assert qual and "active_org()" in qual and "can_write()" in qual, (
                    f"Unscoped UPDATE USING on {table}.{policy}: {qual}"
                )


def test_restored_rls_baseline_is_run_once_in_ci():
    """Prevent duplicate expensive restored-DB checks while retaining the security gate."""
    from pathlib import Path

    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "postgres-rls.yml").read_text(encoding="utf-8")
    assert workflow.count("run: python -m pytest -q tests/test_pg_restore_rls_baseline.py") == 2, (
        "Expected one source and one restored RLS baseline invocation"
    )
    assert "research_candidates" in CORE_TENANT_TABLES
    assert REQUIRED_POLICIES["research_candidates"] == {"research_read", "research_insert", "research_update"}
    assert workflow.count("name: Verify core tenant RLS and policy baseline on restored database") == 1
    # A second invocation is not a restore gate if it silently reuses the source DSN
    # or runs before pg_restore has completed. Verify both wiring and ordering.
    restore_step = workflow.index("name: Rehearse PostgreSQL backup and restore into separate disposable database")
    restored_gate = workflow.index("name: Verify core tenant RLS and policy baseline on restored database")
    next_step = workflow.index("name: Validate restored SECURITY DEFINER routines with live role checks")
    assert restore_step < restored_gate < next_step
    restored_block = workflow[restored_gate:next_step]
    assert "PG_TEST_DSN: postgresql://postgres:test-password@localhost:5432/merchantscope_restore" in restored_block
    assert restored_block.count("run: python -m pytest -q tests/test_pg_restore_rls_baseline.py") == 1


def test_missing_postgres_dsn_fails_closed_in_github_actions(monkeypatch):
    """A misconfigured CI job must not report a green skipped security gate."""
    monkeypatch.delenv("PG_TEST_DSN", raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(pytest.fail.Exception, match="PG_TEST_DSN is required"):
        test_core_tenant_rls_and_policy_baseline()


def test_missing_psycopg_fails_closed_in_github_actions(monkeypatch):
    """A missing DB driver must fail the live RLS gate, not silently skip it."""
    import sys

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("PG_TEST_DSN", "postgresql://unused/unused")
    monkeypatch.setitem(sys.modules, "psycopg", None)
    with pytest.raises(pytest.fail.Exception, match="psycopg is required"):
        test_core_tenant_rls_and_policy_baseline()
