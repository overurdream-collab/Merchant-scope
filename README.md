# MerchantScope | مرصد التجار

Independent GitHub-native merchant intelligence project. **Not production-ready.**

## Two distinct execution paths

### Legacy local SQLite pilot
`app.main:app` uses a shared `X-Admin-Token` and SQLite. It has an Arabic RTL dashboard at `/`, heuristic evidence-based scoring, source-linked evidence, bounded CSV import preview/commit, human approval queue, proposal drafts, and optional locally configured Ollama drafting. No external platform scraping, licensed social API connector, automatic outreach or live market claims are provided. This path has **no production-grade identity, tenant isolation or independent reviewer authentication**. Never expose it publicly or store sensitive real merchant records.

Run locally (Python 3.11+):

```bash
python -m venv .venv
# Activate the environment for your shell, then:
pip install -r requirements-dev.txt
# Set MERCHANTSCOPE_ADMIN_TOKEN to a long random secret in your environment.
uvicorn app.main:app --host 127.0.0.1 --port 8000
python -m pytest -q
```

### PostgreSQL secure developer preview
`app.pg_api:app` and `app/secure_dashboard.html` implement a **separate** PostgreSQL-backed identity/roles/tenant-isolation preview. Consult `docs/SECURE_API_V2.md`, `docs/REQUIREMENTS_TRACEABILITY.md` and the ordered `db/postgres/` migrations before configuring `MERCHANTSCOPE_AUTH_DSN` and `MERCHANTSCOPE_DATA_DSN`. Bootstrap the first admin offline using `scripts/bootstrap_pg.py`. Serve only on loopback during development:

```bash
uvicorn app.pg_api:app --host 127.0.0.1 --port 8788
```

Do **not** treat this preview as a migration of existing SQLite pilot data or as permission to deploy to the public internet.

## Evidence and acceptance boundaries

- `.github/workflows/ci.yml` tests the Python API, JavaScript syntax, a synthetic Chromium browser smoke flow and loopback Docker startup of the **legacy pilot**. These green checks do not establish PostgreSQL tenant isolation.
- `.github/workflows/postgres-rls.yml` separately tests disposable PostgreSQL security and backup/restore regressions. Verify the **exact candidate commit** and its workflow result; success of the legacy CI workflow is not a substitute.
- `docs/PG_BACKUP_RESTORE.md` explains same-cluster synthetic restore limitations. It does not prove production backup schedules, offsite encrypted retention, PITR, fresh-cluster role restoration, or measured RPO/RTO.
- `docs/MARKETING_SKILLS.md` describes proposed Boring Marketing Skills only. Do not execute third-party skills until their pinned revision, license, dependencies, prompts and network actions have been reviewed.
- Real Facebook, Instagram, TikTok and Maps connectors require lawful authorized access, source/observed-at/licensing provenance and deletion workflows. Do not infer live metrics from the local synthetic fixtures.
- No autonomous outreach. Human review and authorization remain mandatory.

## Open release gates

Track [identity, RLS and PostgreSQL acceptance (#2)](https://github.com/overurdream-collab/Merchant-scope/issues/2), [lawful source connectors (#3)](https://github.com/overurdream-collab/Merchant-scope/issues/3), [audited AI/marketing skills (#4)](https://github.com/overurdream-collab/Merchant-scope/issues/4), and [real pilot, E2E, security, deployment and recovery (#5)](https://github.com/overurdream-collab/Merchant-scope/issues/5). PR #1 remains a review vehicle, not a production approval. Never merge or announce production readiness without complete, independently verified P0 evidence.
