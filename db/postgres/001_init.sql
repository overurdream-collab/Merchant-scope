-- MerchantScope PostgreSQL 16+ tenant security foundation.
-- Do not expose merchant_runtime directly to end users.
BEGIN;
CREATE SCHEMA IF NOT EXISTS ms;
DO $$ BEGIN CREATE ROLE merchant_runtime NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE TYPE ms.member_role AS ENUM ('admin','analyst','reviewer','viewer');
CREATE TYPE ms.review_status AS ENUM ('pending_review','approved','rejected','changes_requested');
CREATE TYPE ms.lead_stage AS ENUM ('new','qualified','contacted','proposal','won','lost');

CREATE TABLE ms.organizations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 name text NOT NULL CHECK (length(name) BETWEEN 2 AND 200),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE ms.memberships (
 org_id uuid NOT NULL REFERENCES ms.organizations(id),
 user_id uuid NOT NULL,
 role ms.member_role NOT NULL DEFAULT 'viewer',
 PRIMARY KEY(org_id,user_id)
);
CREATE TABLE ms.merchants (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 org_id uuid NOT NULL REFERENCES ms.organizations(id),
 name text NOT NULL CHECK (length(name) BETWEEN 2 AND 200),
 normalized_name text NOT NULL,
 category text, city text NOT NULL, governorate text, market text,
 website text, created_by uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(id,org_id), UNIQUE(org_id,normalized_name,city)
);
CREATE TABLE ms.channels (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 org_id uuid NOT NULL,
 merchant_id uuid NOT NULL,
 platform text NOT NULL, url text NOT NULL,
 verified_at timestamptz,
 FOREIGN KEY (merchant_id,org_id) REFERENCES ms.merchants(id,org_id),
 UNIQUE(org_id,url), UNIQUE(id,org_id)
);
CREATE TABLE ms.evidence (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 org_id uuid NOT NULL,
 merchant_id uuid NOT NULL,
 platform text NOT NULL, source_url text NOT NULL CHECK (source_url ~ '^https?://'),
 observed_at timestamptz NOT NULL,
 published_at timestamptz,
 body text, likes bigint CHECK (likes>=0), comments bigint CHECK(comments>=0), views bigint CHECK(views>=0),
 collection_method text NOT NULL DEFAULT 'manual',
 created_by uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY (merchant_id,org_id) REFERENCES ms.merchants(id,org_id),
 UNIQUE(id,org_id),
 CHECK (published_at IS NULL OR published_at <= observed_at)
);
CREATE TABLE ms.assessments (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 org_id uuid NOT NULL, merchant_id uuid NOT NULL,
 result jsonb NOT NULL,
 created_by uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY (merchant_id,org_id) REFERENCES ms.merchants(id,org_id),
 UNIQUE(id,org_id)
);
CREATE TABLE ms.recommendations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 org_id uuid NOT NULL, merchant_id uuid NOT NULL,
 assessment_id uuid,
 problem text NOT NULL, action text NOT NULL, rationale text,
 status ms.review_status NOT NULL DEFAULT 'pending_review',
 created_by uuid NOT NULL, reviewer_id uuid,
 review_notes text, reviewed_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY (merchant_id,org_id) REFERENCES ms.merchants(id,org_id),
 FOREIGN KEY (assessment_id,org_id) REFERENCES ms.assessments(id,org_id),
 UNIQUE(id,org_id)
);
CREATE TABLE ms.recommendation_evidence (
 org_id uuid NOT NULL,
 recommendation_id uuid NOT NULL,
 evidence_id uuid NOT NULL,
 PRIMARY KEY(org_id,recommendation_id,evidence_id),
 FOREIGN KEY (recommendation_id,org_id) REFERENCES ms.recommendations(id,org_id),
 FOREIGN KEY (evidence_id,org_id) REFERENCES ms.evidence(id,org_id)
);
CREATE TABLE ms.leads (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 org_id uuid NOT NULL, merchant_id uuid NOT NULL,
 stage ms.lead_stage NOT NULL DEFAULT 'new',
 outreach_approved boolean NOT NULL DEFAULT false,
 approved_by uuid, approved_at timestamptz,
 created_by uuid NOT NULL,
 FOREIGN KEY (merchant_id,org_id) REFERENCES ms.merchants(id,org_id),
 UNIQUE(org_id,merchant_id), UNIQUE(id,org_id)
);
CREATE TABLE ms.audit_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 org_id uuid NOT NULL,
 actor uuid, action text NOT NULL, entity text NOT NULL,
 entity_id uuid, payload jsonb NOT NULL DEFAULT '{}'::jsonb,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE FUNCTION ms.actor_id() RETURNS uuid LANGUAGE sql STABLE AS $$
 SELECT nullif(current_setting('app.user_id',true),'')::uuid $$;
