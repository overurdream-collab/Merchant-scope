-- MerchantScope production identity foundation. Run after 001_init.sql.
BEGIN;
DO $$ BEGIN CREATE ROLE merchant_auth NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE TABLE ms.user_accounts (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 email text NOT NULL UNIQUE CHECK (email = lower(email)),
 password_hash text NOT NULL,
 disabled_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE ms.sessions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 user_id uuid NOT NULL REFERENCES ms.user_accounts(id) ON DELETE CASCADE,
 org_id uuid NOT NULL REFERENCES ms.organizations(id) ON DELETE CASCADE,
 token_hash bytea NOT NULL UNIQUE CHECK (length(token_hash)=32),
 expires_at timestamptz NOT NULL,
 revoked_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY (org_id,user_id) REFERENCES ms.memberships(org_id,user_id)
);
CREATE INDEX sessions_lookup ON ms.sessions(token_hash) WHERE revoked_at IS NULL;
CREATE INDEX sessions_expiry ON ms.sessions(expires_at);
REVOKE ALL ON ms.user_accounts,ms.sessions FROM PUBLIC;
GRANT USAGE ON SCHEMA ms TO merchant_auth;
GRANT SELECT ON ms.user_accounts,ms.memberships,ms.organizations TO merchant_auth;
GRANT SELECT,INSERT,UPDATE ON ms.sessions TO merchant_auth;
-- Runtime has no direct access to authentication secrets.
REVOKE ALL ON ms.user_accounts,ms.sessions FROM merchant_runtime;
COMMIT;
