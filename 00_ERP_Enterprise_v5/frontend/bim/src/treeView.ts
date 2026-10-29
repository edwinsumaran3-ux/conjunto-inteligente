/** Árbol espacial colapsable con búsqueda, selección activa y puntos de salud del gemelo. */
import { TreeNode, filterTree } from "./spatial";
import { esc, icon } from "./ui";
export type Health = "bad" | "warn" | "ok";
export interface FloorHealthSummary { linkedAssets: number; ok: number; warn: number; bad: number; status: Health | "none"; }

export function summarizeFloorHealth(tree: TreeNode | null, health: Map<string, Health>): Map<number, FloorHealthSummary> {
  const floors = new Map<number, FloorHealthSummary>();
  const visit = (node: TreeNode): Omit<FloorHealthSummary, "status"> => {
    const totals = { linkedAssets: 0, ok: 0, warn: 0, bad: 0 };
    const own = node.globalId ? health.get(node.globalId) : undefined;
    if (own) { totals.linkedAssets++; totals[own]++; }
    for (const child of node.children) {
      const childTotals = visit(child);
      totals.linkedAssets += childTotals.linkedAssets; totals.ok += childTotals.ok; totals.warn += childTotals.warn; totals.bad += childTotals.bad;
    }
    if (node.type.toUpperCase() === "IFCBUILDINGSTOREY") {
      floors.set(node.expressID, { ...totals, status: totals.bad ? "bad" : totals.warn ? "warn" : totals.linkedAssets ? "ok" : "none" });
    }
    return totals;
  };
  if (tree) visit(tree);
  return floors;
}

export class TreeView {
  private tree: TreeNode | null = null; private q = ""; private open = new Set<number>(); private active: number | null = null; private health = new Map<string, Health>(); private floors = new Map<number, FloorHealthSummary>(); private autoOpened = false;
  constructor(private host: HTMLElement, private onSelect: (n: TreeNode) => void) {
    host.addEventListener("click", (e) => {
      const el = (e.target as HTMLElement).closest<HTMLElement>("[data-id]"); if (!el) return; const id = Number(el.dataset.id);
      if ((e.target as HTMLElement).closest(".tw") && !(e.target as HTMLElement).closest(".tw.leaf")) { this.toggle(id); return; }
      const n = this.find(this.tree, id); if (n) { this.onSelect(n); if (n.children.length) this.open.add(id); this.render(); }
    });
  }
  setTree(t: TreeNode | null) { this.tree = t; this.floors = summarizeFloorHealth(t, this.health); this.autoOpened = false; this.open.clear(); if (t) { const walk = (n: TreeNode, d: number) => { if (d < 4 && n.children.length) this.open.add(n.expressID); n.children.forEach((c) => walk(c, d + 1)); }; walk(t, 0); } this.render(); }
  setHealth(m: Map<string, Health>) { this.health = m; this.floors = summarizeFloorHealth(this.tree, m); this.render(); }
  filter(q: string) { this.q = q; this.render(); }
  find(n: TreeNode | null, id: number): TreeNode | null { if (!n) return null; if (n.expressID === id) return n; for (const c of n.children) { const r = this.find(c, id); if (r) return r; } return null; }
  toggle(id: number) { this.open.has(id) ? this.open.delete(id) : this.open.add(id); this.render(); }
  setActive(id: number | null) {
    this.active = id; if (id != null && this.tree) { const path: number[] = []; const dfs = (n: TreeNode): boolean => { if (n.expressID === id) return true; for (const c of n.children) if (dfs(c)) { path.push(n.expressID); return true; } return false; }; dfs(this.tree); path.forEach((p) => this.open.add(p)); }
    this.render(); this.host.querySelector(".tree-node.active")?.scrollIntoView({ block: "nearest" });
  }
  private row(n: TreeNode, forceOpen: boolean): string {
    const kids = n.children.length > 0, isOpen = forceOpen || this.open.has(n.expressID), h = n.globalId ? this.health.get(n.globalId) : undefined;
    const floor = n.type.toUpperCase() === "IFCBUILDINGSTOREY" ? this.floors.get(n.expressID) : undefined;
    const status = h ?? floor?.status;
    const floorIndicator = floor ? `<span class="level-health${floor.linkedAssets ? "" : " empty"}" title="${floor.linkedAssets ? `${floor.linkedAssets} activos con salud · ${floor.ok} operativos · ${floor.warn} en atención · ${floor.bad} críticos` : "Sin activos con salud vinculada"}">${floor.linkedAssets ? `<i class="ok" style="flex:${floor.ok}"></i><i class="warn" style="flex:${floor.warn}"></i><i class="bad" style="flex:${floor.bad}"></i><small>${floor.linkedAssets}</small>` : "<small>Sin datos</small>"}</span>` : "";
    const ty = n.type.replace(/^IFC/, "").toLowerCase();
    return `<div class="tree-node${n.expressID === this.active ? " active" : ""}" data-id="${n.expressID}" role="treeitem" aria-expanded="${kids ? isOpen : "false"}" title="${esc(n.type)}${n.globalId ? " · " + esc(n.globalId) : ""}">` +
      `<span class="tw${kids ? (isOpen ? " open" : "") : " leaf"}">${icon("chevron", 12)}</span><span class="hd ${status ?? "none"}"></span><span class="nm">${esc(n.name)}</span>${floorIndicator}<span class="ty">${esc(ty)}</span></div>` +
      (kids && isOpen ? `<div class="tree-kids" role="group">${n.children.map((c) => this.row(c, forceOpen)).join("")}</div>` : "");
  }
  render() {
    if (!this.tree) { this.host.innerHTML = `<div class="empty-state">${icon("folder", 32)}<p>El modelo no declara estructura espacial.</p></div>`; return; }
    const t = filterTree(this.tree, this.q); if (!t) { this.host.innerHTML = `<div class="empty-state"><p>Sin coincidencias para «${esc(this.q)}».</p></div>`; return; }
    this.host.innerHTML = `<div role="tree">${this.row(t, !!this.q.trim())}</div>`;
  }
}
