// @vitest-environment node
import { describe, expect, it } from "vitest";
import { inspectorHtml, selectionLabelHtml } from "./inspector";
import type { InspectorData } from "./inspector";

const base: InspectorData = {
  name: "Bomba de presurización B1",
  ifcType: "IFCPUMP",
  globalId: "3tQ5UgSD11VOwa7ZfyDW$n",
  detail: null,
  psets: [{ set: "Pset_ManufacturerTypeInformation", props: [{ name: "Manufacturer", value: "Grundfos" }, { name: "ModelLabel", value: "CR 32-160" }] }],
};

describe("presentación contextual de activos", () => {
  it("muestra fabricante y modelo procedentes de los Psets IFC", () => {
    const html = inspectorHtml(base);
    expect(html).toContain("Grundfos");
    expect(html).toContain("CR 32-160");
    expect(html).toContain("Sin telemetría enlazada");
  });

  it("representa un score de salud null sin producir NaN", () => {
    const html = inspectorHtml({ ...base, detail: { health: { health_score: null, severity: null, open_anomalies: 0 } } });
    expect(html).toContain("Sin calcular");
    expect(html).toContain(">—</span>");
    expect(html).not.toContain("NaN");
  });

  it("solo publica lecturas reales en la etiqueta 3D y escapa el contenido IFC", () => {
    const html = selectionLabelHtml("Bomba <B1>", undefined, [{ name: "Presión", value: 3.26, canonical_unit: "bar" }]);
    expect(html).toContain("Bomba &lt;B1&gt;");
    expect(html).toContain("3,3 bar");
    expect(selectionLabelHtml("Bomba B1", undefined, [])).toContain("Sin telemetría enlazada");
    expect(selectionLabelHtml("Bomba B1", undefined, [], true)).toContain("Proxy visual IFC");
  });
});