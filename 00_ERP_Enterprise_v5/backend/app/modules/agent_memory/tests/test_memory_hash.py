from backend.app.modules.agent_memory.service import content_hash
def test_memory_hash_is_canonical(): assert content_hash({'b':2,'a':1})==content_hash({'a':1,'b':2})
