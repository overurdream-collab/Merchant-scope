# MerchantScope — Verified handover and remaining acceptance gates
Date: 2026-11-19

## Canonical repository
https://github.com/overurdream-collab/Merchant-scope
Draft PR #1: https://github.com/overurdream-collab/Merchant-scope/pull/1

## Working local pilot (SQLite, loopback-only by default)
- Arabic RTL dashboard with merchant registry, source links, timestamped evidence, documented publication dates, assessments, market comparisons, opportunities, review, audited approved proposals, CSV preview/import/export.
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
- Existing Python local pilot CI: https://github.com/overurdream-collab/Merchant-scope/actions/runs/44420427201 — success, 31 tests plus compilation and browser JavaScript syntax validation.
- No migration to production PostgreSQL data service has been performed.

## Open P0 gates
1. Implement production API with authenticated individual sessions and safe transactional PostgreSQL tenant context; connect entire UI. Migrate old SQLite pilot records with rehearsal and backup/restore. Enforce role separation by user, not only shared secrets.
2. Verify live target environment for OSM, privacy/legal requirements and permissions. Add approved source API integrations (Meta/Google/TikTok where allowed), content snapshots, scheduled ingestion and idempotent retries.
3. Install an actual local/hosted model and evaluate Arabic content, hallucination rate, proof checking, source citation accuracy, prompt injection and costs. Read and audit skills before enabling any external workflow.
4. Perform browser E2E tests and real merchant UAT with documented evidence, negative permissions tests, restore drill, threat model, deployment and monitoring.
5. Do not contact businesses automatically or treat observed sample metrics as complete market statistics.

## Release decision
**Internal local pilot: available for controlled testing.**
**Production launch: NOT APPROVED.**
PR #1 remains draft. No paid services provisioned. Never claim acceptance until open P0 gates pass independently.
