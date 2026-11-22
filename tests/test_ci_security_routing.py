"""Guard CI routing: PostgreSQL-only live checks must never run without a service.

The generic suite still runs all other tests. The dedicated PostgreSQL workflow
must run the baseline on both the source and restored databases.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_generic_ci_excludes_live_postgres_baseline():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "python -m pytest -q --ignore=tests/test_pg_restore_rls_baseline.py" in ci
    # The live gate is excluded from generic CI, but offline routing regressions
    # must remain executable and must never be silently skipped.
    assert "tests/test_pg_restore_rls_baseline.py::test_general_ci_executes_offline_postgres_gate_regressions" in ci
    assert "tests/test_pg_restore_rls_baseline.py::test_missing_postgres_dsn_fails_closed_in_github_actions" in ci
    assert "tests/test_pg_restore_rls_baseline.py::test_missing_psycopg_fails_closed_in_github_actions" in ci
    assert "PG_TEST_DSN:" not in ci


def test_dedicated_postgres_ci_runs_both_baselines():
    pg = (ROOT / ".github/workflows/postgres-rls.yml").read_text(encoding="utf-8")
    invocation = "run: python -m pytest -q tests/test_pg_restore_rls_baseline.py"
    assert pg.count(invocation) == 2
    assert "name: Verify core tenant RLS and policy baseline on source database" in pg
    assert "name: Verify core tenant RLS and policy baseline on restored database" in pg
    assert "PG_TEST_DSN: postgresql://postgres:test-password@localhost:5432/merchantscope_restore" in pg
