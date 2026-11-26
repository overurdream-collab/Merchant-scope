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
