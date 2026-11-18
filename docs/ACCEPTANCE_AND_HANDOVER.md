# MerchantScope — Verified handover and remaining acceptance gates
Date: 2026-11-19

## Canonical repository
https://github.com/overurdream-collab/Merchant-scope
Draft PR #1: https://github.com/overurdream-collab/Merchant-scope/pull/1

## Working local pilot (SQLite, loopback-only by default)
- Arabic RTL dashboard with merchant registry, source links, timestamped evidence, documented publication dates, evidence-based assessments, market comparisons, ranked opportunities, review, audited approved proposals, CSV preview/import/export.
- Portfolio reporting with measurable evidence coverage, approval statuses, lead stages, source quality warnings and real PDF print layout. Reports use the local merchant sample only.
- Re-running an unchanged assessment reuses the previous result and cannot create duplicate recommendations. New evidence triggers a new assessment.
- Recommendation corrections: reviewer requests changes, analyst revises with evidence IDs, previous decision/content retained in audit, recommendation resubmitted pending review. No silent modification of approved text.
- Local Docker Compose binds 127.0.0.1 only; separate analyst/reviewer keys, non-root container, read-only filesystem and persistent named data volume. Do not publish beyond loopback.
- OSM Overpass public merchant discovery bounded to a selected radius/category, opt-in manual import and ODbL source attribution. Real upstream availability NOT validated by CI.
- Optional Ollama localhost 5-mode marketing agent with evidence-ID validation and human review. No model configured/validated in CI, so do not claim model inference quality.
- Analyst/reviewer secrets can be separated in the local pilot, but these are shared role tokens, NOT user authentication.
- Marketing skill references pinned to boringmarketer/boring-marketing-skills commit bd5aaedab44368d76326d98d488697158b886679; they are curated task mappings, NOT external executable code.

## Production PostgreSQL security foundation (NOT yet wired to pilot API)
- File: db/postgres/001_init.sql
- Tenant RLS + membership roles; reviewer cannot edit merchant records.
- Approval requires a source-evidence link and a different reviewer.
- Lead outreach guarded at SQL layer; audit insert is trigger-owned.
- Tests use a dedicated PostgreSQL 16 GitHub Actions service.
- Verified CI: https://github.com/overurdream-collab/Merchant-scope/actions/runs/44420427187 — success.
- Latest verified Python/local Docker/browser CI: https://github.com/overurdream-collab/Merchant-scope/actions/runs/44422110497 — success. Includes Python test suite, JS syntax check, Chromium end-to-end synthetic UI and PDF print-mode checks, Docker build/health/authentication smoke. Screenshots uploaded as synthetic `merchantscope-ui-acceptance` artifact.
- Latest PostgreSQL RLS CI: https://github.com/overurdream-collab/Merchant-scope/actions/runs/44422110280 — success. PostgreSQL identity design remains a separate draft PR #6, not the running API.
- No migration to production PostgreSQL data service has been performed.

## Open P0 gates
1. Implement production API with authenticated individual sessions and safe transactional PostgreSQL tenant context; connect entire UI. Migrate old SQLite pilot records with rehearsal and backup/restore. Enforce role separation by user, not only shared secrets.
2. Verify live target environment for OSM, privacy/legal requirements and permissions. Add approved source API integrations (Meta/Google/TikTok where allowed), content snapshots, scheduled ingestion and idempotent retries.
3. Install an actual local/hosted model and evaluate Arabic content, hallucination rate, proof checking, source citation accuracy, prompt injection and costs. Read and audit skills before enabling any external workflow.
4. Extend browser E2E tests beyond synthetic smoke to full user journeys; complete real merchant UAT with consent, independent reviewer tests, production restore drill, threat model, deployment, backup and monitoring.
5. Do not contact businesses automatically or treat observed sample metrics as complete market statistics.

## Release decision
**Internal local pilot: available for controlled testing.**
**Production launch: NOT APPROVED.**
PR #1 remains draft. No paid services provisioned. Never claim acceptance until open P0 gates pass independently.

## Evidence after latest improvements
- Main feature branch HEAD before this document: `ad743fc6cb9810e125431c517b0b2f0e194d2feb`; checks passed. 
- New capabilities since previous report: screenshot artifact, Docker smoke, repeat-analysis idempotency and revision/resubmission workflow.
- All live external integrations remain disabled unless explicit credentials and permissions are configured. Data quality must be tested against real consented merchant samples.
