// @vitest-environment node
import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "node:fs";
import { IfcAPI } from "web-ifc";
import { buildSpatialTree, countElements, filterTree, readPsets, TreeNode } from "./spatial";

let api: IfcAPI, modelID: number, tree: TreeNode;
beforeAll(async () => {
  api = new IfcAPI(); api.SetWasmPath(process.cwd() + "/node_modules/web-ifc/", true); await api.Init();
  modelID = api.OpenModel(new Uint8Array(readFileSync("bim/public/torre_demo.ifc"))); tree = (await buildSpatialTree(api, modelID))!;
});
const flat = (t: TreeNode): TreeNode[] => [t, ...t.children.flatMap(flat)];

describe("estructura espacial real del IFC", () => {
  it("proyecto > sitio > edificio > niveles > elementos", () => {
    expect(tree.type).toBe("IFCPROJECT"); const types = flat(tree).map((n) => n.type);
    for (const t of ["IFCSITE", "IFCBUILDING", "IFCBUILDINGSTOREY", "IFCWALL", "IFCSLAB", "IFCPUMP", "IFCTANK"]) expect(types, t).toContain(t);
    expect(flat(tree).filter((n) => n.type === "IFCBUILDINGSTOREY")).toHaveLength(3);
  });
  it("los elementos traen nombre y GlobalId reales", () => {
    const pump = flat(tree).find((n) => n.type === "IFCPUMP")!; expect(pump.globalId).toBe("3tQ5UgSD11VOwa7ZfyDW$n"); expect(pump.name).toContain("Bomba");
    expect(countElements(tree)).toBeGreaterThanOrEqual(17);
  });
  it("la búsqueda conserva ancestros de las coincidencias", () => {
    const f = filterTree(tree, "bomba")!; expect(flat(f).some((n) => n.type === "IFCPUMP")).toBe(true); expect(flat(f).some((n) => n.type === "IFCBUILDING")).toBe(true);
    expect(flat(f).some((n) => n.type === "IFCTANK")).toBe(false); expect(filterTree(tree, "no-existe-xyz")).toBeNull(); expect(filterTree(tree, "3tQ5UgSD11VOwa7ZfyDW$n")).not.toBeNull();
  });
  it("Psets crudos del equipo (fabricante y modelo) leídos del archivo", async () => {
    const pump = flat(tree).find((n) => n.type === "IFCPUMP")!; const ps = await readPsets(api, modelID, pump.expressID);
    const m = ps.find((p) => p.set === "Pset_ManufacturerTypeInformation"); expect(m, JSON.stringify(ps)).toBeTruthy();
    expect(m!.props.find((p) => p.name === "Manufacturer")?.value).toBe("ACME"); expect(m!.props.find((p) => p.name === "ModelLabel")?.value).toBe("P-100");
  });
});
