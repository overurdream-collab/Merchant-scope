# MerchantScope verified implementation and release gates
Date: 2026-11-19. Source of truth: GitHub PR #1, branch feat/merchant-intelligence-mvp.

## Available in local pilot
- Responsive Arabic RTL dashboard for merchants, dated evidence, cautious metrics, market sample comparisons, leads, pending recommendations and approval decisions.
- Bounded OpenStreetMap discovery (read-only preview), manually confirmed imports, OSM URL provenance and ODbL attribution in CSV exports.
- Optional Ollama localhost agent with five task modes (content, audience, competition, prospecting, proposal), strict existing-evidence-ID validation and pending human review; no model/API key supplied, so actual AI model inference is **not verified**.
- Separate analyst and reviewer local secrets when MERCHANTSCOPE_REVIEWER_TOKEN is configured. Default denies remote access.
- Evidence distinguishes observed_at from published_at; unknown publication dates never count toward posting-consistency scoring.
- Human approval before outreach, with no autonomous messages sent.
- Source policy docs/MARKETING_SKILLS.md and docs/OSM_DISCOVERY.md.

## Verified by GitHub CI
30 passing automated tests + Python compilation + JavaScript syntax check on commit 6d0d57c; later source attribution changes must re-run CI. Tests use synthetic data and mock the external OSM endpoint and local model.

## Blockers for production acceptance
1. PostgreSQL backend, migrations, tenant isolation, identity sessions and independent per-user reviewer authorization; existing per-role tokens are **NOT production-ready**.
2. Confirm live Overpass reachability and terms in target deployment, avoid misuse of shared public API. Social platform collectors (Meta/TikTok/Google) need consent and approved APIs.
3. Live Ollama model installed and evaluated with Arabic merchant evidence, false claims, prompt injection and quality benchmark; skills mappings reviewed but upstream source code not run.
4. Deployment, secrets, backups, recovery drills, security testing, browser E2E tests, real merchant pilot and operating-cost limits.
5. Legal review of personal data, communication permissions and OSM-derived data rights.

## Release decision
Local pilot **accepted for internal testing only** if CI stays green; production release **REJECTED until all P0 gates pass**. Draft PR #1 must not merge as production-ready.

## Acceptance process for next engineer
- Read README and docs/PROVENANCE_SECURITY.md.
- Check PR #1 and GitHub Actions, reproduce tests.
- Work on a separate reviewable branch, add negative auth tests.
- Use real merchant data only with documented public/authorized provenance, never fabricate.
- Do not silently enable outbound marketing.
