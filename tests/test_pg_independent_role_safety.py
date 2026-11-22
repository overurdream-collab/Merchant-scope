"""Offline regression for independent PostgreSQL restore service-role safety."""
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "postgres-rls.yml"


def test_independent_restore_rejects_elevated_service_roles():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    block = workflow.split(
        "name: Rehearse restore on independent PostgreSQL cluster with global roles", 1
    )[1].split("name: Upload secure synthetic UI screenshots", 1)[0]
    assert "for role in merchant_auth merchant_runtime; do" in block
    for attribute in (
        "rolsuper", "rolbypassrls", "rolcreatedb", "rolcreaterole",
        "rolreplication",
    ):
        assert attribute in block
    assert 'test "$elevated" = f' in block
    assert 'for cluster in "$source_container" "$target_container"; do' in block
    assert 'test -n "$source_role" && test "$source_role" = "$target_role"' in block
