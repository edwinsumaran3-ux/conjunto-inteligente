from __future__ import annotations
import json
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.modules.accounting.domain.journal import Journal
class AccountingRepository:
    async def post(self,session:AsyncSession,journal:Journal)->UUID:
        journal.validate(); payload=[{'account_id':str(x.account_id),'debit':str(x.debit),'credit':str(x.credit),'currency':x.currency,'description':x.description,'exchange_rate':str(x.exchange_rate)} for x in journal.lines]
        return await session.scalar(text('SELECT post_journal(:t,:p,:d,:desc,:st,:sid,:u,CAST(:lines AS jsonb))'),{'t':journal.tenant_id,'p':journal.period_id,'d':journal.entry_date,'desc':journal.description,'st':journal.source_type,'sid':journal.source_id,'u':journal.created_by,'lines':json.dumps(payload,separators=(',',':'))})
