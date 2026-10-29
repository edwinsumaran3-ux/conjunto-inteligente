from backend.app.modules.physical_edge.service import sign_envelope,verify_signature,command_allowed,safety_allows,sha256_json

def test_signature_round_trip():
    secret=b'x'*32; env={'command_id':'1','sequence':1,'payload_hash':sha256_json({'x':1})}; sig=sign_envelope(env,secret)
    assert verify_signature(env,sig,secret); assert not verify_signature(env,sig[:-1]+'0',secret)

def test_safety_fail_closed():
    assert safety_allows('kill_switch','set_relay') is False
    assert safety_allows('kill_switch','safe_state') is True
    assert safety_allows('armed','set_relay') is True

def test_capability_allowlist():
    assert command_allowed('set_relay',['set_relay'])
    assert not command_allowed('set_relay',['lock'])
