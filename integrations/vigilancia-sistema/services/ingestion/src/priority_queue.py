PRIORITY_MAP={"CRITICAL":0,"SECURITY":1,"ANOMALY":2,"TELEMETRY":3}
def priority_of(event):return PRIORITY_MAP.get(event.get("priority","TELEMETRY"),3)
