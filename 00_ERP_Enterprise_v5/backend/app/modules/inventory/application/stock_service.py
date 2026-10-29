from __future__ import annotations
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.idempotency import reserve, complete, fingerprint
from backend.app.modules.inventory.domain.stock import StockDirection, StockMovement

class InventoryStockService:
    async def create_item(self, session: AsyncSession, tenant_id: UUID, actor_id: UUID, sku: str, name: str, unit: str) -> UUID:
        row = await session.scalar(text("""
            INSERT INTO inventory_items(tenant_id,sku,name,unit,active,created_by)
            VALUES(:t,:sku,:name,:unit,true,:u) RETURNING id
        """), {"t": tenant_id, "sku": sku, "name": name, "unit": unit, "u": actor_id})
        item_id = UUID(str(row))
        await session.execute(text("INSERT INTO inventory_stock(tenant_id,item_id,quantity) VALUES(:t,:i,0)"), {"t": tenant_id, "i": item_id})
        return item_id

    async def register_movement(
        self, session: AsyncSession, tenant_id: UUID, actor_id: UUID, item_id: UUID,
        direction: StockDirection, quantity: Decimal, *, reason: str, reference: str | None,
        idempotency_key: UUID | str,
    ) -> UUID:
        movement = StockMovement(direction, quantity)
        movement.validate()
        payload = {"item_id": str(item_id), "direction": direction.value, "quantity": str(quantity), "reason": reason, "reference": reference}
        key = str(idempotency_key)
        route = "POST:/inventory/movements"
        idem = await reserve(session, tenant_id, key, route, fingerprint(payload))
        if idem.status == "completed":
            return UUID(str(idem.response_body["id"]))
        if idem.status == "in_progress":
            raise RuntimeError("request with this idempotency key is already in progress")

        row = (await session.execute(text("""
            SELECT quantity FROM inventory_stock
             WHERE tenant_id=:t AND item_id=:i FOR UPDATE
        """), {"t": tenant_id, "i": item_id})).mappings().one_or_none()
        if row is None:
            raise ValueError("inventory item stock record not found")
        current = Decimal(str(row["quantity"]))
        balance = movement.resulting_balance(current)
        movement_id = UUID(str(await session.scalar(text("""
            INSERT INTO inventory_movements
              (tenant_id,item_id,direction,quantity,balance_after,reason,reference,created_by,idempotency_key)
            VALUES(:t,:i,:dir,:q,:b,:reason,:ref,:u,:k) RETURNING id
        """), {"t":tenant_id,"i":item_id,"dir":direction.value,"q":quantity,"b":balance,"reason":reason,"ref":reference,"u":actor_id,"k":key})))
        await session.execute(text("UPDATE inventory_stock SET quantity=:q,updated_at=now() WHERE tenant_id=:t AND item_id=:i"), {"q": balance, "t": tenant_id, "i": item_id})
        await complete(session, tenant_id, key, route, 201, {"id": str(movement_id)})
        return movement_id
