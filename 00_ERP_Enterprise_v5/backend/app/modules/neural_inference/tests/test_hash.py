from backend.app.modules.neural_inference.service import canonical_hash
def test_inference_hash_is_canonical(): assert canonical_hash({'x':[1,2],'a':True})==canonical_hash({'a':True,'x':[1,2]})
