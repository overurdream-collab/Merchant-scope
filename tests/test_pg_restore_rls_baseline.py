"""Read-only RLS baseline gate for source and independently restored PostgreSQL.

This test deliberately does not run migrations or alter the database: restoring
the same insecure schema into a second database must never count as success.
"""
import os

import pytest

CORE_TENANT_TABLES = (
    "organizations", "memberships", "merchants", "channels", "evidence",
    "assessments", "recommendations", "recommendation_evidence",
    "leads", "audit_events",
)
REQUIRED_POLICIES = {
    "organizations": {"org_read"},
    "memberships": {"membership_read", "membership_write"},
    **{
        table: {"tenant_read"}
        for table in CORE_TENANT_TABLES
        if table not in ("organizations", "memberships")
    },
}


def test_core_tenant_rls_and_policy_baseline():
    dsn = os.environ.get("PG_TEST_DSN")
    if not dsn:
        pytest.skip("PostgreSQL test database is not configured")
    psycopg = pytest.importorskip("psycopg")
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
            """SELECT tablename, policyname, cmd, qual, with_check FROM pg_policies
               WHERE schemaname='ms' AND tablename = ANY(%s)""",
            (list(CORE_TENANT_TABLES),),
        ).fetchall()
        by_table = {table: set() for table in CORE_TENANT_TABLES}
        for table, policy, cmd, qual, with_check in policies:
            by_table[table].add(policy)
            if policy in REQUIRED_POLICIES[table]:
                expected_cmd = "ALL" if policy == "membership_write" else "SELECT"
                assert cmd == expected_cmd, f"Unsafe policy command on {table}.{policy}: {cmd}"
                assert qual and "active_org()" in qual, (
                    f"Missing tenant scope in {table}.{policy} USING clause: {qual}"
                )
                expected_predicate = (
                    "has_role(" if policy == "membership_write" else "is_member()"
                )
                assert expected_predicate in qual, (
                    f"Missing membership/role guard in {table}.{policy}: {qual}"
                )
                if policy == "membership_write":
                    assert with_check and "active_org()" in with_check and "has_role(" in with_check, (
                        f"Missing tenant/admin WITH CHECK on {table}.{policy}: {with_check}"
                    )
        for table, required in REQUIRED_POLICIES.items():
            assert required <= by_table[table], (
                f"Missing baseline policies on {table}: {required - by_table[table]}"
            )
