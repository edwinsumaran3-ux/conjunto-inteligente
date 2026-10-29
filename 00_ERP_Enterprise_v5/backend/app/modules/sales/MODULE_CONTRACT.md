# sales

Status: PARTIALLY IMPLEMENTED (Etapa 3).

## What is real
- Domain layer (`domain/order.py`, `domain/order_lifecycle.py`): order/line
  validation (positive quantity, non-negative price, 3-letter currency,
  at least one line) and the DRAFT -> CONFIRMED -> FULFILLED state machine
  (CANCELLED reachable from DRAFT/CONFIRMED only). Executed and verified
  with 8 real unit tests in this environment.
- Application layer (`application/order_service.py`): order creation uses
  the project's generic idempotency mechanism (`backend.app.core.idempotency`),
  same as `billing.application.invoice_service.create_draft`. State
  transitions use guarded UPDATE (WHERE status=<expected>) to detect
  concurrent changes, same idiom as `inventory.application.stock_service`.
  Fulfillment composes `inventory.application.stock_service.InventoryStockService`
  (an application service call, never a direct write to inventory's tables —
  same pattern as `billing.issue_service` composing `accounting.posting_service`),
  with a deterministic per-line idempotency key so a retried fulfillment
  request cannot double-consume stock.
  **NOT VERIFIED against a real PostgreSQL instance** — no DB/network
  available in the environment where this was written. STATIC PASS only.
- Migration `0030_sales_module.py`: `sales_orders`, `sales_order_lines`
  (FK to `inventory_items`), RLS/FORCE RLS, chained after `0029_inventory_module`.
- API router (`api/router.py`): create/confirm/fulfill/cancel endpoints,
  registered in `backend/app/api/router.py`.

## What is still NOT implemented (do not assume otherwise)
- No pricing rules, discounts, or tax calculation on order lines (unit_price
  is taken as given — billing already has its own tax handling, this does
  not duplicate it).
- No partial fulfillment (an order is fulfilled all-or-nothing today).
- No link from a fulfilled sales order to a billing invoice — that
  integration (sales -> billing) is not built yet.
- No backorder handling beyond what `inventory` already allows per item
  (`allow_negative_stock`).
- No integration test executed against real PostgreSQL/Redis.
- No load or chaos testing.

Forbidden (unchanged from the original contract): placeholder endpoints,
fake persistence, silent fallbacks, cross-module database writes that
bypass application services.
