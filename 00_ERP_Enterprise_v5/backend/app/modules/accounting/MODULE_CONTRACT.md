# Accounting — IMPLEMENTED FINANCIAL KERNEL

Implemented in this phase: accounting periods, chart of accounts, immutable journal entries/lines, atomic posting, tenant isolation, per-currency balance validation, compensating-entry rule, transactional outbox emission.

Not implemented here: tax/fiscal certification, country-specific e-invoicing, bank reconciliation, payroll accounting, consolidation, FX revaluation, period closing automation beyond explicit close, or external payment settlement. Those remain blocked until their own invariants and infrastructure tests exist.

Forbidden: floating-point money, mutation of posted journals, cross-tenant references, automatic retries of non-idempotent financial mutations, silent fallback on missing accounting data.
