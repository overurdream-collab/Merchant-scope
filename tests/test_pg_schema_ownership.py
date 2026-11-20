"""Negative privilege regression for the application schema.

Runtime and authentication roles must never be able to redefine trusted SQL
objects used by SECURITY DEFINER functions or row-level security policies.
"""
import os
import pytest


def test_untrusted_roles_cannot_create_in_application_schema():
    psycopg = pytest.importorskip("psycopg")
    dsn = os.environ.get("PG_TEST_DSN")
    if not dsn:
        pytest.skip("Disposable PostgreSQL CI database is required")
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            """
            SELECT role_name,
                   has_schema_privilege(role_name, 'ms', 'CREATE') AS can_create
            FROM (VALUES ('merchant_runtime'), ('merchant_auth')) AS roles(role_name)
            """
        ).fetchall()
    assert len(rows) == 2
    assert not [role for role, allowed in rows if allowed], (
        "Untrusted roles can create or replace trusted application objects: "
        + repr([role for role, allowed in rows if allowed])
    )


def test_privileged_routines_are_not_owned_by_runtime_or_auth_roles():
    psycopg = pytest.importorskip("psycopg")
    dsn = os.environ.get("PG_TEST_DSN")
    if not dsn:
        pytest.skip("Disposable PostgreSQL CI database is required")
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            """
            SELECT p.oid::regprocedure::text, pg_get_userbyid(p.proowner)
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'ms' AND p.prosecdef
            ORDER BY 1
            """
        ).fetchall()
    assert rows, "No SECURITY DEFINER functions found; review schema setup"
    unsafe = [(signature, owner) for signature, owner in rows
              if owner in {'merchant_runtime', 'merchant_auth'}]
    assert not unsafe, f"SECURITY DEFINER owner is an untrusted role: {unsafe}"
