"""Fail-closed CI regression for untrusted pull-request and database credentials.

This checks repository workflow policy, not runtime authorization.
"""
from pathlib import Path
import re

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def test_untrusted_pull_requests_cannot_acquire_write_permissions():
    for workflow in WORKFLOWS.glob("*.yml"):
        source = workflow.read_text(encoding="utf-8")
        assert "pull_request_target:" not in source, workflow.name
        assert "workflow_run:" not in source, workflow.name
        assert "permissions: write-all" not in source, workflow.name
        assert not re.search(r"^\s*(contents|actions|checks|deployments|issues|packages|pull-requests|security-events):\s*write\s*$", source, re.M), workflow.name


def test_live_postgres_ci_uses_disposable_service_not_production_secrets():
    ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    job = ci.split("\n  postgres-live-security:\n", 1)[1].split("\n  browser-smoke:\n", 1)[0]
    assert "image: postgres:16" in job
    assert "POSTGRES_DB: merchantscope_test" in job
    assert "PG_TEST_DSN: postgresql://postgres:test-password@localhost:5432/merchantscope_test" in job
    assert "${{ secrets." not in job
    assert "continue-on-error:" not in job
    assert "upload-artifact" not in job
