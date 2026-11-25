# Marketing evaluation, commercial proposals and release gates (Phase 3–5)

## Phase 3 — measured model quality (NOT YET VERIFIED ON LIVE MODEL)
- Evidence first: the 30 directory listings in `research/sanaa_30_candidates_2026-11-19.json` are not post data. Do not run model scoring or fabricate engagement from them.
- Use real sourced posts, written observations, documented timestamps, and authorized competitor evidence. User/customer permission may be needed depending on platform access and data rights.
- Run the configured local Ollama model when actually available, keep every generated item `pending_review`.
- Have an independent, identified reviewer label each claim **supported**, **partially_supported**, or **unsupported**, verifying citations against source pages. Do not score the model's own self-assessment.
- `python scripts/evaluate_marketing.py path/to/reviews.jsonl --out evaluation.json` outputs a machine-readable, SHA256-sealed evaluation summary and returns nonzero unless the minimum 30 human-attested real consented cases with verified source and reviewer different from creator, 100% known citations, 0 unsupported/partially supported, and >=90% supported hold. This is a *strict software gate*, not proof that reviewers are qualified or genuinely independent.
- Required JSONL per line: `{"case_id":"case-1","sample_origin":"real_consented","source_verified":true,"created_by":"analyst-id","reviewer_id":"different-human-person-id","reviewed_at":"2026-11-25T12:00:00+03:00","evidence":[{"id":"post-1","source_url":"https://example.org/post"}],"claims":[{"text":"This post names a product","evidence_ids":["post-1"],"human_label":"supported"}]}`. Demonstration examples MUST be identified synthetic; there are no real human-labelled cases included in this repository.

## Phase 4 — accountable prices, no guessed ROI
- `app/commercial.py` builds quote drafts from independently **approved**, evidence-linked service lines.
- All line prices, quantities and currency originate with an authorized human/operator; total uses Python Decimal. No external API or fictitious marketing-price benchmark.
- Drafts are **not approved for sending**. Separate owner acceptance of scope, payment terms, currency and tax treatment is required before issuing a quote or contacting anyone.
- Existing PostgreSQL proposal endpoint must enforce source-linked reviewed recommendations. Integrating this independent calculator in a later API PR must preserve the reviewer boundary.

## Phase 5 — launch decision
**NOT READY** until all release prerequisites have independent evidence:
- Exact release commit: Python+browser+PostgreSQL CI pass, security/RLS tests, fail-closed on unauthorized access.
- Controlled live model run on at least 30 actual evidence-rich reviewed cases; measure accuracy, unsupported-claim and citation rates.
- Named independent review, tested price/scope approval (and no automatic outreach).
- Consented real merchant UAT, permitted source APIs, provenance and privacy reviews.
- Production HTTPS, multi-user authentication hardening, secrets, rate limiting/MFA, audited backup/restore and recovery plans, threat model and penetration review.
- No publicly deployed or production-ready status inferred from successful synthetic CI.

## Outcome matrix
| Required evidence | Status |
| --- | --- |
| 30 sourced directory candidate entries | Prepared, not verified social activity |
| 30 model results reviewed by humans | NOT DONE |
| Reliable market and competitor analytics on real posts | NOT DONE |
| Reviewable, evidence-grounded offer/pricing engine | Draft helper implemented |
| Security and recovery synthetic CI | Existing checks, latest PostgreSQL workflow currently requires repair |
| Production acceptance | NOT APPROVED |

Independent workstreams PR #9 (secure AI integration), #10 (local PostgreSQL deployment) and #8 (CSP hardening) remain open/draft; merge only after comparing against current development head and passing exact-head CI.

**Do not substitute synthetic examples:** a synthetic sample always fails the release gate irrespective of perfect citations. Human attestations must themselves be independently audited; software cannot detect intentionally false attestations.
