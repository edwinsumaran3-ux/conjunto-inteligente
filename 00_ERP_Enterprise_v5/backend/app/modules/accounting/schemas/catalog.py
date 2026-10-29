from datetime import date
from pydantic import BaseModel,Field,field_validator
from backend.app.modules.accounting.domain.value_objects import AccountKind
class PeriodIn(BaseModel):
    code:str=Field(min_length=1,max_length=30); starts_on:date; ends_on:date
    @field_validator('ends_on')
    @classmethod
    def order(cls,v,info):
        if 'starts_on' in info.data and v<info.data['starts_on']: raise ValueError('ends_on must be >= starts_on')
        return v
class AccountIn(BaseModel):
    code:str=Field(min_length=1,max_length=30); name:str=Field(min_length=1,max_length=160); kind:AccountKind; normal_side:str=Field(min_length=1,max_length=1)
    @field_validator('normal_side')
    @classmethod
    def side(cls,v):
        v=v.upper()
        if v not in {'D','C'}: raise ValueError('normal_side must be D or C')
        return v
