# MerchantScope | مرصد التجار

GitHub-native marketing intelligence pilot, independent of Lovable.

**Three goals:** identify marketing-service prospects, research competitors and markets, and assess merchant marketing content with evidence-based reviewable recommendations.

## Local run

Requires Python 3.11+.

```bash
python -m venv .venv
# PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
```

Set a long secret in your terminal (`$env:MERCHANTSCOPE_ADMIN_TOKEN="long-random-value"` in PowerShell or `export MERCHANTSCOPE_ADMIN_TOKEN="long-random-value"` in Bash), then run:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
python -m pytest -q
```

Open `http://127.0.0.1:8000/docs` for the API documentation. Supply the secret through the `X-Admin-Token` header. The application currently has an API-only interface; its web dashboard is not yet implemented in this repository.

## Scope actually implemented
- SQLite local merchant register, duplicate prevention, channels and source-linked evidence
- Six-dimension **heuristic** scoring with unavailable vs zero distinction and coverage threshold; generated recommendations only from measured deficiencies
- Human approval queue, outreach approval before moving sales lead to contacted/proposal, audit records
- CSV export with formula neutralization; CSV import **preview only**
- Automated tests and GitHub Actions CI

## Security / limitations
- **LOCAL PROTOTYPE ONLY**. Single shared token; no user identity, RBAC, or tenant isolation. Never expose this service on a public interface, nor store sensitive data.
- The URL validator does not fetch external content. Real platform collection requires compliant integrations; there is NO Facebook, TikTok, Instagram or Maps API integration, no scraping, no LLM execution and no scheduled automation.
- Approval represents a local operator action, not an independently identified reviewer. No external messages or advertising are sent.
- The competitor dimension is unavailable until verified comparative data is implemented.
- Scores are simple transparent heuristics, not statistically validated measurements.
- Data from Lovable is not imported. This is an independent implementation.

## Next engineering phases
1. PostgreSQL; auth, role-based and tenant-scoped policies, role-separated reviewers; evidence history and safe URLs.
2. Complete Arabic RTL frontend and audit-friendly reporting; competitor comparisons and market intelligence.
3. Version-pin and audit selected MIT-licensed boring-marketing-skills, connect authorized platforms.
4. End-to-end acceptance, security scans, operational backups, monitoring and approval workflows.


## Iteration 2 — Dashboard & intelligence endpoints
- Arabic RTL browser dashboard at `/` (secret entered each session; not persisted)
- Overview KPI endpoint, sample-limited market segmentation by city/category
- Evidence-aware 2–10 merchant comparison without speculative ranking
- Internal lead opportunity prioritization; score unavailable if evidence coverage is insufficient
- Human-review queue & audit, CSV dedup preview, reports via browser print, safe external source links
- Read-only marketing skill catalog: 7 proposed Boring Marketing Skills; **NOT installed/executed**
- Additional API tests for market, comparison, permissions, and dashboard

**Acceptance boundary:** This is a functional **local pilot**, not a production multi-user SaaS. Real market discovery, API-licensed platform collection, scheduled agents, independent security review, enterprise tenancy, PostgreSQL, and live production deployment remain outside this verified release. No fake live integrations. Do not expose the pilot service to the public internet.


## Iteration 3 — explicit approved import & proposal generation
- `POST /api/import/commit`: human-confirmed, bounded merchant bulk import (validated fields, deduplication and audit). This **does not** scrape external platforms.
- `GET /api/merchants/{id}/proposal`: evidence-linked proposal draft **only from human-approved recommendations**. Never sends messages or makes performance promises.
- Tests assert confirmation requirement, idempotent duplicates, unsafe-link validation and proposal prerequisites.

## Optional local AI agent (Ollama)
To run local model-assisted drafting, start Ollama on **127.0.0.1:11434**, install a model with sufficient Arabic proficiency, then set `MERCHANTSCOPE_OLLAMA_MODEL` to its exact name. API: `POST /api/merchants/{id}/agent-draft` with `{"mode":"content"|"audience"|"competition"|"prospecting"|"proposal"}`. Model must return JSON citing existing evidence IDs. Invalid or unsupported citations are rejected, and any valid drafts remain `pending_review`. **No sending, publishing, or financial effect is performed by this endpoint.**
Upstream marketing skills are **conceptually mapped**, not blindly installed or executed. See `docs/MARKETING_SKILLS.md`.
