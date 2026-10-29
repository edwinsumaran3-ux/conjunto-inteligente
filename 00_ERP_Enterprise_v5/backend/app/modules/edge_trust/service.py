from __future__ import annotations
import hashlib,hmac,json
from dataclasses import dataclass

def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str)
def digest(v): return hashlib.sha256(canonical(v).encode()).hexdigest()
def attest_payload(device_id,nonce,boot_id,firmware_hash,measurement_hash):
    return {'device_id':str(device_id),'nonce':nonce,'boot_id':boot_id,'firmware_hash':firmware_hash,'measurement_hash':measurement_hash}
def sign_attestation(payload,key): return hmac.new(key,canonical(payload).encode(),hashlib.sha256).hexdigest()
def verify_attestation(payload,signature,key): return hmac.compare_digest(sign_attestation(payload,key),signature)
def reconcile(device_sequence,server_sequence,seen_sequences):
    seen=set(seen_sequences); duplicate=max(0,len(seen_sequences)-len(seen)); missing=max(0,device_sequence-server_sequence)
    conflict=1 if server_sequence>device_sequence else 0
    return {'missing':missing,'duplicates':duplicate,'conflicts':conflict,'status':'conflicted' if conflict else 'reconciled'}
def rollout_allowed(healthy_percent,failure_percent,policy):
    return bool(policy['enabled'] and healthy_percent>=policy['min_healthy_percent'] and failure_percent<=policy['max_failure_percent'])
def select_rollout_batch(devices,max_concurrent):
    eligible=[d for d in devices if d.get('status')=='eligible' and d.get('attested')]
    return eligible[:max(0,max_concurrent)]
@dataclass(frozen=True)
class ChaosResult:
    scenario:str
    expected_safe:bool
    observed_safe:bool
    passed:bool

def evaluate_chaos(scenario,observed_state):
    expected={'network_loss':'safe','gateway_failure':'safe','replay':'safe','clock_skew':'safe','corrupt_ota':'safe'}.get(scenario)
    if expected is None: raise ValueError('UNKNOWN_CHAOS_SCENARIO')
    return ChaosResult(scenario,True,observed_state==expected,observed_state==expected)
