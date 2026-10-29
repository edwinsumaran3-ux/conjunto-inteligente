from uuid import UUID
class CatalogService:
    def __init__(self,repo=None):
        from backend.app.modules.accounting.infrastructure.catalog_repository import CatalogRepository
        self.repo=repo or CatalogRepository()
    async def create_period(self,s,t,cmd):return await self.repo.create_period(s,t,cmd.code,cmd.starts_on,cmd.ends_on)
    async def close_period(self,s,t,p,u):return await self.repo.close_period(s,t,p,u)
    async def create_account(self,s,t,cmd):return await self.repo.create_account(s,t,cmd.code,cmd.name,cmd.kind.value,cmd.normal_side)
