/** Extracción de geometría IFC con web-ifc, sin depender de three (se prueba en Node con vitest). */
import { IfcAPI } from "web-ifc";
import { extractMepNetwork, MepNetwork } from "./mep";

export interface RawMesh {
  expressID: number;
  globalId: string | null;
  ifcType: string;
  name: string | null;
  positions: Float32Array; // xyz
  normals: Float32Array; // xyz
  indices: Uint32Array;
  matrix: number[]; // 4x4 column-major (flatTransformation)
  color: [number, number, number, number];
}
export interface IfcLoadResult { modelID: number; schema: string; meshes: RawMesh[]; mep: MepNetwork; api: IfcAPI; }

const val = (x: any): string | null => (x && typeof x === "object" && "value" in x ? String(x.value) : null);

export async function openIfc(api: IfcAPI, data: Uint8Array): Promise<IfcLoadResult> {
  const modelID = api.OpenModel(data);
  if (modelID < 0) throw new Error("web-ifc no pudo abrir el archivo IFC");
  const meshes: RawMesh[] = [];
  api.StreamAllMeshes(modelID, (flat) => {
    let line: any = null;
    try { line = api.GetLine(modelID, flat.expressID); } catch { /* entidad sin atributos legibles */ }
    const globalId = val(line?.GlobalId);
    const name = val(line?.Name);
    // Nombre de clase por el CÓDIGO de tipo de web-ifc (constructor.name se minifica en el bundle: salía «J1» en el navegador)
    const ifcType = (api.GetNameFromTypeCode(api.GetLineType(modelID, flat.expressID)) || "IFC").toUpperCase();
    for (let i = 0; i < flat.geometries.size(); i++) {
      const g = flat.geometries.get(i);
      const geom = api.GetGeometry(modelID, g.geometryExpressID);
      const v = api.GetVertexArray(geom.GetVertexData(), geom.GetVertexDataSize());
      const idx = api.GetIndexArray(geom.GetIndexData(), geom.GetIndexDataSize());
      const n = v.length / 6; // intercalado: x y z nx ny nz
      const positions = new Float32Array(n * 3), normals = new Float32Array(n * 3);
      for (let k = 0; k < n; k++) {
        positions.set(v.subarray(k * 6, k * 6 + 3), k * 3);
        normals.set(v.subarray(k * 6 + 3, k * 6 + 6), k * 3);
      }
      meshes.push({ expressID: flat.expressID, globalId, ifcType, name, positions, normals, indices: Uint32Array.from(idx),
        matrix: Array.from(g.flatTransformation), color: [g.color.x, g.color.y, g.color.z, g.color.w] });
      geom.delete?.();
    }
  });
  const mep = extractMepNetwork(api, modelID, meshes);
  return { modelID, schema: api.GetModelSchema(modelID), meshes, mep, api };
}

export function boundsOf(meshes: RawMesh[]): { min: [number, number, number]; max: [number, number, number] } | null {
  const min: [number, number, number] = [Infinity, Infinity, Infinity], max: [number, number, number] = [-Infinity, -Infinity, -Infinity];
  for (const m of meshes) {
    const t = m.matrix;
    for (let i = 0; i < m.positions.length; i += 3) {
      const x = m.positions[i], y = m.positions[i + 1], z = m.positions[i + 2];
      const w = [t[0] * x + t[4] * y + t[8] * z + t[12], t[1] * x + t[5] * y + t[9] * z + t[13], t[2] * x + t[6] * y + t[10] * z + t[14]];
      for (let a = 0; a < 3; a++) { min[a] = Math.min(min[a], w[a]); max[a] = Math.max(max[a], w[a]); }
    }
  }
  return Number.isFinite(min[0]) ? { min, max } : null;
}
