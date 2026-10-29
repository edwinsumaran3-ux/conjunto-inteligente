from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class PostingRule:
    code: str
    debit_account: str
    credit_account: str
    description: str

# Conservative defaults. Tenant/company configuration MUST select the actual account
# mapping; these are templates, not an assertion that every Colombian sector uses them.
PUC_COLOMBIA_TEMPLATES = {
    'SALE_GOODS': PostingRule('SALE_GOODS','1305','4135','Venta de mercancías'),
    'PURCHASE_GOODS': PostingRule('PURCHASE_GOODS','1435','2205','Compra de mercancías'),
    'IVA_OUTPUT': PostingRule('IVA_OUTPUT','1305','2408','IVA generado'),
    'IVA_INPUT': PostingRule('IVA_INPUT','2408','2205','IVA descontable'),
    'WITHHOLDING_SOURCE': PostingRule('WITHHOLDING_SOURCE','1355','2365','Retención en la fuente'),
}

def assert_positive_amount(value: Decimal, label: str)->None:
    if value <= 0: raise ValueError(f'{label} must be positive')
