# PostgreSQL backup and restore rehearsal

The `postgres-rls.yml` GitHub Actions workflow now tests a **disposable CI-only PostgreSQL 16 backup/restore** using `pg_dump -Fc -n ms` and `pg_restore` into a separate newly created database. It checks row counts for organizations, merchants, candidates, evidence, recommendations and audit events, and compares every `ms` table's row count and canonical JSONB row-content digest, along with restored column metadata, constraints, index definitions, RLS flags and policy definitions. This catches changed rows even when counts match, and detects missing or altered schema objects after restoration. The digest is an integrity regression check, not a cryptographic proof of a trustworthy backup or a substitute for restore drills.

## Scope limitations
- This is an automated CI rehearsal, **not** evidence that a production backup schedule, offsite encryption, immutable retention, PITR/WAL archive, replica failover or disaster recovery configuration exists.
- The archive is kept on the temporary GitHub runner and not uploaded as an artifact, so synthetic identities and data are not persisted externally.
- Never run a restore into a working production database or with production secrets without a separately approved change and tested rollback plan.
- PostgreSQL roles are cluster-global and are not included in a schema-only `pg_dump`: for recovery onto a new server, provision the minimum necessary roles first via audited migrations, or use a reviewed `pg_dumpall --globals-only` and protect it as a privileged secret.
- Schedule encrypted production backups, test restore to an isolated host, compare row counts and policy enforcement, and document RPO/RTO before launch.

## Release gate
- CI must pass all backup/restore checks on the exact release commit.
- Production acceptance additionally requires an **actual encrypted, access-controlled backup** and observed restoration time into a separate environment, both approved by operations/security.
