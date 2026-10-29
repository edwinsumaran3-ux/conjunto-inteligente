# Inventory module contract

Inventory owns item master data, stock balances and immutable stock movements. Other modules MUST use `InventoryStockService.register_movement`; they MUST NOT write inventory tables directly. All mutations are tenant-scoped, idempotent and concurrency-safe. OUT movements fail closed when stock is insufficient.
