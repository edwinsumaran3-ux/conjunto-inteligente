import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from app.modules.edge_transport.service import verify_ed25519, canonical

def test_ed25519_transport_roundtrip():
    private=Ed25519PrivateKey.generate(); public=private.public_key()
    raw=public.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    import base64
    envelope={'gateway_id':'g','nonce':'n'*16,'sequence':1,'payload':{'x':1}}
    sig=base64.b64encode(private.sign(canonical(envelope))).decode()
    assert verify_ed25519(envelope,sig,base64.b64encode(raw).decode())
    assert not verify_ed25519({**envelope,'sequence':2},sig,base64.b64encode(raw).decode())
