#!/usr/bin/env python3
import argparse,time,docker
client=docker.from_env()
SCENARIOS={"kill-worker":("worker-pool","kill"),"kill-edge":("edge-gateway","kill"),"kill-db":("postgres","pause"),"kill-rabbit":("rabbitmq","pause"),"network-partition":("edge-gateway","network_disconnect"),"kill-agent-orchestrator":("agent-orchestrator","kill")}
def kill(c):x=client.containers.get(c);x.kill();time.sleep(5);x.start()
def pause(c,secs=30):x=client.containers.get(c);x.pause();time.sleep(secs);x.unpause()
def network_disconnect(c,secs=30):
 x=client.containers.get(c);nets=list(x.attrs['NetworkSettings']['Networks'].keys())
 for n in nets:client.networks.get(n).disconnect(x)
 time.sleep(secs)
 for n in nets:client.networks.get(n).connect(x)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--scenario',required=True,choices=list(SCENARIOS));ap.add_argument('--duration',type=int,default=30);a=ap.parse_args();container,action=SCENARIOS[a.scenario];print(f'[CHAOS] {a.scenario} -> {container} / {action}');kill(container) if action=='kill' else pause(container,a.duration) if action=='pause' else network_disconnect(container,a.duration)
if __name__=='__main__':main()
