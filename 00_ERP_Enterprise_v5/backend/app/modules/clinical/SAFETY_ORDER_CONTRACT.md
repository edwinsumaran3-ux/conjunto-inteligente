# Clinical Safety & Orders — Phase 37

## Scope
Allergy history, immutable vital observations, laboratory orders/results, imaging orders/reports, care plans, and deterministic medication-safety checks.

## Safety boundary
- Allergy and vital history are append-only at the database layer.
- Tenant isolation uses RLS + FORCE RLS and composite tenant foreign keys.
- Medication safety returns deterministic conflicts only: active allergy exact code/name match and duplicate active medication code. It does **not** diagnose, prescribe, or override clinician judgment.
- Clinical Decision Support is advisory and must remain separately authorized/audited; no autonomous diagnosis or treatment is implemented here.
- External LIS/RIS/PACS/FHIR/HL7 integrations are not claimed until real protocol and interoperability tests are executed.
- Real PostgreSQL/Redis/Docker execution remains an environment verification boundary when those services are unavailable.
