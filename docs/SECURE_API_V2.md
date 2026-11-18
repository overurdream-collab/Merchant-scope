# Secure PostgreSQL API v2 — development review only

Run migrations 001_init.sql and 002_identity.sql against a dedicated PostgreSQL 16+ database as an administrator. Create trusted DB roles/credentials for the service; neither credentials nor data are committed to GitHub. Do not expose admin database connection to FastAPI.

## Server env
- `MERCHANTSCOPE_ADMIN_DSN` (offline bootstrap only, never used in the running API)
- `MERCHANTSCOPE_AUTH_DSN` (server-only auth role with no write permission to merchant business tables)
- `MERCHANTSCOPE_DATA_DSN` (server-only connection role permitted to SET LOCAL ROLE merchant_runtime)

Install dependencies: `pip install -r requirements-dev.txt "psycopg[binary]>=3.2,<4"`

Offline bootstrap: `python scripts/bootstrap_pg.py` (prompted for organization/email/password).

API entrypoint: `uvicorn app.pg_api:app --host 127.0.0.1 --port 8788`. Serve through hardened TLS termination only after security review. API v2 uses `Authorization: Bearer <opaque session>`, user-specific roles and tenant-scoped PostgreSQL transactions, not shared local-pilot secrets.

## Arabic browser workspace\nThe v2 application now serves a dedicated Arabic RTL interface at `/` with per-user email/password/org login, tenant-scoped merchant registry, evidence entry, deterministic analysis, pending review, and independent reviewer controls. The bearer token is retained only in page memory, not localStorage, so a refresh requires logging in again.\n\n## Initial secured API capabilities
- `POST /api/v2/login`, `GET /api/v2/me`, `POST /api/v2/logout`
- `GET/POST /api/v2/merchants`, merchant dossier and dated evidence creation
- Evidence-gated assessment/recommendations
- Pending review and approval by independent reviewer under database triggers

## Still missing before launch
Production rate limits/session/device management, security reviews for bearer-browser handling, MFA, signed audit of identity events, user invitations/recovery, OSM and authorized platform connectors in v2, portfolio reporting, backup and restore, live model evaluation, security penetration tests and actual deployment. SQLite and PostgreSQL backends remain separate; do not point both at the same data. Live secure UI browser acceptance has been added to the PostgreSQL workflow but the complete production release is NOT approved.

## CI
`.github/workflows/postgres-rls.yml` starts disposable PostgreSQL and exercises account bootstrap, password validation, session lifecycle and complete merchant/evidence/assessment/reviewer API flow. Real external connectors and model execution are not claimed by these tests.
\n## Threats and release safeguards\nUse separate least-privileged PostgreSQL connection accounts. Do not reuse a migration superuser for the running service even though disposable CI tests use superuser connections. Reverse-proxy TLS handling must be configured carefully: the API enforces HTTPS for non-loopback clients. Never commit tokens, connection strings, or real merchant data. Lock down authentication attempts and user onboarding before external network access.\n