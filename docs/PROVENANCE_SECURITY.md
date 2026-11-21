# Evidence provenance and reviewer separation (local pilot)
- observed_at is date/time the collector observed the source; this is NOT necessarily when a post was published.
- published_at is optional and must be explicitly documented from a source. Scores for posting regularity are unavailable until at least three distinct publication dates are present.
- A separate MERCHANTSCOPE_REVIEWER_TOKEN enforces review segregation when set. Analysts using MERCHANTSCOPE_ADMIN_TOKEN cannot approve outreach or recommendations when reviewer token configured. These remain *role tokens*, not personal identities.
- MERCHANTSCOPE_LOCAL_ONLY=1 blocks non-loopback access by default. This remains a local pilot; do not set to 0 for production without proper authentication and security review.
- Source URLs and engagement counts are recorded as supplied; no independent online verification or collection takes place.
