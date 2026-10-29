from decimal import Decimal
from uuid import uuid4
import pytest
from backend.app.modules.accounting.domain.journal import Journal,JournalLine
def line(d='0',c='0',cur='COP'):return JournalLine(uuid4(),Decimal(d),Decimal(c),cur)
def test_balanced_per_currency():
    j=Journal(uuid4(),uuid4(),None,'sale','sale',None,uuid4(),(line('100','0'),line('0','100'))); j.validate()
def test_unbalanced_rejected():
    j=Journal(uuid4(),uuid4(),None,'bad','sale',None,uuid4(),(line('100','0'),line('0','99')))
    with pytest.raises(ValueError):j.validate()
def test_cross_currency_is_not_silently_netting():
    j=Journal(uuid4(),uuid4(),None,'bad','sale',None,uuid4(),(line('100','0','COP'),line('0','100','USD')))
    with pytest.raises(ValueError):j.validate()
