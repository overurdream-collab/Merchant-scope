"""Offline regression checks for the dedicated PostgreSQL security workflow.

These checks detect accidental removal of the separate live PostgreSQL gate.
They do not replace execution of that gate against PostgreSQL 16.
"""
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def test_postgres_security_workflow_is_triggered_on_push_and_pull_request():
    workflow = (WORKFLOWS / "postgres-rls.yml").read_text(encoding="utf-8")
    header = workflow.split("jobs:", 1)[0]
    assert "on:\n  push:\n  pull_request:" in header, (
        "PostgreSQL security checks must run for both pushes and pull requests"
    )
    assert "paths:" not in header and "paths-ignore:" not in header, (
        "Path filtering could silently bypass the PostgreSQL release gate"
    )


def test_postgres_security_workflow_requires_live_database_and_restore():
    workflow = (WORKFLOWS / "postgres-rls.yml").read_text(encoding="utf-8")
    assert "postgres-security:" in workflow
    assert "image: postgres:16" in workflow
    assert "PG_TEST_DSN: postgresql://" in workflow
    for command in (
        "tests/test_pg_schema.py",
        "tests/test_pg_security_definer.py",
        "tests/test_pg_schema_ownership.py",
        "tests/test_pg_restore_rls_baseline.py",
        "pg_dump",
        "pg_restore",
        "Rehearse restore on independent PostgreSQL cluster with global roles",
    ):
        assert command in workflow, f"PostgreSQL release gate lost: {command}"


def test_general_ci_has_independent_live_postgres_security_gate():
    """Fail closed if the separate PostgreSQL workflow is not scheduled by GitHub."""
    ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "  postgres-live-security:\n" in ci
    job = ci.split("  postgres-live-security:\n", 1)[1].split("\n  browser-smoke:", 1)[0]
    assert "image: postgres:16" in job
    assert "PG_TEST_DSN: postgresql://" in job
    assert "continue-on-error:" not in job
    assert "if:" not in job
    for required in (
        "tests/test_pg_schema.py",
        "tests/test_pg_security_definer.py",
        "tests/test_pg_schema_ownership.py",
        "tests/test_pg_restore_rls_baseline.py",
    ):
        assert required in job, f"Live PostgreSQL gate missing {required}"
