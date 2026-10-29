class LocalRuleEngine:
 def process(self,e):
  t=e.get("type")
  if t=="TAMPER":return [{**e,"escalated":True,"priority":"CRITICAL","action":"SOUND_ALARM"}]
  if t=="DOOR":return [{**e,"action":"LOG_AND_NOTIFY_LOCAL"}]
  if t=="MOTION":return [{**e,"action":"RECORD_CLIP"}]
  return [e]
