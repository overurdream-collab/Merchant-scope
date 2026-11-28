"""Offline regression guard for the independent PostgreSQL function restore check.

This checks the CI contract, not a live PostgreSQL restore. A green result here
must never be represented as proof that the independent-cluster drill passed.
"""
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/postgres-rls.yml"


def _independent_restore_step(text: str) -> str:
    start = "name: Rehearse restore on independent PostgreSQL cluster with global roles"
    end = "name: Upload secure synthetic UI screenshots"
    assert text.count(start) == 1, "Independent-cluster restore step missing or duplicated"
    assert text.count(end) == 1, "Restore step boundary missing or duplicated"
    return text.split(start, 1)[1].split(end, 1)[0]


def _check_function_catalog_contract(text: str) -> None:
    step = _independent_restore_step(text)
    required = (
        'function_catalog_sql=',
        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace",
        "n.nspname='ms'",
        "p.prokind IN ('f','p')",
        "pg_get_function_identity_arguments(p.oid)",
        "pg_get_functiondef(p.oid)",
        "p.prosecdef",
        "p.proconfig",
        'source_functions="$(docker exec "$source_container"',
        'target_functions="$(docker exec "$target_container"',
        'test -n "$source_functions" && test "$source_functions" = "$target_functions"',
        "SECURITY FAILURE: independent cluster function definitions or security configuration differ",
    )
    for fragment in required:
        assert fragment in step, f"Missing independent restore function contract: {fragment}"
    assert step.index('docker exec -i "$target_container" pg_restore') < step.index("function_catalog_sql=")
    assert step.index("function_catalog_sql=") < step.index('test -n "$source_functions"')


def test_independent_restore_function_catalog_contract():
    _check_function_catalog_contract(WORKFLOW.read_text(encoding="utf-8"))


def test_function_catalog_contract_fails_closed_on_missing_comparison():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    broken = workflow.replace(
        'test -n "$source_functions" && test "$source_functions" = "$target_functions"',
        'test -n "$source_functions"',
        1,
    )
    assert broken != workflow
    import pytest
    with pytest.raises(AssertionError, match="Missing independent restore function contract"):
        _check_function_catalog_contract(broken)
