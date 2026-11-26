"""Static regression checks; live recovery remains a separate CI gate."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_restore_workflow_uses_external_script():
    workflow = (ROOT / ".github/workflows/postgres-rls.yml").read_text()
    assert 'run: bash scripts/ci_postgres_restore.sh "${{ job.services.postgres.id }}"' in workflow
    for block in re.split(r"^      - ", workflow, flags=re.M):
        if "        run: |\n" in block:
            body = block.split("        run: |\n", 1)[1]
            assert len("\n".join(line[10:] for line in body.splitlines())) <= 21000


def test_restore_script_shell_syntax():
    subprocess.run(["bash", "-n", str(ROOT / "scripts/ci_postgres_restore.sh")], check=True)


def test_independent_restore_identity_exceptions_require_acl_checks():
    workflow = (ROOT / ".github/workflows/postgres-rls.yml").read_text()
    independent = workflow.split("name: Rehearse restore on independent PostgreSQL cluster with global roles", 1)[1]
    assert "AND NOT c.relrowsecurity AND c.relname NOT IN ('user_accounts','sessions')" in independent
    assert "SELECT count(*)=2 AND bool_and(" in independent
    for role in ("\'merchant_runtime\'", "0::oid"):
        assert f"NOT has_any_column_privilege({role}, c.oid" in independent
        assert f"NOT has_table_privilege({role}, c.oid" in independent
    assert "WHEN c.relname='user_accounts' THEN NOT has_any_column_privilege('merchant_auth'" in independent
    for privilege in ("SELECT", "INSERT", "UPDATE"):
        assert f"has_table_privilege('merchant_auth', c.oid, '{privilege}')" in independent
    assert 'test "$identity_safe" = t' in independent
