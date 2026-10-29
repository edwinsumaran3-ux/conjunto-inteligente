-- 005: núcleo contable (libro diario con cadena de hash inmutable), documentos financieros, pagos y tesorería.
-- El código usa estas tablas y funciones (post_journal, allocate_document_number, ...) pero ninguna migración las definía.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE OR REPLACE FUNCTION app_tenant() RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT NULLIF(current_setting('app.current_tenant_id', true), '')::uuid $$;

CREATE TABLE IF NOT EXISTS chart_accounts(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, company_id uuid, code text NOT NULL, name text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE')),
  normal_side text NOT NULL CHECK (normal_side IN ('D','C')), parent_id uuid REFERENCES chart_accounts(id), active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,code));

CREATE TABLE IF NOT EXISTS accounting_periods(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, company_id uuid, code text NOT NULL, starts_on date NOT NULL, ends_on date NOT NULL,
  status text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED','LOCKED')), closed_at timestamptz, closed_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(), CHECK (ends_on >= starts_on), UNIQUE(tenant_id,code));

CREATE TABLE IF NOT EXISTS accounting_posting_profiles(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, company_id uuid, operation text NOT NULL, currency text NOT NULL DEFAULT 'COP',
  debit_account_id uuid REFERENCES chart_accounts(id), credit_account_id uuid REFERENCES chart_accounts(id),
  tax_debit_account_id uuid REFERENCES chart_accounts(id), tax_credit_account_id uuid REFERENCES chart_accounts(id),
  active boolean NOT NULL DEFAULT true, effective_from date NOT NULL DEFAULT '2000-01-01', effective_to date, created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS ix_posting_profiles_lookup ON accounting_posting_profiles(tenant_id,operation,currency,effective_from DESC);

CREATE TABLE IF NOT EXISTS journal_entries(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, company_id uuid, period_id uuid NOT NULL REFERENCES accounting_periods(id),
  seq bigint NOT NULL, entry_date date NOT NULL, description text, source_type text, source_id uuid,
  status text NOT NULL DEFAULT 'POSTED' CHECK (status IN ('POSTED','REVERSED')), posted_by uuid, prev_hash text NOT NULL, entry_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,seq));
CREATE TABLE IF NOT EXISTS journal_lines(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, journal_entry_id uuid NOT NULL REFERENCES journal_entries(id),
  line_no integer NOT NULL, account_id uuid NOT NULL REFERENCES chart_accounts(id), debit numeric(20,4) NOT NULL DEFAULT 0, credit numeric(20,4) NOT NULL DEFAULT 0,
  currency text NOT NULL DEFAULT 'COP', description text,
  CHECK (debit >= 0 AND credit >= 0 AND NOT (debit > 0 AND credit > 0)), UNIQUE(journal_entry_id,line_no));
CREATE INDEX IF NOT EXISTS ix_journal_lines_entry ON journal_lines(tenant_id,journal_entry_id);
CREATE INDEX IF NOT EXISTS ix_journal_lines_account ON journal_lines(tenant_id,account_id);

CREATE OR REPLACE FUNCTION journal_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'journal is immutable: DELETE not allowed on %', TG_TABLE_NAME; END IF;
  IF TG_TABLE_NAME = 'journal_entries' THEN   -- único cambio permitido: status (POSTED -> REVERSED)
    IF NEW.status IS DISTINCT FROM OLD.status AND NEW.seq = OLD.seq AND NEW.entry_hash = OLD.entry_hash AND NEW.prev_hash = OLD.prev_hash
       AND NEW.entry_date = OLD.entry_date AND NEW.tenant_id = OLD.tenant_id THEN RETURN NEW; END IF;
  END IF;
  RAISE EXCEPTION 'journal is immutable: UPDATE not allowed on %', TG_TABLE_NAME;
END $$;
DROP TRIGGER IF EXISTS journal_entries_immutable ON journal_entries; CREATE TRIGGER journal_entries_immutable BEFORE UPDATE OR DELETE ON journal_entries FOR EACH ROW EXECUTE FUNCTION journal_immutable();
DROP TRIGGER IF EXISTS journal_lines_immutable ON journal_lines; CREATE TRIGGER journal_lines_immutable BEFORE UPDATE OR DELETE ON journal_lines FOR EACH ROW EXECUTE FUNCTION journal_immutable();

CREATE TABLE IF NOT EXISTS document_sequences(
  tenant_id uuid NOT NULL, company_id uuid NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000', document_type text NOT NULL, series text NOT NULL,
  next_value bigint NOT NULL DEFAULT 1 CHECK (next_value >= 1), padding integer NOT NULL DEFAULT 8, PRIMARY KEY(tenant_id,company_id,document_type,series));

CREATE TABLE IF NOT EXISTS financial_documents(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, company_id uuid, partner_id uuid, direction text NOT NULL CHECK (direction IN ('AR','AP')),
  document_type text NOT NULL, series text NOT NULL, number text NOT NULL, issue_date date NOT NULL, due_date date, currency text NOT NULL DEFAULT 'COP',
  exchange_rate numeric(18,8) NOT NULL DEFAULT 1, subtotal numeric(20,4) NOT NULL DEFAULT 0, tax_amount numeric(20,4) NOT NULL DEFAULT 0,
  withholding_amount numeric(20,4) NOT NULL DEFAULT 0, total_amount numeric(20,4) NOT NULL DEFAULT 0, balance_amount numeric(20,4) NOT NULL DEFAULT 0,
  lifecycle_status text NOT NULL DEFAULT 'DRAFT' CHECK (lifecycle_status IN ('DRAFT','CALCULATED','READY','SUBMITTING','VALIDATED','REJECTED','VOIDED','CANCELLED')),
  dian_status text NOT NULL DEFAULT 'NOT_REQUIRED', journal_entry_id uuid REFERENCES journal_entries(id), original_document_id uuid REFERENCES financial_documents(id),
  source_type text, source_id uuid, status_reason text, issued_at timestamptz, created_by uuid, created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,document_type,series,number));
