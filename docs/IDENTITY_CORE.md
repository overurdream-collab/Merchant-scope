# PostgreSQL identity foundation (development branch)

This module adds per-user credentials and opaque session tokens to the PostgreSQL RLS schema. Passwords use salted PBKDF2-HMAC-SHA256 with 600,000 iterations; stored sessions contain only SHA-256 token hashes, never plaintext bearer tokens. Role and tenant memberships are read from the database at every session resolution.

## Files
- db/postgres/001_init.sql: tenant data and independent-review RLS controls.
- db/postgres/002_identity.sql: user accounts, sessions and restricted merchant_auth role.
- app/pg_identity.py: offline bootstrap_admin, login, resolve_session, revoke_session, and tenant_transaction.
- tests/test_pg_schema.py: runs on an ephemeral PostgreSQL 16 GitHub Actions service.
- tests/test_identity_crypto.py: deterministic password/session cryptography tests.

## Production integration not yet performed
This is an isolated foundation branch; existing public FastAPI routes still use local SQLite and shared role tokens. A trusted service must use separate DB credentials for authentication and restricted tenant data. Never expose database credentials or role-selection settings to clients. Validate Authorization header and CSRF/session handling when a browser API is built. Identity setup via bootstrap requires a privileged *offline* migration account and must not be exposed as a public endpoint.

## Security gates
- Real key rotation, disable/revoke, user invitations and MFA still pending.
- Consider using vetted identity provider before open-internet deployment, and complete security review.
- Run PG tests and CI on this branch before merge.
