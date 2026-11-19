# PostgreSQL backup and restore rehearsal

The `postgres-rls.yml` GitHub Actions workflow now tests a **disposable CI-only PostgreSQL 16 backup/restore** using `pg_dump -Fc -n ms` and `pg_restore` into a separate newly created database. It checks row counts for organizations, merchants, candidates, evidence, recommendations and audit events, and compares every `ms` table's row count and canonical JSONB row-content digest, along with restored column metadata (including defaults, identity and generated expressions), constraints, index definitions, user-defined trigger definitions, SQL function/procedure signatures and bodies (including execution-security flags), RLS flags and policy definitions. This catches changed rows even when counts match, and detects missing or altered schema objects after restoration, including audit triggers, security-definer functions or default expressions that row-count checks cannot detect. The digest is an integrity regression check, not a cryptographic proof of a trustworthy backup or a substitute for restore drills.

## Authentication ACL regression gate
The restore deliberately retains schema object ACLs (no `--no-acl` flag). The CI test checks both source and restored databases: neither `ms.login_account` nor `ms.lookup_session` may grant `EXECUTE` to `PUBLIC`, while the narrowly scoped `merchant_auth` role must retain `EXECUTE` on both. This guards against the PostgreSQL default `PUBLIC EXECUTE` privilege on newly created functions, especially dangerous for `SECURITY DEFINER` authentication lookups. The disposable restore shares cluster-global roles with the source; this is not a fresh-cluster disaster recovery test.

## Scope limitations
- This is an automated CI rehearsal, **not** evidence that a production backup schedule, offsite encryption, immutable retention, PITR/WAL archive, replica failover or disaster recovery configuration exists.
- The archive is kept on the temporary GitHub runner and not uploaded as an artifact, so synthetic identities and data are not persisted externally.
- Never run a restore into a working production database or with production secrets without a separately approved change and tested rollback plan.
- PostgreSQL roles are cluster-global and are not included in a schema-only `pg_dump`: for recovery onto a new server, provision the minimum necessary roles first via audited migrations, or use a reviewed `pg_dumpall --globals-only` and protect it as a privileged secret.
- Schedule encrypted production backups, test restore to an isolated host, compare row counts and policy enforcement, and document RPO/RTO before launch.

## Release gate
- CI must pass all backup/restore checks on the exact release commit. The metadata comparisons cover the `ms` schema; they do not prove recovery of cluster-level roles, grants, extensions, or production scheduling.
- Production acceptance additionally requires an **actual encrypted, access-controlled backup** and observed restoration time into a separate environment, both approved by operations/security.
