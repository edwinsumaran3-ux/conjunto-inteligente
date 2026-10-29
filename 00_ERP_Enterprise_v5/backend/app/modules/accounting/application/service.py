from uuid import UUID
from ..infrastructure.repository import AccountingRepository
from ..domain.journal import Journal,JournalLine
from ..schemas.journal import JournalIn
from backend.app.core.outbox import enqueue
class AccountingService:
    def __init__(self,repo=None):self.repo=repo or AccountingRepository()
    async def post_journal(self,s,tenant_id:UUID,user_id:UUID,cmd:JournalIn)->UUID:
        j=Journal(tenant_id,cmd.period_id,cmd.entry_date,cmd.description,cmd.source_type,cmd.source_id,user_id,tuple(JournalLine(x.account_id,x.debit,x.credit,x.currency,x.description,x.exchange_rate) for x in cmd.lines)); j.validate(); eid=await self.repo.post(s,j); await enqueue(s,tenant_id,'accounting.journal.posted','journal_entry',eid,{'journal_entry_id':str(eid)}); return eid
