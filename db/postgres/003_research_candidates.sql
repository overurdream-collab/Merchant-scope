-- 003: Provenance-first research candidates. Do not treat directory listings
-- as verified merchants, contact consent, or evidence of social performance.
BEGIN;

CREATE TABLE ms.research_candidates (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 org_id uuid NOT NULL REFERENCES ms.organizations(id),
 name text NOT NULL CHECK (length(name) BETWEEN 2 AND 200),
 normalized_name text NOT NULL,
 city text NOT NULL CHECK (length(city) BETWEEN 1 AND 100),
 category text,
 source_url text NOT NULL CHECK (source_url ~ '^https://'),
 source_kind text NOT NULL DEFAULT 'public_directory_listing',
 observed_on date NOT NULL CHECK (observed_on <= CURRENT_DATE),
 status text NOT NULL DEFAULT 'unverified'
     CHECK (status IN ('unverified','reviewed','rejected','promoted')),
 review_notes text,
 reviewed_by uuid,
 reviewed_at timestamptz,
 promoted_merchant_id uuid,
 created_by uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(org_id,source_url),
 UNIQUE(id,org_id),
 FOREIGN KEY (promoted_merchant_id,org_id) REFERENCES ms.merchants(id,org_id),
 CHECK ((status IN ('reviewed','rejected','promoted')) = (reviewed_by IS NOT NULL)),
 CHECK ((status='promoted') = (promoted_merchant_id IS NOT NULL))
);
CREATE INDEX candidates_status ON ms.research_candidates(org_id,status,created_at);
ALTER TABLE ms.research_candidates ENABLE ROW LEVEL SECURITY;
CREATE POLICY research_read ON ms.research_candidates FOR SELECT
  USING (org_id=ms.active_org() AND ms.is_member());
CREATE POLICY research_insert ON ms.research_candidates FOR INSERT
  WITH CHECK (org_id=ms.active_org() AND ms.can_write());
CREATE POLICY research_update ON ms.research_candidates FOR UPDATE
  USING (org_id=ms.active_org()
         AND (ms.can_write() OR ms.has_role('reviewer'::ms.member_role)))
  WITH CHECK (org_id=ms.active_org()
         AND (ms.can_write() OR ms.has_role('reviewer'::ms.member_role)));

CREATE FUNCTION ms.guard_research_candidate() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=ms,pg_temp AS $$
BEGIN
 IF TG_OP='INSERT' THEN
   IF NEW.status<>'unverified' OR NEW.created_by<>ms.actor_id()
      OR NEW.reviewed_by IS NOT NULL OR NEW.promoted_merchant_id IS NOT NULL THEN
      RAISE EXCEPTION 'Research candidates must enter unverified and belong to the acting analyst';
   END IF;
   RETURN NEW;
 END IF;

 IF ROW(NEW.name,NEW.normalized_name,NEW.city,NEW.category,NEW.source_url,
        NEW.source_kind,NEW.observed_on,NEW.created_by,NEW.org_id)
    IS DISTINCT FROM
    ROW(OLD.name,OLD.normalized_name,OLD.city,OLD.category,OLD.source_url,
        OLD.source_kind,OLD.observed_on,OLD.created_by,OLD.org_id) THEN
    RAISE EXCEPTION 'Candidate source and identity fields are immutable';
 END IF;
 IF OLD.status='unverified' THEN
    IF NOT ms.has_role('reviewer'::ms.member_role)
       OR OLD.created_by=ms.actor_id()
       OR NEW.status NOT IN ('reviewed','rejected')
       OR NEW.promoted_merchant_id IS NOT NULL THEN
      RAISE EXCEPTION 'Independent reviewer must decide on unverified candidates';
    END IF;
    NEW.reviewed_by:=ms.actor_id();
    NEW.reviewed_at:=now();
 ELSIF OLD.status='reviewed' AND NEW.status='promoted' THEN
    IF NOT ms.can_write() OR NEW.promoted_merchant_id IS NULL THEN
      RAISE EXCEPTION 'Only an analyst can promote a reviewed candidate';
    END IF;
    NEW.reviewed_by:=OLD.reviewed_by;
    NEW.reviewed_at:=OLD.reviewed_at;
    NEW.review_notes:=OLD.review_notes;
 ELSE
    RAISE EXCEPTION 'Finalized candidate decisions are immutable';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER candidate_guard BEFORE INSERT OR UPDATE ON ms.research_candidates
 FOR EACH ROW EXECUTE FUNCTION ms.guard_research_candidate();
CREATE TRIGGER audit_candidates AFTER INSERT OR UPDATE ON ms.research_candidates
 FOR EACH ROW EXECUTE FUNCTION ms.audit_change();

GRANT SELECT,INSERT,UPDATE ON ms.research_candidates TO merchant_runtime;
COMMIT;
