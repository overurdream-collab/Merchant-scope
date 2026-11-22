"""Contract test: independent PostgreSQL recovery preserves function security metadata.

This static check guards CI wiring, not live recovery success.
"""
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/postgres-rls.yml"


def test_independent_restore_compares_function_definitions_and_search_paths():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    section = workflow.split(
        "- name: Rehearse restore on independent PostgreSQL cluster with global roles", 1
    )[1].split("- name: Upload secure synthetic UI screenshots", 1)[0]
    for required in (
        "pg_get_function_identity_arguments(p.oid)",
        "pg_get_functiondef(p.oid)",
        "p.prosecdef",
        "p.proconfig",
        'source_functions="$(docker exec "$source_container"',
        'target_functions="$(docker exec "$target_container"',
        'test -n "$source_functions" && test "$source_functions" = "$target_functions"',
        "SECURITY FAILURE: independent cluster function definitions or security configuration differ",
    ):
        assert required in section, f"Independent function parity gate missing: {required}"
