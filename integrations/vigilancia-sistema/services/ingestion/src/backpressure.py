class Backpressure:
 def __init__(self,max_queue:int=100000):self.max_queue=max_queue;self.current=0
 def update(self,size:int):self.current=max(0,size)
 def should_accept(self,event:dict)->bool:
  ratio=self.current/max(self.max_queue,1);p=event.get("priority")
  if ratio<.70:return True
  if ratio<.90:return p in {"CRITICAL","SECURITY","ANOMALY"}
  return p=="CRITICAL"