CREATE TABLE IF NOT EXISTS financial_document_lines(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, financial_document_id uuid NOT NULL REFERENCES financial_documents(id) ON DELETE CASCADE,
  line_no integer NOT NULL, description text, quantity numeric(20,6) NOT NULL DEFAULT 1, unit_price numeric(20,4) NOT NULL DEFAULT 0, account_id uuid REFERENCES chart_accounts(id),
  line_subtotal numeric(20,4) NOT NULL DEFAULT 0, tax_amount numeric(20,4) NOT NULL DEFAULT 0, UNIQUE(financial_document_id,line_no));
CREATE TABLE IF NOT EXISTS financial_document_taxes(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, financial_document_id uuid NOT NULL REFERENCES financial_documents(id) ON DELETE CASCADE,
  line_id uuid REFERENCES financial_document_lines(id) ON DELETE CASCADE, tax_code text NOT NULL, rate numeric(9,4) NOT NULL, base_amount numeric(20,4) NOT NULL, tax_amount numeric(20,4) NOT NULL);

CREATE TABLE IF NOT EXISTS receivable_payable(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, financial_document_id uuid NOT NULL REFERENCES financial_documents(id),
  original_amount numeric(20,4) NOT NULL CHECK (original_amount >= 0), outstanding_amount numeric(20,4) NOT NULL CHECK (outstanding_amount >= 0), currency text NOT NULL,
  status text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','PARTIALLY_SETTLED','SETTLED','CANCELLED')), created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id,financial_document_id));

CREATE TABLE IF NOT EXISTS treasury_accounts(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, company_id uuid, name text NOT NULL, currency text NOT NULL DEFAULT 'COP',
  ledger_account_id uuid REFERENCES chart_accounts(id), active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS payments(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, company_id uuid, partner_id uuid, direction text NOT NULL CHECK (direction IN ('RECEIPT','DISBURSEMENT')),
  payment_date date NOT NULL, amount numeric(20,4) NOT NULL CHECK (amount > 0), currency text NOT NULL DEFAULT 'COP', treasury_account_id uuid REFERENCES treasury_accounts(id),
  external_reference text, status text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','POSTED','REVERSED','CANCELLED')), idempotency_key text, journal_entry_id uuid REFERENCES journal_entries(id),
  created_by uuid, posted_at timestamptz, reversed_at timestamptz, created_at timestamptz NOT NULL DEFAULT now());
CREATE UNIQUE INDEX IF NOT EXISTS ux_payments_idem ON payments(tenant_id,idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE TABLE IF NOT EXISTS payment_allocations(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, payment_id uuid NOT NULL REFERENCES payments(id), receivable_payable_id uuid NOT NULL REFERENCES receivable_payable(id),
  amount numeric(20,4) NOT NULL CHECK (amount > 0), reversed_at timestamptz, reversed_by_payment_id uuid, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS payment_reversals(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, payment_id uuid NOT NULL REFERENCES payments(id), reversal_payment_id uuid NOT NULL REFERENCES payments(id),
  reason text, created_by uuid, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,payment_id));
CREATE TABLE IF NOT EXISTS treasury_movements(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, treasury_account_id uuid NOT NULL REFERENCES treasury_accounts(id), movement_date date NOT NULL,
  direction text NOT NULL CHECK (direction IN ('IN','OUT')), amount numeric(20,4) NOT NULL CHECK (amount > 0), currency text NOT NULL, reference text,
  payment_id uuid REFERENCES payments(id), journal_entry_id uuid REFERENCES journal_entries(id), status text NOT NULL DEFAULT 'POSTED', created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS tax_rules(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, company_id uuid, code text NOT NULL, rate numeric(9,4) NOT NULL, rounding_scale integer NOT NULL DEFAULT 2,
  effective_from date NOT NULL DEFAULT '2000-01-01', effective_to date, active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now());

-- Soporte de procesos ejecutables (cierre anual, depreciación, provisiones)
CREATE TABLE IF NOT EXISTS fixed_assets(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, company_id uuid, name text NOT NULL, acquisition_cost numeric(20,4) NOT NULL CHECK (acquisition_cost >= 0),
  salvage_value numeric(20,4) NOT NULL DEFAULT 0, useful_life_months integer NOT NULL CHECK (useful_life_months > 0), in_service_on date NOT NULL,
  accumulated_depreciation numeric(20,4) NOT NULL DEFAULT 0, active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS asset_depreciation_runs(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, company_id uuid, run_year integer NOT NULL, run_month integer NOT NULL CHECK (run_month BETWEEN 1 AND 12),
  total_amount numeric(20,4) NOT NULL, journal_entry_id uuid REFERENCES journal_entries(id), created_by uuid, created_at timestamptz NOT NULL DEFAULT now());
CREATE UNIQUE INDEX IF NOT EXISTS ux_depr_run ON asset_depreciation_runs(tenant_id,coalesce(company_id,'00000000-0000-0000-0000-000000000000'),run_year,run_month);
CREATE TABLE IF NOT EXISTS provisions(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, company_id uuid, name text NOT NULL, balance numeric(20,4) NOT NULL DEFAULT 0 CHECK (balance >= 0), created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS provision_movements(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, provision_id uuid NOT NULL REFERENCES provisions(id), movement_type text NOT NULL CHECK (movement_type IN ('ACCRUE','RELEASE','UTILIZE')),
  amount numeric(20,4) NOT NULL CHECK (amount > 0), journal_entry_id uuid REFERENCES journal_entries(id), created_by uuid, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS annual_close_runs(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, company_id uuid, fiscal_year integer NOT NULL, net_result numeric(20,4) NOT NULL,
  journal_entry_id uuid REFERENCES journal_entries(id), status text NOT NULL DEFAULT 'COMPLETED', created_by uuid, created_at timestamptz NOT NULL DEFAULT now());
CREATE UNIQUE INDEX IF NOT EXISTS ux_annual_close ON annual_close_runs(tenant_id,coalesce(company_id,'00000000-0000-0000-0000-000000000000'),fiscal_year);

-- ===================== FUNCIONES =====================
CREATE OR REPLACE FUNCTION assert_tenant(p_t uuid) RETURNS void LANGUAGE plpgsql AS $$
BEGIN IF p_t IS DISTINCT FROM app_tenant() THEN RAISE EXCEPTION 'tenant mismatch: argument does not match app.current_tenant_id' USING ERRCODE='42501'; END IF; END $$;

CREATE OR REPLACE FUNCTION journal_entry_hash(p_prev text, p_t uuid, p_seq bigint, p_date date, p_desc text, p_src_type text, p_src uuid, p_lines jsonb) RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT encode(digest(coalesce(p_prev,'')||'|'||p_t::text||'|'||p_seq::text||'|'||p_date::text||'|'||coalesce(p_desc,'')||'|'||coalesce(p_src_type,'')||'|'||coalesce(p_src::text,'')||'|'||p_lines::text,'sha256'),'hex') $$;

CREATE OR REPLACE FUNCTION post_journal(p_t uuid, p_period uuid, p_date date, p_desc text, p_src_type text, p_src uuid, p_user uuid, p_lines jsonb) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE per accounting_periods; v_seq bigint; v_prev text; v_id uuid := gen_random_uuid(); v_debit numeric := 0; v_credit numeric := 0; l jsonb; n int := 0; v_norm jsonb := '[]'::jsonb; v_acc chart_accounts;
BEGIN
  PERFORM assert_tenant(p_t);
  SELECT * INTO per FROM accounting_periods WHERE tenant_id=p_t AND id=p_period FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'accounting period not found'; END IF;
  IF per.status <> 'OPEN' THEN RAISE EXCEPTION 'accounting period % is %', per.code, per.status; END IF;
  IF p_date NOT BETWEEN per.starts_on AND per.ends_on THEN RAISE EXCEPTION 'entry date % outside period %', p_date, per.code; END IF;
  IF p_lines IS NULL OR jsonb_typeof(p_lines) <> 'array' OR jsonb_array_length(p_lines) < 2 THEN RAISE EXCEPTION 'journal needs at least two lines'; END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended('journal:'||p_t::text, 0));
  FOR l IN SELECT * FROM jsonb_array_elements(p_lines) LOOP
    n := n + 1;
    SELECT * INTO v_acc FROM chart_accounts WHERE tenant_id=p_t AND id=(l->>'account_id')::uuid;
    IF NOT FOUND OR NOT v_acc.active THEN RAISE EXCEPTION 'account % not found or inactive', l->>'account_id'; END IF;
    v_debit := v_debit + coalesce((l->>'debit')::numeric,0); v_credit := v_credit + coalesce((l->>'credit')::numeric,0);
    v_norm := v_norm || jsonb_build_array(jsonb_build_object('n',n,'a',l->>'account_id','d',coalesce((l->>'debit')::numeric,0)::numeric(20,4)::text,'c',coalesce((l->>'credit')::numeric,0)::numeric(20,4)::text));
  END LOOP;
  IF v_debit <> v_credit OR v_debit = 0 THEN RAISE EXCEPTION 'journal not balanced: debit % credit %', v_debit, v_credit USING ERRCODE='23514'; END IF;
  SELECT coalesce(max(seq),0)+1 INTO v_seq FROM journal_entries WHERE tenant_id=p_t;
  SELECT entry_hash INTO v_prev FROM journal_entries WHERE tenant_id=p_t AND seq=v_seq-1;
  v_prev := coalesce(v_prev, repeat('0',64));
  INSERT INTO journal_entries(id,tenant_id,company_id,period_id,seq,entry_date,description,source_type,source_id,posted_by,prev_hash,entry_hash)
    VALUES (v_id,p_t,per.company_id,p_period,v_seq,p_date,p_desc,p_src_type,p_src,p_user,v_prev,journal_entry_hash(v_prev,p_t,v_seq,p_date,p_desc,p_src_type,p_src,v_norm));
  n := 0;
  FOR l IN SELECT * FROM jsonb_array_elements(p_lines) LOOP
    n := n + 1;
    INSERT INTO journal_lines(tenant_id,journal_entry_id,line_no,account_id,debit,credit,currency,description)
      VALUES (p_t,v_id,n,(l->>'account_id')::uuid,coalesce((l->>'debit')::numeric,0),coalesce((l->>'credit')::numeric,0),coalesce(l->>'currency','COP'),l->>'description');
  END LOOP;
  RETURN v_id;
END $$;

CREATE OR REPLACE FUNCTION validate_journal_hash_chain(p_t uuid) RETURNS boolean LANGUAGE plpgsql AS $$
DECLARE e journal_entries; v_prev text := repeat('0',64); v_norm jsonb; v_expect bigint := 1; v_d numeric; v_c numeric;
BEGIN
  PERFORM assert_tenant(p_t);
  FOR e IN SELECT * FROM journal_entries WHERE tenant_id=p_t ORDER BY seq LOOP
    IF e.seq <> v_expect THEN RAISE EXCEPTION 'journal sequence gap at %', v_expect USING ERRCODE='XX001'; END IF;
    SELECT jsonb_agg(jsonb_build_object('n',line_no,'a',account_id::text,'d',debit::text,'c',credit::text) ORDER BY line_no), sum(debit), sum(credit)
      INTO v_norm, v_d, v_c FROM journal_lines WHERE tenant_id=p_t AND journal_entry_id=e.id;
    IF v_d IS DISTINCT FROM v_c THEN RAISE EXCEPTION 'journal entry % is not balanced', e.id USING ERRCODE='XX001'; END IF;
    IF e.prev_hash <> v_prev OR e.entry_hash <> journal_entry_hash(v_prev,p_t,e.seq,e.entry_date,e.description,e.source_type,e.source_id,
         (SELECT jsonb_agg(jsonb_build_object('n',(x->>'n')::int,'a',x->>'a','d',(x->>'d')::numeric::text,'c',(x->>'c')::numeric::text)) FROM jsonb_array_elements(v_norm) x)) THEN
      RAISE EXCEPTION 'journal hash chain broken at seq %', e.seq USING ERRCODE='XX001'; END IF;
    v_prev := e.entry_hash; v_expect := v_expect + 1;
  END LOOP;
  RETURN true;
END $$;

CREATE OR REPLACE FUNCTION allocate_document_number(p_t uuid, p_company uuid, p_type text, p_series text) RETURNS text LANGUAGE plpgsql AS $$
DECLARE r document_sequences;
BEGIN
  PERFORM assert_tenant(p_t);
  UPDATE document_sequences SET next_value = next_value + 1
   WHERE tenant_id=p_t AND company_id=coalesce(p_company,'00000000-0000-0000-0000-000000000000') AND document_type=p_type AND series=p_series
   RETURNING * INTO r;
  IF NOT FOUND THEN RETURN NULL; END IF;
  RETURN lpad((r.next_value-1)::text, r.padding, '0');
END $$;

CREATE OR REPLACE FUNCTION transition_financial_document(p_t uuid, p_doc uuid, p_target text, p_user uuid, p_reason text) RETURNS void LANGUAGE plpgsql AS $$
DECLARE d financial_documents;
BEGIN
  PERFORM assert_tenant(p_t);
  SELECT * INTO d FROM financial_documents WHERE tenant_id=p_t AND id=p_doc FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'financial document not found'; END IF;
  -- Misma máquina de estados que backend/app/modules/billing/domain/invoice_lifecycle.py
  IF NOT ( (d.lifecycle_status='DRAFT' AND p_target IN ('CALCULATED','CANCELLED'))
        OR (d.lifecycle_status='CALCULATED' AND p_target IN ('READY','DRAFT','CANCELLED'))
        OR (d.lifecycle_status='READY' AND p_target IN ('SUBMITTING','CANCELLED'))
        OR (d.lifecycle_status='SUBMITTING' AND p_target IN ('VALIDATED','REJECTED'))
        OR (d.lifecycle_status='REJECTED' AND p_target IN ('READY','CANCELLED'))
        OR (d.lifecycle_status='VALIDATED' AND p_target='VOIDED') ) THEN
    RAISE EXCEPTION 'invalid invoice transition % -> %', d.lifecycle_status, p_target USING ERRCODE='23514'; END IF;
  IF p_target='VOIDED' AND d.journal_entry_id IS NOT NULL THEN
    RAISE EXCEPTION 'posted document cannot be voided; issue a credit note (reversal)' USING ERRCODE='23514'; END IF;
  UPDATE financial_documents SET lifecycle_status=p_target, status_reason=p_reason, updated_at=now() WHERE id=p_doc;
END $$;

CREATE OR REPLACE FUNCTION reverse_payment_allocations(p_t uuid, p_payment uuid, p_reversal uuid) RETURNS void LANGUAGE plpgsql AS $$
DECLARE a payment_allocations;
BEGIN
  PERFORM assert_tenant(p_t);
  FOR a IN SELECT * FROM payment_allocations WHERE tenant_id=p_t AND payment_id=p_payment AND reversed_at IS NULL FOR UPDATE LOOP
    UPDATE receivable_payable SET outstanding_amount = outstanding_amount + a.amount,
      status = CASE WHEN outstanding_amount + a.amount >= original_amount THEN 'OPEN' ELSE 'PARTIALLY_SETTLED' END
     WHERE tenant_id=p_t AND id=a.receivable_payable_id;
    UPDATE payment_allocations SET reversed_at=now(), reversed_by_payment_id=p_reversal WHERE id=a.id;
  END LOOP;
END $$;

CREATE OR REPLACE FUNCTION _profile_for(p_t uuid, p_company uuid, p_op text, p_date date) RETURNS accounting_posting_profiles LANGUAGE plpgsql AS $$
DECLARE r accounting_posting_profiles;
BEGIN
  SELECT * INTO r FROM accounting_posting_profiles WHERE tenant_id=p_t AND company_id IS NOT DISTINCT FROM p_company AND operation=p_op AND active
     AND effective_from<=p_date AND (effective_to IS NULL OR effective_to>=p_date) ORDER BY effective_from DESC LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'posting profile not configured: %', p_op; END IF;
  RETURN r;
END $$;

CREATE OR REPLACE FUNCTION _open_period(p_t uuid, p_company uuid, p_date date) RETURNS uuid LANGUAGE sql AS $$
  SELECT id FROM accounting_periods WHERE tenant_id=p_t AND company_id IS NOT DISTINCT FROM p_company AND status='OPEN' AND p_date BETWEEN starts_on AND ends_on LIMIT 1 $$;

CREATE OR REPLACE FUNCTION run_asset_depreciation(p_t uuid, p_company uuid, p_year int, p_month int, p_user uuid) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE v_total numeric := 0; v_end date := (make_date(p_year,p_month,1) + interval '1 month - 1 day')::date; prof accounting_posting_profiles; v_run uuid := gen_random_uuid(); v_je uuid; per uuid; a fixed_assets; v_dep numeric;
BEGIN
  PERFORM assert_tenant(p_t);
  IF EXISTS (SELECT 1 FROM asset_depreciation_runs WHERE tenant_id=p_t AND company_id IS NOT DISTINCT FROM p_company AND run_year=p_year AND run_month=p_month) THEN
    RAISE EXCEPTION 'depreciation already executed for %-%', p_year, p_month USING ERRCODE='23505'; END IF;
  FOR a IN SELECT * FROM fixed_assets WHERE tenant_id=p_t AND company_id IS NOT DISTINCT FROM p_company AND active AND in_service_on <= v_end FOR UPDATE LOOP
    v_dep := least(round((a.acquisition_cost - a.salvage_value) / a.useful_life_months, 4), a.acquisition_cost - a.salvage_value - a.accumulated_depreciation);
    IF v_dep > 0 THEN UPDATE fixed_assets SET accumulated_depreciation = accumulated_depreciation + v_dep WHERE id=a.id; v_total := v_total + v_dep; END IF;
  END LOOP;
  IF v_total > 0 THEN
    prof := _profile_for(p_t, p_company, 'DEPRECIATION', v_end); per := _open_period(p_t, p_company, v_end);
    IF per IS NULL THEN RAISE EXCEPTION 'no open accounting period for %', v_end; END IF;
    v_je := post_journal(p_t, per, v_end, format('Depreciation %s-%s', p_year, p_month), 'DEPRECIATION', v_run, p_user,
      jsonb_build_array(jsonb_build_object('account_id',prof.debit_account_id,'debit',v_total,'credit',0), jsonb_build_object('account_id',prof.credit_account_id,'debit',0,'credit',v_total)));
  END IF;
  INSERT INTO asset_depreciation_runs(id,tenant_id,company_id,run_year,run_month,total_amount,journal_entry_id,created_by) VALUES (v_run,p_t,p_company,p_year,p_month,v_total,v_je,p_user);
  RETURN v_run;
END $$;

CREATE OR REPLACE FUNCTION post_provision_movement(p_t uuid, p_prov uuid, p_kind text, p_amount numeric, p_user uuid) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE pr provisions; prof accounting_posting_profiles; v_id uuid := gen_random_uuid(); v_je uuid; per uuid; v_op text; v_date date := current_date; d uuid; c uuid;
BEGIN
  PERFORM assert_tenant(p_t);
  IF p_kind NOT IN ('ACCRUE','RELEASE','UTILIZE') THEN RAISE EXCEPTION 'invalid provision movement %', p_kind; END IF;
  SELECT * INTO pr FROM provisions WHERE tenant_id=p_t AND id=p_prov FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'provision not found'; END IF;
  IF p_kind <> 'ACCRUE' AND p_amount > pr.balance THEN RAISE EXCEPTION 'movement exceeds provision balance' USING ERRCODE='23514'; END IF;
  v_op := 'PROVISION_' || p_kind; prof := _profile_for(p_t, pr.company_id, v_op, v_date); per := _open_period(p_t, pr.company_id, v_date);
  IF per IS NULL THEN RAISE EXCEPTION 'no open accounting period for %', v_date; END IF;
  v_je := post_journal(p_t, per, v_date, format('Provision %s %s', p_kind, pr.name), 'PROVISION', v_id, p_user,
    jsonb_build_array(jsonb_build_object('account_id',prof.debit_account_id,'debit',p_amount,'credit',0), jsonb_build_object('account_id',prof.credit_account_id,'debit',0,'credit',p_amount)));
  UPDATE provisions SET balance = balance + CASE WHEN p_kind='ACCRUE' THEN p_amount ELSE -p_amount END WHERE id=p_prov;
  INSERT INTO provision_movements(id,tenant_id,provision_id,movement_type,amount,journal_entry_id,created_by) VALUES (v_id,p_t,p_prov,p_kind,p_amount,v_je,p_user);
  RETURN v_id;
END $$;

CREATE OR REPLACE FUNCTION execute_annual_close(p_t uuid, p_company uuid, p_year int, p_user uuid) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE v_start date := make_date(p_year,1,1); v_end date := make_date(p_year,12,31); prof accounting_posting_profiles; per uuid; v_je uuid; v_run uuid := gen_random_uuid();
        v_lines jsonb := '[]'::jsonb; r record; v_net numeric := 0;
BEGIN
  PERFORM assert_tenant(p_t);
  IF EXISTS (SELECT 1 FROM annual_close_runs WHERE tenant_id=p_t AND company_id IS NOT DISTINCT FROM p_company AND fiscal_year=p_year) THEN RAISE EXCEPTION 'fiscal year % already closed', p_year USING ERRCODE='23505'; END IF;
  IF EXISTS (SELECT 1 FROM accounting_periods WHERE tenant_id=p_t AND company_id IS NOT DISTINCT FROM p_company AND ends_on BETWEEN v_start AND v_end AND status='OPEN' AND ends_on < v_end) THEN
    RAISE EXCEPTION 'all periods before December must be closed first' USING ERRCODE='23514'; END IF;
  prof := _profile_for(p_t, p_company, 'ANNUAL_CLOSE', v_end); per := _open_period(p_t, p_company, v_end);
  IF per IS NULL THEN RAISE EXCEPTION 'no open accounting period for %', v_end; END IF;
  FOR r IN SELECT a.id, a.kind, sum(l.debit) d, sum(l.credit) c FROM journal_lines l JOIN journal_entries e ON e.id=l.journal_entry_id AND e.tenant_id=l.tenant_id
             JOIN chart_accounts a ON a.id=l.account_id WHERE l.tenant_id=p_t AND e.company_id IS NOT DISTINCT FROM p_company AND e.entry_date BETWEEN v_start AND v_end
              AND a.kind IN ('REVENUE','EXPENSE') GROUP BY a.id, a.kind HAVING sum(l.debit) <> sum(l.credit) LOOP
    v_lines := v_lines || jsonb_build_array(jsonb_build_object('account_id',r.id,'debit',greatest(r.c-r.d,0),'credit',greatest(r.d-r.c,0)));
    v_net := v_net + (r.c - r.d);
  END LOOP;
  IF jsonb_array_length(v_lines) > 0 THEN
    v_lines := v_lines || jsonb_build_array(jsonb_build_object('account_id', prof.credit_account_id, 'debit', greatest(-v_net,0), 'credit', greatest(v_net,0)));
    v_je := post_journal(p_t, per, v_end, 'Annual close '||p_year, 'ANNUAL_CLOSE', v_run, p_user, v_lines);
  END IF;
  INSERT INTO annual_close_runs(id,tenant_id,company_id,fiscal_year,net_result,journal_entry_id,created_by) VALUES (v_run,p_t,p_company,p_year,v_net,v_je,p_user);
  RETURN v_run;
END $$;

CREATE OR REPLACE FUNCTION complete_annual_close(p_t uuid, p_company uuid, p_year int, p_user uuid) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE v_run uuid;
BEGIN
  PERFORM assert_tenant(p_t);
  SELECT id INTO v_run FROM annual_close_runs WHERE tenant_id=p_t AND company_id IS NOT DISTINCT FROM p_company AND fiscal_year=p_year;
  IF v_run IS NULL THEN v_run := execute_annual_close(p_t,p_company,p_year,p_user); END IF;
  UPDATE accounting_periods SET status='LOCKED', closed_at=coalesce(closed_at,now()), closed_by=coalesce(closed_by,p_user)
   WHERE tenant_id=p_t AND company_id IS NOT DISTINCT FROM p_company AND ends_on BETWEEN make_date(p_year,1,1) AND make_date(p_year,12,31);
  RETURN v_run;
END $$;

-- RLS fail-closed por tenant
DO $$ DECLARE t text; BEGIN
  FOR t IN SELECT unnest(ARRAY['chart_accounts','accounting_periods','accounting_posting_profiles','journal_entries','journal_lines','document_sequences','financial_documents',
    'financial_document_lines','financial_document_taxes','receivable_payable','treasury_accounts','payments','payment_allocations','payment_reversals','treasury_movements',
    'tax_rules','fixed_assets','asset_depreciation_runs','provisions','provision_movements','annual_close_runs']) LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t); EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS %I ON %I', t||'_tenant_isolation', t);
    EXECUTE format('CREATE POLICY %I ON %I USING (tenant_id = app_tenant()) WITH CHECK (tenant_id = app_tenant())', t||'_tenant_isolation', t);
  END LOOP; END $$;
