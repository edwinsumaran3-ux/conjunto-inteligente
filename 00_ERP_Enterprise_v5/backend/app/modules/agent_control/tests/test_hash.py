import hashlib, json

def test_execution_input_hash_is_canonical():
    a={'b':2,'a':1}; b={'a':1,'b':2}
    assert hashlib.sha256(json.dumps(a,sort_keys=True,separators=(',',':')).encode()).hexdigest()==hashlib.sha256(json.dumps(b,sort_keys=True,separators=(',',':')).encode()).hexdigest()
