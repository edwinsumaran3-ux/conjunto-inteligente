// @vitest-environment node
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { IfcAPI } from "web-ifc";
import { openIfc, boundsOf } from "./ifcGeometry";

describe("carga IFC real (web-ifc WASM)", () => {
  it("extrae geometría de bomba, tanque, muros y losas con GlobalId", async () => {
    const api = new IfcAPI();
    api.SetWasmPath(resolve(__dirname, "../../node_modules/web-ifc") + "/", true);
    await api.Init();
    const data = new Uint8Array(readFileSync(resolve(__dirname, "../public/torre_demo.ifc")));
    const r = await openIfc(api, data);
    expect(r.schema).toBe("IFC4");
    const types = new Set(r.meshes.map((m) => m.globalId));
    expect(r.meshes.length).toBeGreaterThanOrEqual(17);       // 12 muros + 3 losas + bomba + tanque
    expect(types.has("3tQ5UgSD11VOwa7ZfyDW$n")).toBe(true);   // bomba
    expect(types.has("13bz5Kktn94Ay9K8f9y71Q")).toBe(true);   // tanque
    const pump = r.meshes.find((m) => m.globalId === "3tQ5UgSD11VOwa7ZfyDW$n")!;
    expect(pump.name).toContain("Bomba");
    expect(pump.indices.length % 3).toBe(0);
    const b = boundsOf(r.meshes)!;
    expect(b.max[0] - b.min[0]).toBeCloseTo(10, 1);            // 10 m de ancho (verificado también con ifcopenshell)
    expect(b.max[1] - b.min[1]).toBeCloseTo(9, 1);             // web-ifc entrega Y-up: 3 niveles = 9.0 m exactos
    api.CloseModel(r.modelID);
  });
  it("la clase IFC sale del código de tipo de web-ifc (no de constructor.name, que el bundle minifica: salía «J1»)", async () => {
    const api = new IfcAPI(); api.SetWasmPath(process.cwd() + "/node_modules/web-ifc/", true); await api.Init();
    const r = await openIfc(api, new Uint8Array(readFileSync("bim/public/torre_demo.ifc"))); const types = new Set(r.meshes.map((m) => m.ifcType));
    for (const t of ["IFCWALL", "IFCSLAB", "IFCPUMP", "IFCTANK"]) expect(types.has(t), t + " en " + [...types]).toBe(true); expect([...types].every((t) => /^IFC[A-Z]+$/.test(t))).toBe(true);
  });
});
