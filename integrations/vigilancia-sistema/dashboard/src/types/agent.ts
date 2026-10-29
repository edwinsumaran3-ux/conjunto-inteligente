export type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type ActionType = "SOUND_ALARM" | "LOCK_ACCESS" | "UNLOCK_ACCESS" | "NOTIFY_AUTHORITIES" | "FOCUS_CAMERA" | "START_RECORDING" | "SAFE_HOLD" | "NO_OP";

export interface AgentStatus {
  agents: string[];
  last_tick: number | null;
  last_incident: { incident_id: string; kind: string; at: number } | null;
  pending_approvals: number;
}

export interface PendingApproval {
  approval_id: string;
  action_id: string;
  requested_at: string;
  expires_at: string;
  fallback_action: ActionType;
  agent_name: string;
  action_type: ActionType;
  severity: Severity;
  target_device_id: string | null;
  zone: string | null;
  rationale: string;
  payload: Record<string, unknown>;
}

export interface AgentAction {
  action_id: string;
  incident_id: string | null;
  agent_name: string;
  action_type: ActionType;
  severity: Severity;
  target_device_id: string | null;
  zone: string | null;
  rationale: string;
  status: string;
  created_at: string;
  resolved_at: string | null;
}
