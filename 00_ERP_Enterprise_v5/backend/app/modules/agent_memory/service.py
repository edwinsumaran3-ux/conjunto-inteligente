from __future__ import annotations
import hashlib, json
from typing import Any
def content_hash(content: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str).encode()).hexdigest()
