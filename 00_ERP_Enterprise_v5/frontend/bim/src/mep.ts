import {
  IfcAPI,
  IFCDISTRIBUTIONCIRCUIT,
  IFCDISTRIBUTIONSYSTEM,
  IFCRELASSIGNSTOGROUP,
  IFCRELCONNECTSELEMENTS,
  IFCRELCONNECTSPORTS,
  IFCRELCONNECTSPORTTOELEMENT,
} from "web-ifc";

export type MepDiscipline = "water" | "gas" | "electrical" | "hvac" | "fire" | "unknown";
export const MEP_DISCIPLINES = ["water", "gas", "electrical", "hvac", "fire"] as const;
export type MepLayer = (typeof MEP_DISCIPLINES)[number];
export const MEP_LAYER_COLORS: Record<MepLayer, number> = { water: 0x47a9ff, gas: 0xffa15b, electrical: 0xffd166, hvac: 0x9b93ff, fire: 0xff646f };
export interface MepMeshIdentity { expressID: number; globalId: string | null; ifcType: string; name: string | null; }
export interface MepComponent extends MepMeshIdentity { discipline: MepDiscipline; systemExpressIDs: number[]; }
export interface MepSystem { expressID: number; globalId: string | null; name: string; discipline: MepDiscipline; componentExpressIDs: number[]; }
export interface MepConnection { fromExpressID: number; toExpressID: number; relation: "connects-elements" | "connects-ports"; }
export interface MepNetwork { systems: MepSystem[]; components: MepComponent[]; connections: MepConnection[]; }
export interface MepLayerSummary { counts: Record<MepLayer, number>; systems: number; connections: number; unclassified: number; }

interface IfcReader {
  GetLine(modelID: number, expressID: number): any;
  GetLineIDsWithType(modelID: number, type: number, includeInherited?: boolean): { size(): number; get(index: number): number };
  GetLineType(modelID: number, expressID: number): number;
  GetNameFromTypeCode(type: number): string;
}

const COMPONENT_TYPES = /^(IFC(PIPE|CABLE|DUCT|FLOW|VALVE|PUMP|TANK|FAN|AIRTERMINAL|ELECTRIC|SANITARY|DISTRIBUTION))/;
const text = (value: unknown): string => {
  if (value == null) return "";
  if (typeof value === "object" && "value" in value) return String((value as { value: unknown }).value ?? "");
  return String(value);
};
const refId = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (value && typeof value === "object" && "value" in value) return refId((value as { value: unknown }).value);
  if (value && typeof value === "object" && "expressID" in value) return refId((value as { expressID: unknown }).expressID);
  return null;
};
const refs = (value: unknown): number[] => (Array.isArray(value) ? value : value == null ? [] : [value]).map(refId).filter((id): id is number => id != null);
const relationIDs = (api: IfcReader, modelID: number, type: number, includeInherited = true): number[] => {
  const ids = api.GetLineIDsWithType(modelID, type, includeInherited);
  return Array.from({ length: ids.size() }, (_, index) => ids.get(index));
};

export function classifyMepDiscipline(ifcType: string, descriptors: string[] = []): MepDiscipline {
  const type = ifcType.toUpperCase(), label = descriptors.join(" ").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  if (/\b(gas|fuel|combustible|naturalgas|lpg)\b/.test(label)) return "gas";
  if (/\b(fire|sprinkler|fireprotection)\b/.test(label)) return "fire";
  if (/\b(electric|electrical|power|lighting|cable|wire|communication|data|control)\b/.test(label) || /^IFC(CABLE|ELECTRIC|LIGHTING)/.test(type)) return "electrical";
  if (/\b(hvac|ventilation|air|cooling|heating|refrigeration|duct)\b/.test(label) || /^IFC(DUCT|FAN|AIRTERMINAL)/.test(type)) return "hvac";
  if (/\b(water|potable|domestic|plumbing|drain|wastewater|sewage|sanitary|hydronic)\b/.test(label)) return "water";
  if (/^IFCSANITARY/.test(type)) return "water";
  return "unknown";
}

export function summarizeMepLayers(network: MepNetwork): MepLayerSummary {
  const counts: Record<MepLayer, number> = { water: 0, gas: 0, electrical: 0, hvac: 0, fire: 0 };
  let unclassified = 0;
  for (const component of network.components) {
    if (component.discipline === "unknown" || component.systemExpressIDs.length === 0) { unclassified++; continue; }
    counts[component.discipline]++;
  }
  return { counts, systems: network.systems.length, connections: network.connections.length, unclassified };
}

