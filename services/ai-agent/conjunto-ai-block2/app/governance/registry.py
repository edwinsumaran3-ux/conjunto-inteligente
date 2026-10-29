from __future__ import annotations
from dataclasses import dataclass
from app.governance.contracts import AgentName


@dataclass(frozen=True)
class AgentContract:
    name: AgentName
    mission: str
    read_tools: frozenset[str]
    write_tools: frozenset[str]
    human_required_actions: frozenset[str]
    max_context_items: int = 100
    max_tool_calls: int = 20


COMMON_READ = frozenset({"get_asset_history", "get_area_by_keywords"})
CONTRACTS = {
    AgentName.RECEPTION: AgentContract(
        AgentName.RECEPTION,
        "clasificar solicitudes y derivar contexto",
        COMMON_READ,
        frozenset({"create_work_request"}),
        frozenset({"send", "close"}),
    ),
    AgentName.DIAGNOSTIC: AgentContract(
        AgentName.DIAGNOSTIC,
        "analizar fallas y evidencia técnica",
        COMMON_READ,
        frozenset({"create_diagnostic"}),
        frozenset({"close"}),
    ),
    AgentName.PROCUREMENT: AgentContract(
        AgentName.PROCUREMENT,
        "preparar compras, RFQ y comparativos",
        COMMON_READ | {"get_inventory"},
        frozenset({"create_purchase"}),
        frozenset({"approve", "pay", "send"}),
    ),
    AgentName.PLAN: AgentContract(
        AgentName.PLAN,
        "interpretar planos y relacionar elementos físicos",
        frozenset({"get_plan", "get_area_by_keywords"}),
        frozenset({"create_twin_relation"}),
        frozenset({"close"}),
    ),
    AgentName.MAINTENANCE: AgentContract(
        AgentName.MAINTENANCE,
        "priorizar mantenimiento y recomendar intervenciones",
        COMMON_READ | {"get_work_orders"},
        frozenset({"create_work_order"}),
        frozenset({"execute", "close"}),
    ),
    AgentName.VENDOR: AgentContract(
        AgentName.VENDOR,
        "evaluar proveedores contra criterios verificables",
        frozenset({"get_vendor_history", "get_purchase_history"}),
        frozenset({"create_vendor_evaluation"}),
        frozenset({"send"}),
    ),
    AgentName.INVENTORY: AgentContract(
        AgentName.INVENTORY,
        "analizar existencias, reservas y reposición",
        frozenset({"get_inventory", "get_asset_history"}),
        frozenset({"create_replenishment"}),
        frozenset({"approve"}),
    ),
    AgentName.FINANCE: AgentContract(
        AgentName.FINANCE,
        "analizar facturas, pagos y controles financieros",
        frozenset({"get_invoice", "get_account_balance"}),
        frozenset({"create_payment_proposal"}),
        frozenset({"approve", "pay"}),
    ),
    AgentName.SECURITY: AgentContract(
        AgentName.SECURITY,
        "correlacionar eventos de seguridad y proponer respuesta",
        frozenset({"get_incident", "get_camera_events", "get_sensor_events"}),
        frozenset({"create_incident"}),
        frozenset({"execute", "close", "send"}),
    ),
    AgentName.COMMUNICATION: AgentContract(
        AgentName.COMMUNICATION,
        "preparar comunicaciones con trazabilidad y aprobación",
        frozenset({"get_resident_context"}),
        frozenset({"send_notification"}),
        frozenset({"send"}),
    ),
    AgentName.REPORTING: AgentContract(
        AgentName.REPORTING,
        "generar informes a partir de datos confirmados",
        frozenset({"get_kpis", "get_audit_log"}),
        frozenset({"create_report"}),
        frozenset(),
    ),
    AgentName.COMPLIANCE: AgentContract(
        AgentName.COMPLIANCE,
        "verificar políticas, controles y evidencia",
        frozenset({"get_policy", "get_audit_log"}),
        frozenset({"create_compliance_finding"}),
        frozenset({"close"}),
    ),
    AgentName.SURVEILLANCE_ADVISOR: AgentContract(
        AgentName.SURVEILLANCE_ADVISOR,
        "asesorar sobre eventos de vigilancia y escalamiento",
        frozenset({"get_incident", "get_camera_events", "get_sensor_events"}),
        frozenset({"create_incident", "dispatch_drone"}),
        frozenset({"execute", "send", "close"}),
    ),
}


def get_contract(name: str) -> AgentContract:
    try:
        return CONTRACTS[AgentName(name)]
    except ValueError as exc:
        raise KeyError(f"Unknown agent: {name}") from exc


def authorize_tool(agent: str, tool: str, write: bool) -> bool:
    c = get_contract(agent)
    return tool in (c.write_tools if write else c.read_tools)
