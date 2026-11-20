"""Catalog-wide SECURITY DEFINER execution guard for disposable PostgreSQL CI.

Run after test_pg_schema.py, which creates roles and applies migration 004.
The runtime may execute exactly two RLS membership predicates; PUBLIC may
execute none. New privileged functions fail closed unless explicitly reviewed.
"""
import os

import pytest


RUNTIME_RLS_PREDICATES = {"ms.has_role(ms.member_role)", "ms.is_member()"}


@pytest.mark.parametrize("role", ["PUBLIC", "merchant_runtime"])
def test_security_definer_execution_is_exactly_allowlisted(role):
    psycopg = pytest.importorskip("psycopg")
    dsn = os.environ.get("PG_TEST_DSN")
    if not dsn:
        pytest.skip("Disposable PostgreSQL CI database is required")
    with psycopg.connect(dsn) as connection:
        rows = connection.execute(
            """
            SELECT p.oid::regprocedure::text,
                   CASE WHEN %s = 'PUBLIC'
                     THEN EXISTS (
                       SELECT 1 FROM aclexplode(
                         coalesce(p.proacl, acldefault('f'::"char", p.proowner))
                       ) AS acl
                       WHERE acl.grantee = 0 AND acl.privilege_type = 'EXECUTE'
                     )
                     ELSE has_function_privilege(
                       'merchant_runtime', p.oid, 'EXECUTE'
                     )
                   END AS exposed
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'ms' AND p.prosecdef
            ORDER BY p.oid::regprocedure::text
            """,
            (role,),
        ).fetchall()
    assert rows, "No SECURITY DEFINER functions found; review schema setup"
    exposed = {name for name, allowed in rows if allowed}
    expected = RUNTIME_RLS_PREDICATES if role == "merchant_runtime" else set()
    assert exposed == expected, (
        f"{role} SECURITY DEFINER execution drift: "
        f"unexpected={sorted(exposed - expected)}, "
        f"missing_required={sorted(expected - exposed)}"
    )


def test_security_definer_search_path_is_pinned():
    """Privileged routines must not resolve attacker-controlled schemas first.

    PostgreSQL SECURITY DEFINER routines execute with owner privileges; an
    implicit or mutable search_path can redirect unqualified object names.
    pg_temp must be explicitly last, after the trusted application schema.
    """
    psycopg = pytest.importorskip("psycopg")
    dsn = os.environ.get("PG_TEST_DSN")
    if not dsn:
        pytest.skip("Disposable PostgreSQL CI database is required")
    with psycopg.connect(dsn) as connection:
        rows = connection.execute(
            """
            SELECT p.oid::regprocedure::text,
                   coalesce(p.proconfig, ARRAY[]::text[])
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'ms' AND p.prosecdef
            ORDER BY p.oid::regprocedure::text
            """
        ).fetchall()
    assert rows, "No SECURITY DEFINER functions found; review schema setup"
    unsafe = {
        signature: settings
        for signature, settings in rows
        if not any(
            setting.startswith("search_path=")
            and [part.strip() for part in setting.split("=", 1)[1].split(",")]
            == ["ms", "pg_temp"]
            for setting in settings
        )
    }
    assert not unsafe, f"Unsafe SECURITY DEFINER search_path: {unsafe}"
