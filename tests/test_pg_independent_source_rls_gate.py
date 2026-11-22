"""Static regression guard: recovery parity cannot certify an insecure source.

The live PostgreSQL workflow, not this test, establishes actual RLS behavior.
"""
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/postgres-rls.yml"


def test_independent_restore_rejects_disabled_rls_in_both_clusters():
    text = WORKFLOW.read_text(encoding="utf-8")
    section = text.split(
        "- name: Rehearse restore on independent PostgreSQL cluster with global roles", 1
    )[1].split("- name: Upload secure synthetic UI screenshots", 1)[0]
    for required in (
        'disabled_rls_sql=',
        'AND NOT c.relrowsecurity',
        'for cluster_db in "$source_container:merchantscope_test" "$target_container:merchantscope_restore"; do',
        'disabled_rls="$(docker exec "$cluster" psql -X -U postgres -d "$database" -Atc "$disabled_rls_sql")"',
        'test -z "$disabled_rls"',
    ):
        assert required in section, f"Missing independent source/restore RLS gate: {required}"
