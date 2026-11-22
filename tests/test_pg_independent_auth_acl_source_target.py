"""Regression guard for independent-cluster authentication privilege checks.

This static contract only verifies CI wiring; PostgreSQL Actions must execute
the real negative and positive authorization assertions on the exact head.
"""
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/postgres-rls.yml"


def test_independent_restore_checks_auth_privileges_on_both_clusters():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    section = workflow.split(
        "- name: Rehearse restore on independent PostgreSQL cluster with global roles", 1
    )[1].split("- name: Upload secure synthetic UI screenshots", 1)[0]
    start = section.index('          for sql in \\\n            "SELECT relrowsecurity')
    end = section.index("          # Compare and enforce the full SECURITY DEFINER", start)
    acl = section[start:end]
    for required in (
        '"SELECT NOT has_function_privilege(\'merchant_runtime\', \'ms.login_account(text,uuid)\', \'EXECUTE\')"',
        '"SELECT NOT has_function_privilege(\'merchant_runtime\', \'ms.lookup_session(bytea)\', \'EXECUTE\')"',
        '"SELECT has_function_privilege(\'merchant_auth\', \'ms.login_account(text,uuid)\', \'EXECUTE\')"',
        '"SELECT has_function_privilege(\'merchant_auth\', \'ms.lookup_session(bytea)\', \'EXECUTE\')"',
        '"SELECT NOT has_function_privilege(\'PUBLIC\', \'ms.login_account(text,uuid)\', \'EXECUTE\')"',
        '"SELECT NOT has_function_privilege(\'PUBLIC\', \'ms.lookup_session(bytea)\', \'EXECUTE\')"',
        'for cluster_db in "$source_container:merchantscope_test" "$target_container:merchantscope_restore"; do',
        'actual="$(docker exec "$cluster" psql -X -U postgres -d "$database" -Atc "$sql")"',
        'test "$actual" = t',
    ):
        assert required in acl, f"Missing source/target authentication ACL gate: {required}"
