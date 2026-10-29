import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { AgentAction, AgentStatus, PendingApproval } from "../types/agent";

export function useAgentLoop() {
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [pending, setPending] = useState<PendingApproval[]>([]);
  const [recentActions, setRecentActions] = useState<AgentAction[]>([]);
  const [online, setOnline] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [st, pend, actions] = await Promise.all([api.agentsStatus(), api.approvalsPending(), api.actionsRecent()]);
      setStatus(st as AgentStatus);
      setPending(pend as PendingApproval[]);
      setRecentActions(actions as AgentAction[]);
      setOnline(true);
    } catch {
      setOnline(false);
    }
  }, []);

  const decide = useCallback(async (approvalId: string, decidedBy: string, decision: "APPROVED" | "REJECTED") => {
    await api.approvalsDecide(approvalId, decidedBy, decision);
    await refresh();
  }, [refresh]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, [refresh]);

  return { status, pending, recentActions, online, decide, refresh };
}