CREATE FUNCTION ms.active_org() RETURNS uuid LANGUAGE sql STABLE AS $$
 SELECT nullif(current_setting('app.org_id',true),'')::uuid $$;
CREATE FUNCTION ms.has_role(required ms.member_role) RETURNS boolean
 LANGUAGE sql STABLE SECURITY DEFINER SET search_path=ms,pg_temp AS $$
 SELECT EXISTS(SELECT 1 FROM ms.memberships
 WHERE user_id=ms.actor_id() AND org_id=ms.active_org()
   AND (role=required OR role='admin'::ms.member_role)) $$;
CREATE FUNCTION ms.is_member() RETURNS boolean
 LANGUAGE sql STABLE SECURITY DEFINER SET search_path=ms,pg_temp AS $$
 SELECT EXISTS(SELECT 1 FROM ms.memberships
 WHERE user_id=ms.actor_id() AND org_id=ms.active_org()) $$;
CREATE FUNCTION ms.can_write() RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT ms.has_role('analyst'::ms.member_role) $$;

CREATE FUNCTION ms.guard_recommendation() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=ms,pg_temp AS $$
BEGIN
 IF TG_OP='INSERT' THEN
   IF NEW.status <> 'pending_review' OR NEW.created_by <> ms.actor_id() THEN
      RAISE EXCEPTION 'New recommendations must be pending and owned by actor';
   END IF;
   RETURN NEW;
 END IF;
 IF OLD.status='approved' AND
    (NEW.problem IS DISTINCT FROM OLD.problem OR NEW.action IS DISTINCT FROM OLD.action OR NEW.rationale IS DISTINCT FROM OLD.rationale) THEN
      RAISE EXCEPTION 'Approved recommendations are immutable; create a correction';
 END IF;
 IF NOT ms.can_write() AND
    (NEW.problem IS DISTINCT FROM OLD.problem OR NEW.action IS DISTINCT FROM OLD.action OR NEW.rationale IS DISTINCT FROM OLD.rationale) THEN
      RAISE EXCEPTION 'Reviewer cannot rewrite recommendation content';
 END IF;
 IF NEW.status IS DISTINCT FROM OLD.status THEN
   IF NOT ms.has_role('reviewer'::ms.member_role) OR OLD.created_by=ms.actor_id() THEN
      RAISE EXCEPTION 'Independent reviewer required';
   END IF;
   IF OLD.status <> 'pending_review' THEN
      RAISE EXCEPTION 'Only pending recommendations may be reviewed';
   END IF;
   IF NEW.status='approved' AND NOT EXISTS(
      SELECT 1 FROM ms.recommendation_evidence re
      WHERE re.org_id=NEW.org_id AND re.recommendation_id=NEW.id) THEN
      RAISE EXCEPTION 'Source evidence required before approval';
   END IF;
   NEW.reviewer_id:=ms.actor_id();
   NEW.reviewed_at:=now();
 ELSE
   IF NOT ms.can_write() AND NOT ms.has_role('reviewer'::ms.member_role) THEN
      RAISE EXCEPTION 'No edit role';
   END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER recommendations_guard BEFORE INSERT OR UPDATE ON ms.recommendations
 FOR EACH ROW EXECUTE FUNCTION ms.guard_recommendation();

CREATE FUNCTION ms.guard_lead() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=ms,pg_temp AS $$
BEGIN
 IF TG_OP='INSERT' THEN
   IF NEW.created_by <> ms.actor_id() OR NEW.outreach_approved THEN
      RAISE EXCEPTION 'Lead creation cannot preapprove outreach';
   END IF;
   RETURN NEW;
 END IF;
 IF NEW.stage IS DISTINCT FROM OLD.stage AND NOT ms.can_write() THEN
   RAISE EXCEPTION 'Only analyst may change lead stage';
 END IF;
 IF NEW.outreach_approved IS DISTINCT FROM OLD.outreach_approved THEN
   IF NOT ms.has_role('reviewer'::ms.member_role) OR OLD.created_by=ms.actor_id() THEN
      RAISE EXCEPTION 'Independent reviewer required for outreach';
   END IF;
   NEW.approved_by:=CASE WHEN NEW.outreach_approved THEN ms.actor_id() ELSE NULL END;
   NEW.approved_at:=CASE WHEN NEW.outreach_approved THEN now() ELSE NULL END;
 END IF;
 IF NEW.stage IN ('contacted','proposal','won') AND NOT NEW.outreach_approved THEN
   RAISE EXCEPTION 'No outreach without approval';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER leads_guard BEFORE INSERT OR UPDATE ON ms.leads
 FOR EACH ROW EXECUTE FUNCTION ms.guard_lead();

