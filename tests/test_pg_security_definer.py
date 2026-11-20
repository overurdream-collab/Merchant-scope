"""Fail closed when any SECURITY DEFINER function is executable by PUBLIC or runtime.

Run after test_pg_schema.py, which creates the disposable CI schema and roles.
This is a catalog-wide guard: newly added functions must be covered automatically.
"""
import os
import pytest


@pytest.mark.parametrize("role", ["PUBLIC", "merchant_runtime"])
def test_security_definer_routines_are_not_executable_by_untrusted_roles(role):
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
    exposed = [name for name, allowed in rows if allowed]
    assert not exposed, f"{role} can execute privileged routines: {exposed}"
