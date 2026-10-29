from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
class CatalogRepository:
    async def create_period(self,s:AsyncSession,t:UUID,code:str,starts_on,ends_on)->UUID:
        return await s.scalar(text("INSERT INTO accounting_periods(id,tenant_id,code,starts_on,ends_on,status) VALUES(gen_random_uuid(),:t,:c,:a,:b,'OPEN') RETURNING id"),{'t':t,'c':code,'a':starts_on,'b':ends_on})
    async def close_period(self,s:AsyncSession,t:UUID,p:UUID,u:UUID)->None:
        result=await s.execute(text("UPDATE accounting_periods SET status='CLOSED',closed_at=now(),closed_by=:u WHERE tenant_id=:t AND id=:p AND status='OPEN'"),{'t':t,'p':p,'u':u})
        if result.rowcount!=1: raise ValueError('period does not exist or is already closed')
    async def create_account(self,s:AsyncSession,t:UUID,code:str,name:str,kind:str,side:str)->UUID:
        return await s.scalar(text("INSERT INTO chart_accounts(id,tenant_id,code,name,kind,normal_side) VALUES(gen_random_uuid(),:t,:c,:n,:k,:side) RETURNING id"),{'t':t,'c':code,'n':name,'k':kind,'side':side})
