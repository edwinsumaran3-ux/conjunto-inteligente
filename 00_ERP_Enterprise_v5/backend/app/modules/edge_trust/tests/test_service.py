from app.modules.edge_trust.service import *
def test_attestation_signature_and_reconciliation():
    p=attest_payload('d','n','b','f','m'); s=sign_attestation(p,b'x'*32)
    assert verify_attestation(p,s,b'x'*32); assert not verify_attestation(p,s,b'y'*32)
    assert reconcile(10,8,[1,2,2])['duplicates']==1
    assert reconcile(8,10,[])['status']=='conflicted'
def test_rollout_and_chaos():
    policy={'enabled':True,'min_healthy_percent':99,'max_failure_percent':1}
    assert rollout_allowed(99.5,.5,policy); assert not rollout_allowed(98,.5,policy)
    assert select_rollout_batch([{'status':'eligible','attested':True},{'status':'eligible','attested':True}],1)==[{'status':'eligible','attested':True}]
    assert evaluate_chaos('network_loss','safe').passed
