import { useState } from "react";
import type { ChangeEvent } from "react";
import { useAgentLoop } from "../hooks/useAgentLoop";
import AgentStatusPanel from "../components/agents/AgentStatusPanel";
import HumanApprovalModal from "../components/agents/HumanApprovalModal";
import EquipmentRegistryPanel from "../components/agents/EquipmentRegistryPanel";
import DroneCatalogPanel from "../components/agents/DroneCatalogPanel";

export default function AgentOrchestratorView() {
  const { status, pending, recentActions, online, decide } = useAgentLoop();
  const [operatorName, setOperatorName] = useState("operador-turno");

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-ops-panel2 bg-ops-panel p-4">
        <h2 className="font-semibold">Orquestación de agentes autónomos</h2>
        <p className="text-xs text-ops-inkdim mt-0.5">
          Ciclo Sense → Plan → Action Proposal → Reflect. Las acciones con impacto físico (sirena, bloqueo de accesos,
          notificación a autoridades) quedan en cola de aprobación humana con temporizador; si vence, se aplica un
          protocolo de salvaguarda automático en vez de ejecutarse.
        </p>
        <label className="text-xs text-ops-inkdim flex items-center gap-2 mt-3">
          Operador que confirma:
          <input value={operatorName} onChange={(e: ChangeEvent<HTMLInputElement>) => setOperatorName(e.target.value)} className="bg-ops-panel2 border border-ops-linesoft rounded-lg px-2 py-1 text-xs" />
        </label>
      </div>

      <AgentStatusPanel status={status} recentActions={recentActions} online={online} />
      <EquipmentRegistryPanel />
      <DroneCatalogPanel />

      <HumanApprovalModal
        pending={pending}
        operatorName={operatorName}
        onDecide={(approvalId, decision) => decide(approvalId, operatorName, decision)}
      />
    </div>
  );
}
