// @vitest-environment node
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import * as IFC from "web-ifc";
import { IfcAPI } from "web-ifc";
import { describe, expect, it } from "vitest";
import { classifyMepDiscipline, extractMepNetwork, summarizeMepLayers } from "./mep";
import type { MepMeshIdentity } from "./mep";
import { openIfc } from "./ifcGeometry";

function fakeIfcApi() {
  const lines = new Map<number, any>([
    [100, { GlobalId: { value: "gas-system" }, Name: { value: "Gas principal" }, PredefinedType: { value: "GAS" } }],
    [101, { GlobalId: { value: "power-system" }, Name: { value: "Electrical power" }, PredefinedType: { value: "POWER" } }],
    [102, { GlobalId: { value: "water-system" }, Name: { value: "Agua potable" }, PredefinedType: { value: "WATER" } }],
    [103, { GlobalId: { value: "hvac-system" }, Name: { value: "HVAC ventilation" }, PredefinedType: { value: "VENTILATION" } }],
    [200, { RelatingGroup: { value: 100 }, RelatedObjects: [{ value: 1 }, { value: 2 }] }],
    [201, { RelatingGroup: { value: 101 }, RelatedObjects: [{ value: 3 }, { value: 4 }] }],
    [202, { RelatingGroup: { value: 102 }, RelatedObjects: [{ value: 5 }, { value: 6 }] }],
    [203, { RelatingGroup: { value: 103 }, RelatedObjects: [{ value: 7 }] }],
    [300, { RelatingElement: { value: 1 }, RelatedElement: { value: 2 } }],
    [301, { RelatingPort: { value: 50 }, RelatedElement: { value: 5 } }],
    [302, { RelatingPort: { value: 60 }, RelatedElement: { value: 6 } }],
    [303, { RelatingPort: { value: 50 }, RelatedPort: { value: 60 } }],
  ]);
  const names = new Map<number, string>([
    [100, "IFCDISTRIBUTIONSYSTEM"], [101, "IFCDISTRIBUTIONCIRCUIT"], [102, "IFCDISTRIBUTIONSYSTEM"], [103, "IFCDISTRIBUTIONSYSTEM"],
  ]);
  const types = new Map<number, number>([
    [100, IFC.IFCDISTRIBUTIONSYSTEM], [101, IFC.IFCDISTRIBUTIONCIRCUIT], [102, IFC.IFCDISTRIBUTIONSYSTEM], [103, IFC.IFCDISTRIBUTIONSYSTEM],
  ]);
  const vectors = new Map<number, number[]>([
    [IFC.IFCDISTRIBUTIONSYSTEM, [100, 102, 103]], [IFC.IFCDISTRIBUTIONCIRCUIT, [101]],
    [IFC.IFCRELASSIGNSTOGROUP, [200, 201, 202, 203]], [IFC.IFCRELCONNECTSELEMENTS, [300]],
    [IFC.IFCRELCONNECTSPORTTOELEMENT, [301, 302]], [IFC.IFCRELCONNECTSPORTS, [303]],
  ]);
  return {
    GetLine: (_modelID: number, id: number) => lines.get(id),
    GetLineIDsWithType: (_modelID: number, type: number) => { const values = vectors.get(type) ?? []; return { size: () => values.length, get: (index: number) => values[index] }; },
    GetLineType: (_modelID: number, id: number) => types.get(id) ?? 0,
    GetNameFromTypeCode: (type: number) => [...names].find(([id]) => types.get(id) === type)?.[1] ?? "IFCUNKNOWN",
  } as unknown as IfcAPI;
}

const meshes: MepMeshIdentity[] = [
  { expressID: 1, globalId: "pipe-gas", ifcType: "IFCPIPESEGMENT", name: "Gas pipe" },
  { expressID: 2, globalId: "valve-gas", ifcType: "IFCVALVE", name: "Gas valve" },
  { expressID: 3, globalId: "cable-1", ifcType: "IFCCABLESEGMENT", name: "Power cable" },
  { expressID: 4, globalId: "panel-1", ifcType: "IFCELECTRICDISTRIBUTIONBOARD", name: "Main panel" },
  { expressID: 5, globalId: "pump-water", ifcType: "IFCPUMP", name: "Water pump" },
  { expressID: 6, globalId: "tank-water", ifcType: "IFCTANK", name: "Water tank" },
  { expressID: 7, globalId: "duct-hvac", ifcType: "IFCDUCTSEGMENT", name: "Supply duct" },
];

describe("topología MEP desde IFC", () => {
  it("clasifica sistemas y componentes por sus relaciones de grupo IFC", () => {
    const network = extractMepNetwork(fakeIfcApi(), 1, meshes);
    expect(network.systems.map((system) => system.discipline).sort()).toEqual(["electrical", "gas", "hvac", "water"]);
    expect(network.components.find((component) => component.expressID === 1)?.discipline).toBe("gas");
    expect(network.components.find((component) => component.expressID === 3)?.discipline).toBe("electrical");
    expect(network.components.find((component) => component.expressID === 5)?.discipline).toBe("water");
    expect(network.components.find((component) => component.expressID === 7)?.discipline).toBe("hvac");
  });

  it("reconoce conexiones directas y conexiones de puerto a puerto", () => {
    const network = extractMepNetwork(fakeIfcApi(), 1, meshes);
    expect(network.connections).toEqual([
      { fromExpressID: 1, toExpressID: 2, relation: "connects-elements" },
      { fromExpressID: 5, toExpressID: 6, relation: "connects-ports" },
    ]);
  });

  it("resume capas por componentes asignados, no por geometría adivinada", () => {
    const network = extractMepNetwork(fakeIfcApi(), 1, meshes);
    expect(summarizeMepLayers(network)).toEqual({
      counts: { water: 2, gas: 2, electrical: 2, hvac: 1, fire: 0 },
      systems: 4, connections: 2, unclassified: 0,
    });
  });

  it("no adivina el sistema de tuberías genéricas sin asignación IFC", () => {
    expect(classifyMepDiscipline("IFCPIPESEGMENT", ["Pipe segment"])).toBe("unknown");
  });

  it("reporta el IFC demo sin redes asignadas, aunque tenga bomba y tanque", async () => {
    const api = new IfcAPI(); api.SetWasmPath(process.cwd() + "/node_modules/web-ifc/", true); await api.Init();
    const file = new Uint8Array(readFileSync(resolve("bim/public/torre_demo.ifc")));
    const loaded = await openIfc(api, file), network = extractMepNetwork(api, loaded.modelID, loaded.meshes);
    expect(network.systems).toHaveLength(0);
    expect(network.connections).toHaveLength(0);
    expect(network.components.map((component) => component.discipline)).toEqual(["unknown", "unknown"]);
    expect(summarizeMepLayers(network).unclassified).toBe(2);
    api.CloseModel(loaded.modelID);
  });
});