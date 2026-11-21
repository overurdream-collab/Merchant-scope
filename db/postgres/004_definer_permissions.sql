-- 004: Harden SECURITY DEFINER execution grants discovered by CI.
-- Apply after 001-003; also safe for existing databases using the same schema.
BEGIN;
DO $$
DECLARE fn record;
BEGIN
  FOR fn IN
    SELECT p.oid::regprocedure AS signature
    FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
    WHERE n.nspname='ms' AND p.prosecdef
  LOOP
    EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC, merchant_runtime', fn.signature);
  END LOOP;
END $$;
-- RLS policies invoke these two narrow membership predicates as merchant_runtime.
-- Trigger functions and authentication lookups must not be directly callable by runtime.
GRANT EXECUTE ON FUNCTION ms.has_role(ms.member_role), ms.is_member() TO merchant_runtime;
COMMIT;
