# PostgreSQL 16 tenant and review foundation
Migration: `db/postgres/001_init.sql`. Run only on an empty dedicated database as a privileged database administrator. It creates the `ms` schema and no-login `merchant_runtime` role. It does **not** create real user identities, sessions, application connection secrets, or a deployed API.

## Isolation model
The trusted application must validate identity and organization membership, open one transaction, then set `SET LOCAL app.user_id` and `SET LOCAL app.org_id` for that transaction before assuming the restricted runtime role. Never grant DB access or role switching to client browsers. Avoid session-pooled connections that can accidentally retain tenant context. Membership checks use security-definer functions and row-level-security policies; tests verify one tenant cannot read another.

## Approval model
Analyst creates pending recommendations. Reviewer must be a different user and must have reviewer role; approving requires an evidence linkage. Reviewer cannot rewrite marketing copy. Separate lead outreach approval is required before contacted/proposal/won transitions. Audit is written by DB triggers rather than direct application inserts.

## CI
Dedicated workflow `.github/workflows/postgres-rls.yml` starts ephemeral PostgreSQL 16 and tests schema install, organization isolation, reviewer read-only policy, evidence-based approval, and audit restrictions.

## Known release blockers
This SQL is a tested **foundation**, not the active SQLite app. Migration/dual-run, session identity verification, tenancy-aware API queries, backup/restore, and security review must complete before production deployment. This design assumes a trusted server that prevents arbitrary SQL / forged session settings.
