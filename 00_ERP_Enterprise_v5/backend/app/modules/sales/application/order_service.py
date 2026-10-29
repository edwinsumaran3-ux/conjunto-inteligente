"""Sales order orchestration: inventory fulfillment and automatic billing draft are one transaction."""
from __future__ import annotations
from datetime import date, timedelta
from uuid import UUID, uuid5, NAMESPACE_URL
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.idempotency import reserve, complete, fingerprint
from backend.app.modules.billing.application.invoice_service import BillingService
from backend.app.modules.billing.schemas.invoice import CreateInvoiceInput, InvoiceLineInput, TaxInput
from backend.app.modules.inventory.application.stock_service import InventoryStockService
from backend.app.modules.inventory.domain.stock import StockDirection
from backend.app.modules.sales.domain.order import SalesOrder, SalesOrderLine
from backend.app.modules.sales.domain.order_lifecycle import SalesOrderState, transition
from backend.app.modules.sales.schemas.order import CreateSalesOrderInput

class SalesOrderNotFoundError(ValueError): pass

class SalesOrderService:
    def __init__(self, stock: InventoryStockService | None = None, billing: BillingService | None = None):
        self.stock = stock or InventoryStockService()
        self.billing = billing or BillingService()

    async def create_draft(self, session: AsyncSession, tenant_id: UUID, user_id: UUID, cmd: CreateSalesOrderInput) -> UUID:
        payload = cmd.model_dump(mode="json")
        route = "POST:/sales/orders"
        idem = await reserve(session, tenant_id, cmd.idempotency_key, route, fingerprint(payload))
        if idem.status == "completed": return UUID(str(idem.response_body["id"]))
        if idem.status == "in_progress": raise RuntimeError("request with this idempotency key is already in progress")
        order = SalesOrder(
            tenant_id=tenant_id, partner_id=cmd.partner_id, currency=cmd.currency.upper(),
            invoice_series=cmd.invoice_series, payment_terms_days=cmd.payment_terms_days,
            lines=tuple(SalesOrderLine(l.item_id,l.quantity,l.unit_price,l.billing_account_id,tuple((t.code,t.rate) for t in l.taxes)) for l in cmd.lines),
        )
        order.validate()
        order_id = UUID(str(await session.scalar(text("""
            INSERT INTO sales_orders(tenant_id,partner_id,currency,status,total_amount,invoice_series,payment_terms_days,created_by)
            VALUES(:t,:p,:c,'DRAFT',:total,:series,:terms,:u) RETURNING id
        """), {"t":tenant_id,"p":cmd.partner_id,"c":order.currency,"total":order.total(),"series":cmd.invoice_series,"terms":cmd.payment_terms_days,"u":user_id})))
        for idx,line in enumerate(order.lines,1):
            await session.execute(text("""
                INSERT INTO sales_order_lines(tenant_id,sales_order_id,line_no,item_id,quantity,unit_price,subtotal,billing_account_id,taxes)
                VALUES(:t,:o,:n,:i,:q,:p,:sub,:a,CAST(:taxes AS jsonb))
            """), {"t":tenant_id,"o":order_id,"n":idx,"i":line.item_id,"q":line.quantity,"p":line.unit_price,"sub":line.subtotal(),"a":line.billing_account_id,"taxes":__import__('json').dumps([{"code":c,"rate":str(r)} for c,r in line.taxes])})
        await complete(session,tenant_id,cmd.idempotency_key,route,201,{"id":str(order_id)})
        return order_id

    async def _load_status(self, session: AsyncSession, tenant_id: UUID, order_id: UUID):
        row=(await session.execute(text("SELECT status, billing_document_id FROM sales_orders WHERE tenant_id=:t AND id=:o FOR UPDATE"),{"t":tenant_id,"o":order_id})).mappings().one_or_none()
        if row is None: raise SalesOrderNotFoundError("sales order not found")
        return SalesOrderState(row["status"]), row["billing_document_id"]

    async def confirm(self, session, tenant_id, order_id):
        current,_=await self._load_status(session,tenant_id,order_id); target=transition(current,SalesOrderState.CONFIRMED)
        if (await session.execute(text("UPDATE sales_orders SET status=:s WHERE tenant_id=:t AND id=:o AND status=:cur RETURNING id"),{"s":target.value,"t":tenant_id,"o":order_id,"cur":current.value})).scalar_one_or_none() is None: raise RuntimeError("sales order status changed concurrently, retry")

    async def cancel(self, session, tenant_id, order_id):
        current,_=await self._load_status(session,tenant_id,order_id); target=transition(current,SalesOrderState.CANCELLED)
        if (await session.execute(text("UPDATE sales_orders SET status=:s WHERE tenant_id=:t AND id=:o AND status=:cur RETURNING id"),{"s":target.value,"t":tenant_id,"o":order_id,"cur":current.value})).scalar_one_or_none() is None: raise RuntimeError("sales order status changed concurrently, retry")

    async def fulfill(self, session: AsyncSession, tenant_id: UUID, actor_id: UUID, order_id: UUID) -> UUID:
        current,billing_document_id=await self._load_status(session,tenant_id,order_id)
        if current is SalesOrderState.FULFILLED:
            if not billing_document_id: raise RuntimeError("fulfilled order has no billing document")
            return UUID(str(billing_document_id))
        target=transition(current,SalesOrderState.FULFILLED)
        order=(await session.execute(text("SELECT partner_id,currency,invoice_series,payment_terms_days FROM sales_orders WHERE tenant_id=:t AND id=:o"),{"t":tenant_id,"o":order_id})).mappings().one()
        lines=(await session.execute(text("SELECT id,item_id,quantity,unit_price,billing_account_id,taxes FROM sales_order_lines WHERE tenant_id=:t AND sales_order_id=:o ORDER BY line_no"),{"t":tenant_id,"o":order_id})).mappings().all()
        if not lines: raise RuntimeError("sales order has no lines, cannot fulfill")
        for line in lines:
            movement_key=uuid5(NAMESPACE_URL,f"sales-order-fulfillment:{order_id}:{line['id']}")
            await self.stock.register_movement(session,tenant_id,actor_id,line["item_id"],StockDirection.OUT,line["quantity"],reason=f"Sales order {order_id} fulfillment",reference=str(order_id),idempotency_key=movement_key)
        today=date.today(); due=today+timedelta(days=int(order["payment_terms_days"]))
        invoice_lines=[]
        for line in lines:
            taxes=[]
            for t in (line["taxes"] or []): taxes.append(TaxInput(code=t["code"],rate=t["rate"]))
            invoice_lines.append(InvoiceLineInput(description=f"Sales order {order_id} line {line['id']}",quantity=line["quantity"],unit_price=line["unit_price"],account_id=line["billing_account_id"],taxes=taxes))
        invoice_cmd=CreateInvoiceInput(partner_id=order["partner_id"],issue_date=today,due_date=due,currency=order["currency"],series=order["invoice_series"],lines=invoice_lines,idempotency_key=str(uuid5(NAMESPACE_URL,f"sales-order-invoice:{order_id}")),source_type="SALES_ORDER",source_id=order_id)
        document_id=await self.billing.create_draft(session,tenant_id,actor_id,invoice_cmd)
        updated=await session.execute(text("UPDATE sales_orders SET status=:s,billing_document_id=:d,fulfilled_at=now() WHERE tenant_id=:t AND id=:o AND status=:cur RETURNING id"),{"s":target.value,"d":document_id,"t":tenant_id,"o":order_id,"cur":current.value})
        if updated.scalar_one_or_none() is None: raise RuntimeError("sales order status changed concurrently, retry")
        return document_id
