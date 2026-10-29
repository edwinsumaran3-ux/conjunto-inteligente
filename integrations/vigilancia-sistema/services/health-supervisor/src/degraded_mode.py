import os,httpx
class DegradedModeDecisor:
 def __init__(self):self.internet_url=os.getenv("INTERNET_CHECK","https://1.1.1.1");self.db_dsn=os.getenv("DB_DSN","");self.ai_urls=os.getenv("AI_URLS","").split(",") if os.getenv("AI_URLS") else []
 def check_internet(self):
  try:httpx.get(self.internet_url,timeout=2.0);return True
  except Exception:return False
 def evaluate(self,db_ok,ai_ok,edge_ok):
  internet=self.check_internet()
  if not edge_ok:return "SAFE"
  if not internet:return "LOCAL"
  if not db_ok or not ai_ok:return "PARTIAL"
  return "FULL"
