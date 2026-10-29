from harness import HIL
def test_network_loss_fails_safe():
 h=HIL(); h.add('d1'); h.fault('d1','network_loss'); assert h.reconcile('d1')=='safe'
def test_gateway_failure_stays_safe():
 h=HIL(); h.add('d1'); h.fault('d1','gateway_failure'); assert h.devices['d1'].state=='safe'
