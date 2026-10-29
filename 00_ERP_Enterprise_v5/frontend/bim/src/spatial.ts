/** Estructura espacial REAL del IFC (Proyecto > Sitio > Edificio > Nivel > elementos) y Property Sets crudos, con web-ifc. Sin three: se prueba en Node. */
import { IfcAPI } from "web-ifc";

export interface TreeNode { expressID: number; type: string; name: string; globalId: string | null; children: TreeNode[]; }
export interface PsetProp { name: string; value: string; unit?: string | null; }
export interface Pset { set: string; props: PsetProp[]; }

const v = (x: any): string | null => (x && typeof x === "object" && "value" in x && x.value != null ? String(x.value) : null);
const label = (line: any, fallback: string) => v(line?.LongName) ?? v(line?.Name) ?? fallback;

export async function buildSpatialTree(api: IfcAPI, modelID: number): Promise<TreeNode | null> {
  const root: any = await (api as any).properties.getSpatialStructure(modelID, false);   // asíncrona en web-ifc
  if (!root || root.expressID == null) return null;
  const walk = (n: any): TreeNode => {
    let line: any = null; try { line = api.GetLine(modelID, n.expressID); } catch { /* entidad sin atributos legibles */ }
    const type = String(n.type ?? line?.constructor?.name ?? "IFC").toUpperCase();
    return { expressID: n.expressID, type, name: label(line, type), globalId: v(line?.GlobalId), children: (n.children ?? []).map(walk) };
  };
  return walk(root);
}

export function countElements(t: TreeNode | null): number {
  if (!t) return 0; return t.children.length ? t.children.reduce((a, c) => a + countElements(c), 0) : 1;
}

/** Filtra el árbol conservando ancestros de las coincidencias (búsqueda por nombre, clase o GlobalId). */
export function filterTree(t: TreeNode, q: string): TreeNode | null {
  const s = q.trim().toLowerCase(); if (!s) return t;
  const hit = (n: TreeNode) => n.name.toLowerCase().includes(s) || n.type.toLowerCase().includes(s) || (n.globalId ?? "").toLowerCase() === s;
  const rec = (n: TreeNode): TreeNode | null => {
    const kids = n.children.map(rec).filter((x): x is TreeNode => !!x);
    return hit(n) || kids.length ? { ...n, children: hit(n) && !kids.length ? n.children : kids } : null;
  };
  return rec(t);
}

/** Property Sets y Quantity Sets crudos del elemento, tal como están en el archivo IFC. */
export async function readPsets(api: IfcAPI, modelID: number, expressID: number): Promise<Pset[]> {
  const out: Pset[] = [];
  let raw: any[] = [];
  try { raw = await (api as any).properties.getPropertySets(modelID, expressID, true); } catch { return out; }
  for (const ps of raw ?? []) {
    const props: PsetProp[] = [];
    for (const p of ps.HasProperties ?? ps.Quantities ?? []) {
      const val = v(p.NominalValue) ?? v(p.LengthValue) ?? v(p.AreaValue) ?? v(p.VolumeValue) ?? v(p.WeightValue) ?? v(p.CountValue);
      props.push({ name: v(p.Name) ?? "(sin nombre)", value: val ?? "—", unit: v(p.Unit) });
    }
    out.push({ set: v(ps.Name) ?? "(Pset sin nombre)", props });
  }
  return out;
}
