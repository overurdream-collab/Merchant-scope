# MerchantScope | Acceptance and handover report
Date: 2026-11-19

## Source of truth
- GitHub: https://github.com/overurdream-collab/Merchant-scope
- Branch: feat/merchant-intelligence-mvp
- PR: https://github.com/overurdream-collab/Merchant-scope/pull/1 (draft, awaiting production readiness)
- Lovable is NOT a runtime/build dependency.

## Implemented and testable local pilot
1. Register merchants by name/location/activity; avoid duplicate normalized name+city.
2. Record source URLs, dated post observations and channel links; validate URL scheme.
3. Produce a transparent, evidence-gated marketing assessment. Missing dimension = null, not zero. No total when coverage insufficient.
4. Produce grounded recommendations with evidence identifiers.
5. Approve/reject/request changes with recorded review notes and audit.
6. Require human sign-off before a lead can enter contacted/proposal/won stages. No automatic outreach.
7. API and responsive Arabic dashboard: overview, merchant dossier, evidence intake, market sample breakdown, comparisons, opportunities, review, audit, CSV import preview/confirmation, CSV export, and print-ready report view.
8. Build a proposal draft solely from human-approved recommendations and link source evidence.
9. Read-only catalog of 7 reference marketing skills; no unvetted third-party skill execution.
10. Automated API tests plus Python compilation and JavaScript syntax check via GitHub Actions.

## Safety and data accuracy
- Market charts describe ONLY registered merchants, not the overall market.
- No real traders or marketing results have been fabricated or preloaded.
- Links must be user-entered and have permitted http(s) scheme. No authorization to scrape protected platform data.
- Do not publish the local-pilot admin secret or operate the pilot over a public network.
- Source evidence is user supplied, so source authenticity still requires review.

## Missing production-release gates (must NOT be marked complete)
- PostgreSQL migrations, tenant isolation, real account authentication and independent reviewer RBAC.
- Automated and authorized data collection using approved API credentials; batching, scheduling, retry/observability.
- Actual AI model service, reviewed and version-pinned Boring Marketing Skills runtime, multimodal content analysis.
- End-to-end browser tests, deployment and recovery testing, penetration tests and threat-model sign-off.
- Real merchant pilot and human audit of recommendations, benchmark quality and relevance.
- Final host/domain, secret management, source API permissions and billing/cost guardrails.

## Acceptance criteria for production
- 100% of privileged API paths protected by proper identity and role, independent reviewer sign-off demonstrable.
- Merchant duplicates prevented, import and source provenance are auditable.
- Recommendations always linked to permitted and reviewable evidence.
- No unapproved outbound communication; no simulated market figures presented as observed.
- 0 failing CI checks, security review accepted, data restore verified, end-to-end UAT completed.

## Verified evidence
- CI previous commit b3adbf0: https://github.com/overurdream-collab/Merchant-scope/actions/runs/44415944278 (completed success)
- Current commit: verify new run in GitHub Actions before accepting this handover.
- Do not equate passing unit tests with production security or full business acceptance.

## Next implementation order
Authentication + PostgreSQL -> authorized sources and manual validation -> AI inference and vetted skills -> reviewer workflow separation -> secure deployments/monitoring -> real merchant UAT.
