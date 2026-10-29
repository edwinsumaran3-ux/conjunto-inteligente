// @vitest-environment node
import { describe, expect, it } from "vitest";
import { summarizeFloorHealth } from "./treeView";
import type { Health } from "./treeView";
import type { TreeNode } from "./spatial";

const tree: TreeNode = {
  expressID: 1, type: "IFCPROJECT", name: "Proyecto", globalId: null, children: [{
    expressID: 2, type: "IFCBUILDING", name: "Edificio", globalId: null, children: [
      { expressID: 3, type: "IFCBUILDINGSTOREY", name: "Nivel 1", globalId: null, children: [
        { expressID: 4, type: "IFCPUMP", name: "Bomba", globalId: "pump-1", children: [] },
        { expressID: 5, type: "IFCTANK", name: "Tanque", globalId: "tank-1", children: [] },
        { expressID: 6, type: "IFCVALVE", name: "Válvula", globalId: "valve-1", children: [] },
      ] },
      { expressID: 7, type: "IFCBUILDINGSTOREY", name: "Nivel 2", globalId: null, children: [
        { expressID: 8, type: "IFCPUMP", name: "Bomba sin vínculo", globalId: "pump-unlinked", children: [] },
      ] },
    ],
  }],
};

describe("salud agregada por piso", () => {
  it("resume severidades reales de los activos descendientes", () => {
    const health = new Map<string, Health>([["pump-1", "ok"], ["tank-1", "warn"], ["valve-1", "bad"]]);
    const floors = summarizeFloorHealth(tree, health);
    expect(floors.get(3)).toEqual({ linkedAssets: 3, ok: 1, warn: 1, bad: 1, status: "bad" });
  });

  it("mantiene un piso sin vínculos como sin datos y no como operativo", () => {
    const floors = summarizeFloorHealth(tree, new Map<string, Health>());
    expect(floors.get(3)).toEqual({ linkedAssets: 0, ok: 0, warn: 0, bad: 0, status: "none" });
    expect(floors.get(7)?.status).toBe("none");
  });

  it("prioriza alerta sobre activos operativos", () => {
    const health = new Map<string, Health>([["pump-1", "ok"], ["valve-1", "warn"]]);
    const floors = summarizeFloorHealth(tree, health);
    expect(floors.get(3)?.status).toBe("warn");
    expect(floors.get(3)?.linkedAssets).toBe(2);
  });
});