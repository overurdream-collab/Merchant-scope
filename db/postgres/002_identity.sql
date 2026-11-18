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
-- User/account/member lookup is through narrow SECURITY DEFINER functions only.
GRANT SELECT,INSERT,UPDATE ON ms.sessions TO merchant_auth;
-- Runtime has no direct access to authentication secrets.
REVOKE ALL ON ms.user_accounts,ms.sessions FROM merchant_runtime;

-- Authentication-only SECURITY DEFINER lookups bypass tenant RLS after validating
-- that the account belongs to the requested organization. Never expose these to runtime.
CREATE FUNCTION ms.login_account(p_email text,p_org uuid)
RETURNS TABLE(user_id uuid,password_hash text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=ms,pg_temp AS $$
 SELECT a.id,a.password_hash FROM ms.user_accounts a
 JOIN ms.memberships m ON m.user_id=a.id AND m.org_id=p_org
 WHERE a.email=p_email AND a.disabled_at IS NULL
$$;
CREATE FUNCTION ms.lookup_session(p_digest bytea)
RETURNS TABLE(id uuid,user_id uuid,org_id uuid,role ms.member_role)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=ms,pg_temp AS $$
 SELECT s.id,s.user_id,s.org_id,m.role FROM ms.sessions s
 JOIN ms.user_accounts a ON a.id=s.user_id
 JOIN ms.memberships m ON m.user_id=s.user_id AND m.org_id=s.org_id
 WHERE s.token_hash=p_digest AND s.revoked_at IS NULL AND s.expires_at>now()
   AND a.disabled_at IS NULL
$$;
REVOKE ALL ON FUNCTION ms.login_account(text,uuid),ms.lookup_session(bytea) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ms.login_account(text,uuid),ms.lookup_session(bytea) TO merchant_auth;
COMMIT;
