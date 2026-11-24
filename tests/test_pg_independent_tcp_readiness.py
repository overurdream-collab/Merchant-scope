"""Regression for issue #2: postgres image bootstrap uses a socket-only server."""
from pathlib import Path


def test_independent_restore_waits_for_final_tcp_server():
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/postgres-rls.yml").read_text(encoding="utf-8")
    step = workflow.split("name: Rehearse restore on independent PostgreSQL cluster with global roles", 1)[1]
    step = step.split("name: Upload secure synthetic UI screenshots", 1)[0]
    readiness = 'docker exec "$target_container" pg_isready -h 127.0.0.1 -U postgres -d merchantscope_restore'
    assert step.count(readiness) == 2
    assert step.index("docker run -d") < step.index(readiness)
    assert step.rindex(readiness) < step.index("pg_dumpall")
    assert 'docker exec "$target_container" pg_isready -U' not in step
