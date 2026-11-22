"""Offline guard for independent PostgreSQL recovery trigger enforcement.

This protects CI wiring; only the live postgres-rls workflow proves actual restore.
"""
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/postgres-rls.yml"


def test_independent_restore_checks_trigger_inventory_and_enforcement():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    section = workflow.split(
        "- name: Rehearse restore on independent PostgreSQL cluster with global roles",
        1,
    )[1].split("- name: Upload secure synthetic UI screenshots", 1)[0]
    for required in (
        'trigger_catalog_sql=',
        'pg_get_triggerdef(t.oid)',
        't.tgenabled',
        'test -n "$source_triggers"',
        'test "$source_triggers" = "$target_triggers"',
        'trigger_safety_sql=',
        'expected_safe_triggers=',
        'assessments:audit_assessments:29:O',
        'research_candidates:candidate_guard:23:O',
        'test "$safe_triggers" = "$expected_safe_triggers"',
        '"$source_container:merchantscope_test" "$target_container:merchantscope_restore"',
    ):
        assert required in section, f"Independent recovery guard missing: {required}"
