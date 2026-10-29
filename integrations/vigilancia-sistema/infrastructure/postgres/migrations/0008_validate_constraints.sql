-- 0008 · Valida las constraints NOT VALID sobre los datos históricos.
-- Si hay filas antiguas que las violan NO se aborta el despliegue: se emite un
-- WARNING con la constraint afectada para que se sanee y se valide a mano
-- (ALTER TABLE ... VALIDATE CONSTRAINT ...).
DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN
    SELECT c.conrelid::regclass AS tbl, c.conname
    FROM pg_constraint c
    WHERE NOT c.convalidated AND c.connamespace = 'public'::regnamespace
      AND (c.conname LIKE 'ck\_%' OR c.conname LIKE 'fk\_%')
  LOOP
    BEGIN
      EXECUTE format('ALTER TABLE %s VALIDATE CONSTRAINT %I', r.tbl, r.conname);
    EXCEPTION WHEN OTHERS THEN
      RAISE WARNING 'constraint % en % no valida datos historicos: %', r.conname, r.tbl, SQLERRM;
    END;
  END LOOP;
END
$$;
