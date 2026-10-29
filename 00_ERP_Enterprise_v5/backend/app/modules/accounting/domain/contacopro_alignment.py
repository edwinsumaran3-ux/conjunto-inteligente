"""Canonical mapping from CONTA-COPRO accounting concepts into the ERP.

CONTA-COPRO is treated as a reference model. Its obsolete legacy terminology is
not imported into runtime. Colombian/DIAN identifiers and the ERP's tenant/RLS
invariants remain authoritative.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum


class ContaModel(StrEnum):
    ACCOUNTING_PERIOD = "AccountingPeriod"
    JOURNAL_ENTRY = "JournalEntry"
    JOURNAL_LINE = "JournalLine"
    FINANCIAL_DOCUMENT = "FinancialDocument"
    TREASURY_ACCOUNT = "TreasuryAccount"
    TREASURY_MOVEMENT = "TreasuryMovement"
    FIXED_ASSET = "FixedAsset"
    DEPRECIATION_RUN = "DepreciationRun"
    PROVISION = "Provision"
    ANNUAL_CLOSING_RUN = "AnnualClosingRun"
    TAX_DETERMINATION = "TaxDetermination"
    DIAN_SUBMISSION = "DianSubmission"
    INTEGRATION_MESSAGE = "IntegrationMessage"


@dataclass(frozen=True, slots=True)
class ModelBinding:
    source: ContaModel
    target_table: str
    invariant: str


BINDINGS: tuple[ModelBinding, ...] = (
    ModelBinding(ContaModel.ACCOUNTING_PERIOD, "accounting_periods", "tenant scoped + period state"),
    ModelBinding(ContaModel.JOURNAL_ENTRY, "journal_entries", "immutable after posting"),
    ModelBinding(ContaModel.JOURNAL_LINE, "journal_lines", "tenant+entry ownership + currency balance"),
    ModelBinding(ContaModel.FINANCIAL_DOCUMENT, "financial_documents", "lifecycle + DIAN identity + immutable validation"),
    ModelBinding(ContaModel.TREASURY_ACCOUNT, "treasury_accounts", "tenant scoped + ledger account"),
    ModelBinding(ContaModel.TREASURY_MOVEMENT, "treasury_movements", "linked to payment/journal"),
    ModelBinding(ContaModel.FIXED_ASSET, "fixed_assets", "asset lifecycle + depreciation"),
    ModelBinding(ContaModel.DEPRECIATION_RUN, "depreciation_runs", "period unique + journal linkage"),
    ModelBinding(ContaModel.PROVISION, "provisions", "period + journal linkage"),
    ModelBinding(ContaModel.ANNUAL_CLOSING_RUN, "annual_closing_runs", "controlled year close"),
    ModelBinding(ContaModel.TAX_DETERMINATION, "tax_determinations", "period tax aggregation"),
    ModelBinding(ContaModel.DIAN_SUBMISSION, "dian_submissions", "external validation ledger"),
)


def binding_for(source: ContaModel) -> ModelBinding:
    for binding in BINDINGS:
        if binding.source is source:
            return binding
    raise KeyError(source)
