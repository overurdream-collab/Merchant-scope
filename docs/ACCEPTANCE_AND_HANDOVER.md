# MerchantScope — Technical handover / release acceptance
Date: 2026-11-19
Source of truth: https://github.com/overurdream-collab/Merchant-scope
Review PR: https://github.com/overurdream-collab/Merchant-scope/pull/1
Release state: **development preview / controlled local pilot — NOT production approved**.

## Delivered code and design

### Legacy local pilot (SQLite, only 127.0.0.1)
- Responsive Arabic RTL dashboard with merchant list, profiles, evidence, competitor/sample comparisons, scoring, sales leads, review workflow, CSV imports/exports, portfolio reports, PDF printing.
- Bounded OSM Overpass discovery with manual confirmation and provenance; no unauthorized scraping.
- Optional local Ollama marketing draft engine (modes content/audience/competition/prospecting/proposal). Outputs require valid evidence IDs and independent human review, and unsupported percentage claims/guarantees are filtered conservatively.
- No repeated analysis for unchanged evidence inputs, and auditor-visible revision/resubmission history.
- Loopback-only Docker Compose, non-root process and read-only container filesystem.
- Python, browser Chromium, JS, container smoke tests on synthetic data.

### Isolated secure PostgreSQL v2 (separate application entrypoint)
- Dedicated SQL schema and migrations `db/postgres/001_init.sql`, `002_identity.sql`.
- Per-user email/password authentication, salted PBKDF2 digests, revocable hashed bearer sessions, tenant-scoped PostgreSQL transactions and enforced RLS.
- Independent reviewer role for recommendation approvals and sales outreach. Reviewer cannot write merchant data. No self-approving author.
- Arabic browser UI `app/secure_dashboard.html` and FastAPI `app/pg_api.py`.
- Merchant registry, evidence entry, assessment, review, portfolio reporting, competitor comparison, opportunities, lead approval, approved proposal drafts, and manually confirmed OSM merchant discovery.
- Offline bootstrap and add-user tooling `scripts/bootstrap_pg.py`, `scripts/add_pg_user.py`. No public registration.
- Tests use disposable PostgreSQL 16 and synthetic merchants, separate analyst/reviewer browser login, documented sources, rejected cross-tenant access, and manual approval safeguards.

## Verified test evidence (commit-specific)
- Commit `9066c258`: [PostgreSQL 16 RLS/secure UI success](https://github.com/overurdream-collab/Merchant-scope/actions/runs/44425922391) and [Python/Arabic UI/Docker success](https://github.com/overurdream-collab/Merchant-scope/actions/runs/44425922393).
- These tests establish functional correctness for covered synthetic cases only, not security certification, provider API availability, or production readiness.
- The exact latest branch head must be reverified in GitHub Actions after every new commit. Never infer success from a previous commit's checks.

## External systems and limitation register
- **Facebook / Instagram / TikTok / Google Places marketing analytics:** live API credentials/approved permissions NOT supplied. No compliant automatic collection can be verified or activated.
- **Ollama / LLM:** optional local code exists, but no validated Arabic model or labelled real merchant acceptance dataset configured. Hallucination/relevance metrics cannot be certified.
- **Boring Marketing Skills:** source pinned to `bd5aaedab44368d76326d98d488697158b886679`; curated prompts/task mapping only. Third-party scripts are NOT blindly installed.
- **Real merchant UAT:** not conducted, no consented sample or baseline outcomes provided; all tests use synthetic data.
- **Public deployment:** no real TLS/production host, distributed rate limits, MFA, managed backups/restore tests, vulnerability assessment, or cost alerting verified. The PostgreSQL v2 is not deployed as a public application.
- **Migration:** no existing production SQLite or Lovable data has been migrated into PostgreSQL. Do not equate two supported data models with a completed migration.

## Acceptance criteria for commercial launch
1. Every account authenticates individually with independent, non-bypassable reviewer permissions, tenant isolation and identity/session negative tests.
2. Every observed claim includes timestamp, source reference, and confidence; missing evidence remains missing. Human reviewer approves every outward recommendation, proposal or communication.
3. All external collection uses API-permitted methods and upholds provenance, consent, deletion, rate limits, source terms and attribution.
4. End-to-end user acceptance on real consented merchant data, with precision/false-claim assessment, restoration and rollback drills, security review, and verified public HTTPS deployment.
5. All CI checks pass on the final release commit and the owner explicitly signs off the release.

**Decision: application code substantially advanced; no honest basis to declare all production gates complete.** PR #1 should stay in draft until these items are met. No outreach or spending is automated.

## Next engineering priority
Real approved provider configuration → LLM evaluation data → production auth hardening, MFA/rate limits/backup → deployment → real-world reviewer acceptance. Do not copy fake credentials or invent marketing analytics.