-- Enable RLS on every tenant business table. Do not use a superuser for app queries.
DO $$
DECLARE t text;
BEGIN
 FOREACH t IN ARRAY ARRAY['organizations','memberships','merchants','channels','evidence',
 'assessments','recommendations','recommendation_evidence','leads','audit_events'] LOOP
  EXECUTE format('ALTER TABLE ms.%I ENABLE ROW LEVEL SECURITY',t);
  -- Do not FORCE RLS here: SECURITY DEFINER membership lookups need owner bypass to prevent policy recursion.
 END LOOP;
END $$;
CREATE POLICY org_read ON ms.organizations FOR SELECT
 USING (id=ms.active_org() AND ms.is_member());
CREATE POLICY membership_read ON ms.memberships FOR SELECT
 USING (org_id=ms.active_org() AND ms.is_member());
CREATE POLICY membership_write ON ms.memberships FOR ALL
 USING (org_id=ms.active_org() AND ms.has_role('admin'::ms.member_role))
 WITH CHECK (org_id=ms.active_org() AND ms.has_role('admin'::ms.member_role));

DO $$
DECLARE t text;
BEGIN
 FOREACH t IN ARRAY ARRAY['merchants','channels','evidence','assessments','recommendations',
 'recommendation_evidence','leads','audit_events'] LOOP
  EXECUTE format('CREATE POLICY tenant_read ON ms.%I FOR SELECT USING (org_id=ms.active_org() AND ms.is_member())',t);
 END LOOP;
 FOREACH t IN ARRAY ARRAY['merchants','channels','evidence','assessments',
 'recommendations','recommendation_evidence','leads'] LOOP
  EXECUTE format('CREATE POLICY tenant_insert ON ms.%I FOR INSERT WITH CHECK (org_id=ms.active_org() AND ms.can_write())',t);
 END LOOP;
 FOREACH t IN ARRAY ARRAY['merchants','channels','evidence','assessments','recommendation_evidence'] LOOP
  EXECUTE format('CREATE POLICY tenant_update ON ms.%I FOR UPDATE USING (org_id=ms.active_org() AND ms.can_write()) WITH CHECK (org_id=ms.active_org() AND ms.can_write())',t);
 END LOOP;
 FOREACH t IN ARRAY ARRAY['recommendations','leads'] LOOP
  EXECUTE format('CREATE POLICY tenant_update ON ms.%I FOR UPDATE USING (org_id=ms.active_org() AND (ms.can_write() OR ms.has_role(''reviewer''::ms.member_role))) WITH CHECK (org_id=ms.active_org() AND (ms.can_write() OR ms.has_role(''reviewer''::ms.member_role)))',t);
 END LOOP;
END $$;
-- Audit must be written by a trusted SECURITY DEFINER trigger, not client-supplied.
CREATE FUNCTION ms.audit_change() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=ms,pg_temp AS $
DECLARE record_data jsonb; tenant uuid; ref uuid;
BEGIN
 record_data:=CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
 tenant:=(record_data->>'org_id')::uuid;
 ref:=COALESCE((record_data->>'id')::uuid,(record_data->>'recommendation_id')::uuid);
 INSERT INTO ms.audit_events(org_id,actor,action,entity,entity_id,payload)
 VALUES(tenant,ms.actor_id(),lower(TG_OP),TG_TABLE_NAME,ref,
        jsonb_build_object('at',now(),'table',TG_TABLE_NAME));
 RETURN COALESCE(NEW,OLD);
END $;
DO $ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['merchants','channels','evidence','assessments','recommendations',
 'recommendation_evidence','leads'] LOOP
  EXECUTE format('CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON ms.%I FOR EACH ROW EXECUTE FUNCTION ms.audit_change()', 'audit_'||t, t);
 END LOOP;
END $;
GRANT USAGE ON SCHEMA ms TO merchant_runtime;
GRANT SELECT, INSERT, UPDATE ON ms.merchants,ms.channels,ms.evidence,ms.assessments,ms.recommendations,ms.recommendation_evidence,ms.leads TO merchant_runtime;
GRANT SELECT,INSERT,UPDATE ON ms.memberships TO merchant_runtime;
GRANT SELECT ON ms.organizations TO merchant_runtime;
GRANT SELECT ON ms.audit_events TO merchant_runtime;
GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA ms TO merchant_runtime;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA ms TO merchant_runtime;
COMMIT;
