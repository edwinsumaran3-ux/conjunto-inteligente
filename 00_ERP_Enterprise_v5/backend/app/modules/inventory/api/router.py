from uuid import UUID
from fastapi import APIRouter, Depends
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session
from backend.app.modules.inventory.application.stock_service import InventoryStockService
from backend.app.modules.inventory.schemas.item import CreateInventoryItemInput, RegisterStockMovementInput
from backend.app.modules.inventory.domain.stock import StockDirection

router = APIRouter(prefix="/inventory", tags=["inventory"])
service = InventoryStockService()

@router.post("/items", status_code=201)
async def create_item(cmd: CreateInventoryItemInput, auth: AuthContext = Depends(get_auth_context), session=Depends(get_tenant_session)):
    item_id = await service.create_item(session, UUID(auth.tenant_id), UUID(auth.user_id), cmd.sku, cmd.name, cmd.unit)
    return {"id": str(item_id), "status": "ACTIVE"}

@router.post("/movements", status_code=201)
async def movement(cmd: RegisterStockMovementInput, auth: AuthContext = Depends(get_auth_context), session=Depends(get_tenant_session)):
    direction = StockDirection(cmd.direction.upper())
    movement_id = await service.register_movement(session, UUID(auth.tenant_id), UUID(auth.user_id), cmd.item_id, direction, cmd.quantity, reason=cmd.reason, reference=cmd.reference, idempotency_key=cmd.idempotency_key)
    from backend.app.platform.realtime.service import publish
    await publish(session, tenant_id=UUID(auth.tenant_id), topic="inventory.movement.registered", payload={"movement_id": str(movement_id), "item_id": str(cmd.item_id), "direction": direction.value}, correlation_id=str(movement_id))
    return {"id": str(movement_id), "direction": direction.value}
