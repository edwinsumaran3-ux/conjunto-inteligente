// @vitest-environment node
// Integración REAL cliente-del-visor <-> API: se ejecuta solo si BIM_API_URL está definida (ver scripts/run_viewer_integration.sh).
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { Api } from "./api";

const URL = process.env.BIM_API_URL;
describe.skipIf(!URL)("visor <-> API real", () => {
  it("login -> importar IFC -> clic sin enlace (nodo técnico) -> enlazar a equipo -> clic resuelve al equipo operativo", async () => {
    const api = new Api(URL!, ""); const TANK = "13bz5Kktn94Ay9K8f9y71Q";
    await api.login(process.env.BIM_TENANT!, process.env.BIM_EMAIL!, process.env.BIM_PWD!); expect(api.token.length).toBeGreaterThan(20);
    const ifc = readFileSync(process.env.BIM_IFC ?? "bim/public/torre_demo.ifc", "utf8");
    const imp = await api.importIfc(ifc, "torre_demo.ifc"); expect(imp.model_version_id ?? imp.id ?? imp.model_id).toBeTruthy();

    const before = await api.lookup(TANK); expect(String(before.node_type)).toMatch(/^ifc/);                    // sin enlace: nodo técnico
    const created = await api.postJson("/nodes", { node_type: "equipment", code: "T1", name: "Tanque 1" });       // equipo operativo
    await api.linkElement(TANK, created.id);
    const after = await api.lookup(TANK); expect(after.node_id).toBe(created.id); expect(after.node_type).toBe("equipment");
    const d = await api.nodeDetail(created.id); expect(d.ifc.entity_type).toBe("IFCTANK"); expect(d.bindings.some((b: any) => b.identifier === TANK)).toBe(true);

    const g = await api.graph(); expect(g.nodes.some((n: any) => n.id === created.id)).toBe(true);
    const o = await api.overview(); expect(o.bim.models).toBeGreaterThanOrEqual(1); expect(o.bim.entities).toBeGreaterThan(100);
    const mv = (await api.modelVersions()).find((m: any) => m.has_file); expect(mv).toBeTruthy();
    const bytes = await api.modelFile(mv.id); expect(new TextDecoder().decode(bytes.slice(0, 13))).toBe("ISO-10303-21;");   // el visor descarga el IFC real
    await expect(api.lookup("GUID-INEXISTENTE")).rejects.toMatchObject({ status: 404 });
  });
});
