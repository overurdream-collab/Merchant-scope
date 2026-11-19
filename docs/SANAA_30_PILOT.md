# Sana'a pilot: sourced 30 merchant research candidates (2026-11-19)

## What was actually collected
`research/sanaa_30_candidates_2026-11-19.json` includes 30 factual business directory listing names in Sana'a, each with its own source listing URL. Sources were opened or linked from the directory during research on 2026-11-19, including HappyNew.Day and EatOutMap.

The list is **NOT** a set of 30 fully verified businesses; it is a **pre-review research queue**. Directory pages explicitly warn that their business information may be stale and sometimes compiled months earlier. Do not claim current opening, ownership, verified social profile, consent or marketing weakness based solely on a directory listing.

## Sampling limitations
The selection is intentionally small and convenience-based, with a disproportionate number of flower/gift listings. No inference about total merchants, market share, conversion rates, demographics or competitor ranks is statistically justified.

## Review and operating procedure
1. Use `app.pg_api:app` with PostgreSQL migrations 001, 002 and **003**, individual analyst/reviewer identities, tenant-safe connection roles and the Arabic secure UI.
2. The analyst uploads the JSON manifest in the “عينة البحث والمراجعة” tab and **manually selects** entries for import. An explicit confirmation is required. Import creates research **candidates** only, not merchant profiles.
3. A different named reviewer opens each source URL and records an approval/rejection note. `reviewed` means *directory source reviewed*, **not** business identity guaranteed or outreach permission.
4. An analyst may separately promote the reviewed entry to a merchant, which links the directory listing as provenance. The merchant has **no assessed posts, metrics or outreach approval**.
5. Independently collect actual public post URLs with documented observation/publication dates and allowed methods. Only then assess marketing, and make any outreach subject to a separate explicit review gate.
6. For each of 30 participants in a **real marketing analysis** trial, seek any needed platform authorization/merchant permission, review tenable current evidence, then independently review every recommendation and log unsupported-claim count.

## IP/privacy
The manifest stores public directory *business names and URLs only*, not private phone numbers, emails, biographies, imagery or copied prose. Respect directory terms and Overture/other underlying licenses; a licensing/privacy review is needed before broad automated collection or commercial redistribution. This is a research list, not a broadcast contact list.

## Acceptance criteria
- 30 distinct, dated source-page references, with statuses `unverified` and `not_assessed`.
- 0 automatically contacted merchants.
- 100% of candidate conversions require independent review; all steps auditable.
- Refusing external source records or unknown evidence results in unavailable scores, not fabricated scores.
- The real merchant analysis KPI phase is NOT complete until independent content verification, outcome labeling and consented UAT take place.

## Open gates beyond code
No production backend instance, live social APIs, real Arabic LLM-evaluation run, independent penetration test or consented merchant study is evidenced by this manifest or its tests.