export function extractMepNetwork(api: IfcAPI, modelID: number, meshes: readonly MepMeshIdentity[]): MepNetwork {
  const reader = api as unknown as IfcReader, components = new Map<number, MepComponent>();
  for (const mesh of meshes) {
    const type = mesh.ifcType.toUpperCase();
    if (!COMPONENT_TYPES.test(type)) continue;
    const line = reader.GetLine(modelID, mesh.expressID);
    components.set(mesh.expressID, {
      ...mesh,
      discipline: classifyMepDiscipline(type, [line?.Name, line?.ObjectType, line?.Description, line?.PredefinedType].map(text)),
      systemExpressIDs: [],
    });
  }

  const systems = new Map<number, MepSystem>();
  for (const systemID of [...relationIDs(reader, modelID, IFCDISTRIBUTIONSYSTEM), ...relationIDs(reader, modelID, IFCDISTRIBUTIONCIRCUIT)]) {
    const line = reader.GetLine(modelID, systemID), type = reader.GetNameFromTypeCode(reader.GetLineType(modelID, systemID));
    if (!/^IFCDISTRIBUTION(SYSTEM|CIRCUIT)$/.test(type)) continue;
    const name = text(line?.LongName) || text(line?.Name) || text(line?.ObjectType) || type;
    const descriptors = [name, line?.Description, line?.ObjectType, line?.PredefinedType].map(text);
    systems.set(systemID, { expressID: systemID, globalId: text(line?.GlobalId) || null, name, discipline: classifyMepDiscipline(type, descriptors), componentExpressIDs: [] });
  }

  for (const relationID of relationIDs(reader, modelID, IFCRELASSIGNSTOGROUP)) {
    const relation = reader.GetLine(modelID, relationID), systemID = refId(relation?.RelatingGroup), system = systemID == null ? undefined : systems.get(systemID);
    if (!system) continue;
    for (const componentID of refs(relation?.RelatedObjects)) {
      const component = components.get(componentID);
      if (!component) continue;
      system.componentExpressIDs.push(componentID); component.systemExpressIDs.push(system.expressID);
    }
  }
  for (const component of components.values()) {
    const disciplines = new Set(component.systemExpressIDs.map((id) => systems.get(id)?.discipline).filter((discipline): discipline is MepDiscipline => !!discipline && discipline !== "unknown"));
    if (disciplines.size === 1) component.discipline = [...disciplines][0];
    else if (disciplines.size > 1) component.discipline = "unknown";
  }

  const portOwners = new Map<number, number>();
  for (const relationID of relationIDs(reader, modelID, IFCRELCONNECTSPORTTOELEMENT)) {
    const relation = reader.GetLine(modelID, relationID), portID = refId(relation?.RelatingPort), elementID = refId(relation?.RelatedElement);
    if (portID != null && elementID != null && components.has(elementID)) portOwners.set(portID, elementID);
  }

  const connections: MepConnection[] = [], seen = new Set<string>();
  const addConnection = (fromExpressID: number | null, toExpressID: number | null, relation: MepConnection["relation"]) => {
    if (fromExpressID == null || toExpressID == null || fromExpressID === toExpressID || !components.has(fromExpressID) || !components.has(toExpressID)) return;
    const key = `${Math.min(fromExpressID, toExpressID)}:${Math.max(fromExpressID, toExpressID)}`;
    if (seen.has(key)) return; seen.add(key); connections.push({ fromExpressID, toExpressID, relation });
  };
  for (const relationID of relationIDs(reader, modelID, IFCRELCONNECTSELEMENTS)) {
    const relation = reader.GetLine(modelID, relationID);
    addConnection(refId(relation?.RelatingElement), refId(relation?.RelatedElement), "connects-elements");
  }
  for (const relationID of relationIDs(reader, modelID, IFCRELCONNECTSPORTS)) {
    const relation = reader.GetLine(modelID, relationID), from = portOwners.get(refId(relation?.RelatingPort) ?? -1), to = portOwners.get(refId(relation?.RelatedPort) ?? -1);
    addConnection(from ?? null, to ?? null, "connects-ports");
  }

  return { systems: [...systems.values()], components: [...components.values()], connections };
}