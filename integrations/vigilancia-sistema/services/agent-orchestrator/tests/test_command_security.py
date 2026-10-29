import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from control.command_security import sign_command, verify_command
from equipment_contracts import EquipmentCommand, EquipmentType


def command(signature=''):
    return EquipmentCommand('00000000-0000-0000-0000-000000000001','nonce-1',EquipmentType.DRONE,'drone-01','telemetry',{'mode':'read'},1000,1100,'operator-1',signature)


def test_hmac_signature(monkeypatch):
    monkeypatch.setenv('EQUIPMENT_HMAC_KEYS_JSON', '{"drone-01":"secret"}')
    unsigned=command()
    signed=command(sign_command(unsigned,'secret'))
    assert verify_command(signed)


def test_wrong_signature_rejected(monkeypatch):
    monkeypatch.setenv('EQUIPMENT_HMAC_KEYS_JSON', '{"drone-01":"secret"}')
    assert not verify_command(command('bad'))
