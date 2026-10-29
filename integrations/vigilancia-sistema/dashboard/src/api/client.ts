const BASE=import.meta.env.VITE_API_URL||"http://localhost:8000";
const OPERATOR_TOKEN=import.meta.env.VITE_OPERATOR_TOKEN||"";
const authHeaders=():Record<string,string>=>OPERATOR_TOKEN?{"X-Operator-Token":OPERATOR_TOKEN}:{};const EDGE=import.meta.env.VITE_EDGE_URL||"http://localhost:8001";const AGENT=import.meta.env.VITE_AGENT_URL||"http://localhost:8002";
async function get<T>(u:string):Promise<T>{const r=await fetch(u);if(!r.ok)throw new Error(`${r.status} ${u}`);return r.json()}
async function post<T>(u:string,body:unknown):Promise<T>{const r=await fetch(u,{method:"POST",headers:{"Content-Type":"application/json",...authHeaders()},body:JSON.stringify(body)});if(!r.ok)throw new Error(`${r.status} ${u}`);return r.json()}
export const api={
  health:()=>get<any>(`${BASE}/healthz`),
  edgeHealth:()=>get<any>(`${EDGE}/healthz`),
  edgeDevices:()=>get<any[]>(`${EDGE}/devices`),
  incidents:()=>get<any[]>(`${BASE}/incidents?limit=100`),
  events:()=>get<any[]>(`${BASE}/events?limit=100`),
  discoveryScan:(addresses:string[],zone:string)=>post<any[]>(`${EDGE}/discovery/scan`,{addresses,zone}),
  discoveryDevices:()=>get<any[]>(`${EDGE}/discovery/devices`),
  meshTopology:()=>get<Record<string,string[]>>(`${EDGE}/mesh/topology`),
  meshLink:(sensor_id:string,camera_ids:string[])=>post<any>(`${EDGE}/mesh/link`,{sensor_id,camera_ids}),
  agentsHealth:()=>get<any>(`${AGENT}/healthz`),
  agentsStatus:()=>get<any>(`${AGENT}/agents/status`),
  approvalsPending:()=>get<any[]>(`${AGENT}/approvals/pending`),
  approvalsHistory:()=>get<any[]>(`${AGENT}/approvals/history?limit=50`),
  approvalsDecide:(approvalId:string,decided_by:string,decision:"APPROVED"|"REJECTED")=>post<any>(`${AGENT}/approvals/${approvalId}/decide`,{decided_by,decision}),
  actionsRecent:()=>get<any[]>(`${AGENT}/actions/recent?limit=100`),
  equipmentRegistry:()=>get<any[]>(`${AGENT}/equipment/registry`),
  equipmentEmergencyStop:()=>post<any>(`${AGENT}/equipment/emergency-stop`,{}),
  droneCatalog:()=>get<any[]>(`${AGENT}/equipment/drone-catalog`),
  registerDrone:(equipment_id:string,model_key:string)=>post<any>(`${AGENT}/equipment/drones`,{equipment_id,model_key}),
};
