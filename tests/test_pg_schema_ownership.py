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


def test_application_roles_cannot_bypass_row_level_security():
    """RLS policy checks are meaningless if a runtime role can bypass RLS."""
    psycopg = pytest.importorskip("psycopg")
    dsn = os.environ.get("PG_TEST_DSN")
    if not dsn:
        pytest.skip("Disposable PostgreSQL CI database is required")
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            """SELECT rolname, rolsuper, rolbypassrls
               FROM pg_roles
               WHERE rolname IN ('merchant_runtime', 'merchant_auth')
               ORDER BY rolname"""
        ).fetchall()
    assert {row[0] for row in rows} == {'merchant_runtime', 'merchant_auth'}, (
        f"Required application roles missing: {rows}"
    )
    unsafe = [name for name, superuser, bypassrls in rows if superuser or bypassrls]
    assert not unsafe, f"Application roles can bypass tenant RLS: {unsafe}"


def test_application_roles_have_no_cluster_administration_attributes():
    """A compromised application credential must not manage roles or databases."""
    psycopg = pytest.importorskip("psycopg")
    dsn = os.environ.get("PG_TEST_DSN")
    if not dsn:
        pytest.skip("Disposable PostgreSQL CI database is required")
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            """SELECT rolname, rolcreaterole, rolcreatedb, rolreplication
               FROM pg_roles
               WHERE rolname IN ('merchant_runtime', 'merchant_auth')
               ORDER BY rolname"""
        ).fetchall()
    assert {row[0] for row in rows} == {'merchant_runtime', 'merchant_auth'}, (
        f"Required application roles missing: {rows}"
    )
    unsafe = [name for name, create_role, create_db, replication in rows
              if create_role or create_db or replication]
    assert not unsafe, (
        "Application roles hold cluster administration privileges: " + repr(unsafe)
    )


def test_application_roles_do_not_inherit_pg_privileged_capabilities():
    """Role flags alone miss inherited predefined PostgreSQL privilege roles."""
    psycopg = pytest.importorskip("psycopg")
    dsn = os.environ.get("PG_TEST_DSN")
    if not dsn:
        pytest.skip("Disposable PostgreSQL CI database is required")
    privileged = (
        "pg_read_all_data", "pg_write_all_data", "pg_monitor",
        "pg_read_server_files", "pg_write_server_files",
        "pg_execute_server_program", "pg_signal_backend",
    )
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            """SELECT app.rolname, capability.rolname,
                      pg_has_role(app.oid, capability.oid, 'USAGE')
               FROM pg_roles app CROSS JOIN pg_roles capability
               WHERE app.rolname IN ('merchant_runtime', 'merchant_auth')
                 AND capability.rolname = ANY(%s)
               ORDER BY app.rolname, capability.rolname""",
            (list(privileged),),
        ).fetchall()
    assert {name for name, _, _ in rows} == {'merchant_runtime', 'merchant_auth'}
    assert {cap for _, cap, _ in rows} == set(privileged), (
        "Expected PostgreSQL predefined privilege roles are missing"
    )
    inherited = [(app, cap) for app, cap, allowed in rows if allowed]
    assert not inherited, f"Application roles inherit privileged capabilities: {inherited}"


def test_application_roles_do_not_own_tenant_tables_or_schema():
    """Table owners normally bypass RLS; neither app credential may own tenant data."""
    psycopg = pytest.importorskip("psycopg")
    dsn = os.environ.get("PG_TEST_DSN")
    if not dsn:
        pytest.skip("Disposable PostgreSQL CI database is required")
    with psycopg.connect(dsn) as conn:
        schema = conn.execute(
            """SELECT pg_get_userbyid(nspowner)
               FROM pg_namespace WHERE nspname = 'ms'"""
        ).fetchone()
        assert schema is not None, "Application schema ms is missing"
        rows = conn.execute(
            """SELECT c.relname, c.relkind, pg_get_userbyid(c.relowner)
               FROM pg_class c
               JOIN pg_namespace n ON n.oid = c.relnamespace
               WHERE n.nspname = 'ms' AND c.relkind IN ('r', 'p')
               ORDER BY c.relname"""
        ).fetchall()
    assert rows, "No tenant tables found in application schema"
    untrusted = {'merchant_runtime', 'merchant_auth'}
    assert schema[0] not in untrusted, (
        f"Application schema owned by untrusted role: {schema[0]}"
    )
    unsafe = [(table, kind, owner) for table, kind, owner in rows
              if owner in untrusted]
    assert not unsafe, (
        "Application role owns tenant tables and can bypass RLS: " + repr(unsafe)
    )
