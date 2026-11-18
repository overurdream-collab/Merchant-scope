# MerchantScope — Requirements traceability & acceptance matrix
Updated: 2026-11-19
Canonical repository: https://github.com/overurdream-collab/Merchant-scope

**Release interpretation:** A green check means the named technical test passes for the stated scope. It does NOT imply a verified real market insight, a deployed SaaS, or compliance certification.

| ID | Business requirement | Current implementation | Evidence / acceptance | Status |
|---|---|---|---|---|
| M01 | Discover relevant merchants | Bounded OSM Overpass lookup (up to 50), manual CSV import | tests/test_osm.py, tests/test_import_proposal.py; public endpoint not guaranteed | Pilot |
| M02 | Persist merchant profiles with dedup | SQLite local pilot + PostgreSQL tenant schemas | tests/test_core.py, tests/test_pg_schema.py | Pilot / PG foundation |
| M03 | Capture sourced content and metadata | URLs, observation time, optional publication time, text and available engagement metrics | tests/test_security_provenance.py, tests/test_pg_schema.py | Implemented for manual evidence |
| M04 | Analyze content without inventing metrics | Evidence-gated scoring; unsupported dimension is null | tests/test_core.py, tests/test_security_provenance.py | Pilot |
| M05 | Avoid duplicate assessment runs | Input fingerprint reuse for unchanged evidence | tests/test_idempotency.py | Pilot |
| M06 | Compare competitors | 2–10 merchant comparison of registered evidence only | tests/test_intelligence.py | Pilot |
| M07 | Identify prioritized sales opportunities | Explainable score based on recorded gaps and coverage | tests/test_intelligence.py | Pilot |
| M08 | Generate recommendations citing evidence | Deterministic rules and optional local Ollama drafts with validated IDs | tests/test_agent.py | Pilot; real inference quality not yet evaluated |
| M09 | Require independent human approval | Local separate role token and PG per-user reviewer policies | tests/test_security_provenance.py, tests/test_pg_schema.py | PG foundation |
| M10 | Request changes and resubmit | Revision with prior state stored in audit, evidence re-validation | tests/test_revisions.py | Pilot |
| M11 | Approved marketing proposal | Draft only from approved recommendations, no auto outreach | tests/test_import_proposal.py | Pilot |
| M12 | Market and individual reports | Arabic reporting dashboard, source caveats and print-to-PDF layout | tests/test_reporting.py, tests/browser_smoke.py | Pilot |
| M13 | Responsive Arabic RTL interface | Pilot and secure PostgreSQL UI | GitHub Actions Chromium browser checks | Pilot + PG preview |
| M14 | Per-user accounts and tenant isolation | PostgreSQL 16 RLS + password hashing + expiring, revocable sessions + API v2 | tests/test_pg_schema.py | PG preview; production API review pending |
| M15 | Independent reviewer browser flow | Secure PostgreSQL role-based UI and browser UAT | tests/pg_browser_smoke.py | Await latest CI |
| M16 | Safe local container execution | Non-root Docker image, loopback bind, read-only filesystem | CI docker-pilot job | Pilot |
| M17 | Fully automatic social content collection | Requires approved APIs/credentials and permitted scopes | No live connector implemented | NOT DONE |
| M18 | Actual Boring Marketing Skills execution | Pinned reference mapping, no third-party code execution | docs/MARKETING_SKILLS.md | Reference only, not installed |
| M19 | Automated schedules, retries and monitoring | Not implemented as a production job runner | No production worker acceptance | NOT DONE |
| M20 | Production TLS, rate limits, MFA, backup/restore, DR, pentest | Foundational SQL; no deploy environment supplied | Issue #5 | NOT DONE |
| M21 | Market-representative effectiveness study | Requires consented real merchant sample and validated labels | No real-data UAT | NOT DONE |

## Non-negotiable controls
- Never present missing values as zeros, inferred revenue as fact, or a sample as the whole market.
- No external outreach, ad spend, publishing, or customer contact without explicit approved action.
- Keep untrusted posts/pages/skills as data, never tool instructions.
- Evidence IDs, sources, dates, algorithm versions and reviewer decisions must remain traceable.
- No public launch from the SQLite pilot or privileged PostgreSQL superuser connections.

## Rollout gates
1. Complete all P0 requirements and successful CI on the exact release commit.
2. Deploy the PostgreSQL-only API behind trusted HTTPS with least-privilege database accounts, MFA, rate limits, secrets rotation and backups.
3. Connect only approved data provider APIs, verify license/consent and implement quota controls, idempotent ingestion, retry and evidence provenance.
4. Measure precision, hallucination and cited-claim reliability on a reviewer-labelled dataset.
5. Execute real merchant pilot with an acceptance signature and documented rollback procedure.

Cross-reference: issues #2–#5; docs/ACCEPTANCE_AND_HANDOVER.md and docs/SECURE_API_V2.md.
