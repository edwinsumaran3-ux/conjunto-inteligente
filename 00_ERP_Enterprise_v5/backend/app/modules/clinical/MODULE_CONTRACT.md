# Clinical module contract

Status: IMPLEMENTED CORE

The module owns tenant-scoped patient identity, encounters, diagnoses, medication orders and clinical notes. Clinical writes require an authenticated tenant context and use the shared idempotency mechanism for patient/encounter creation.

Lifecycle: `OPEN -> IN_PROGRESS -> COMPLETED`; `OPEN -> CANCELLED`; `IN_PROGRESS -> CANCELLED`. Terminal states cannot transition.

Clinical data is not exposed through unrestricted search or generated SQL. Medication and diagnosis inputs are validated domain objects. Authorization, audit and tenant isolation remain platform responsibilities and are enforced at the API/database boundaries.

Not claimed here: FHIR interoperability, national clinical coding certification, e-prescribing regulatory certification, external laboratory/HL7 integration, biometric identification, or production PostgreSQL verification.
