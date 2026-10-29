import base64,json
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature,encode_dss_signature
from cryptography.exceptions import InvalidSignature
class DeviceIdentity:
 def __init__(self,device_id:str,priv_key_pem:bytes):self.device_id=device_id;self.priv_key=serialization.load_pem_private_key(priv_key_pem,password=None)
 def sign(self,payload:bytes)->str:
  r,s=decode_dss_signature(self.priv_key.sign(payload,ec.ECDSA(hashes.SHA256())));return base64.b64encode(encode_dss_signature(r,s)).decode()
 @staticmethod
 def verify(payload:bytes,signature_b64:str,pub_pem:bytes)->bool:
  try:
   sig=base64.b64decode(signature_b64,validate=True);pub=serialization.load_pem_public_key(pub_pem);pub.verify(sig,payload,ec.ECDSA(hashes.SHA256()));return True
  except (ValueError,TypeError,InvalidSignature):return False
def canonical_event_bytes(event):return json.dumps({k:v for k,v in event.items() if k!="signature"},sort_keys=True,separators=(",",":")).encode()
def sign_event(event,identity):event["signature"]=identity.sign(canonical_event_bytes(event));return event
