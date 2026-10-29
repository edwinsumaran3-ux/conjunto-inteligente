/** Vista del grafo de conocimiento sobre canvas 2D: física en vivo, arrastre de nodos, tooltips, pulso en alertas y HiDPI. */
import { CAT_COLOR, CAT_LABEL, ForceGraph, GEdge, GNode } from "./graph";

export class GraphView {
  private ctx: CanvasRenderingContext2D; private fg: ForceGraph | null = null; private raf = 0; private running = false; private drag: GNode | null = null; private hover: GNode | null = null; private dpr = 1; private w = 300; private h = 300;
  constructor(private canvas: HTMLCanvasElement, private tip: HTMLElement, private onSelect: (n: GNode) => void) {
    this.ctx = canvas.getContext("2d")!;
    const pos = (e: PointerEvent) => { const b = canvas.getBoundingClientRect(); return { x: e.clientX - b.left, y: e.clientY - b.top }; };
    canvas.addEventListener("pointerdown", (e) => { if (!this.fg) return; const p = pos(e), n = this.fg.hit(p.x, p.y); if (n) { this.drag = n; n.fixed = true; canvas.setPointerCapture(e.pointerId); this.fg.reheat(0.4); this.moved = false; } });
    canvas.addEventListener("pointermove", (e) => {
      if (!this.fg) return; const p = pos(e);
      if (this.drag) { this.drag.x = p.x; this.drag.y = p.y; this.moved = true; this.fg.reheat(0.3); return; }
      const n = this.fg.hit(p.x, p.y); this.hover = n; canvas.style.cursor = n ? "pointer" : "default";
      if (n) { tip.hidden = false; tip.style.left = `${Math.min(p.x + 14, this.w - 200)}px`; tip.style.top = `${Math.max(p.y - 10, 4)}px`; tip.innerHTML = `<b>${n.label.replace(/</g, "&lt;")}</b><br><span style="color:var(--mut)">${CAT_LABEL[n.cat]}${n.ref ? " · " + String(n.ref).slice(0, 16) : ""}</span>`; } else tip.hidden = true;
    });
    canvas.addEventListener("pointerup", (e) => { if (this.drag) { const n = this.drag; if (!this.moved) this.onSelect(n); n.fixed = false; this.drag = null; canvas.releasePointerCapture(e.pointerId); } });
    canvas.addEventListener("pointerleave", () => { tip.hidden = true; this.hover = null; });
    new ResizeObserver(() => this.resize()).observe(canvas.parentElement!);
  }
  private moved = false;
  resize() { const p = this.canvas.parentElement!; const w = p.clientWidth, h = p.clientHeight; if (!w || !h) return; this.dpr = Math.min(window.devicePixelRatio || 1, 2); this.w = w; this.h = h; this.canvas.width = w * this.dpr; this.canvas.height = h * this.dpr; this.fg?.resize(w, h); }
  setModel(nodes: GNode[], edges: GEdge[]) { this.resize(); this.fg = new ForceGraph(nodes, edges, this.w, this.h); this.fg.run(120); }   // pre-asienta para que no “salte” al abrirse
  reheat() { this.fg?.reheat(0.9); }
  nodeCount() { return this.fg?.nodes.length ?? 0; }
  start() { if (this.running) return; this.running = true; const loop = () => { if (!this.running) return; this.fg?.tick(); this.draw(); this.raf = requestAnimationFrame(loop); }; loop(); }
  stop() { this.running = false; cancelAnimationFrame(this.raf); }
  private draw() {
    const c = this.ctx, fg = this.fg; c.setTransform(this.dpr, 0, 0, this.dpr, 0, 0); c.clearRect(0, 0, this.w, this.h); if (!fg) return;
    const by = new Map(fg.nodes.map((n) => [n.id, n])); const t = Date.now() / 500;
    for (const e of fg.edges) {
      const a = by.get(e.source), b = by.get(e.target); if (!a || !b) continue; c.beginPath(); c.moveTo(a.x, a.y); c.lineTo(b.x, b.y);
      c.strokeStyle = e.alert ? "#ef4444" : this.hover && (this.hover.id === a.id || this.hover.id === b.id) ? "#5b6b86" : "#273044"; c.lineWidth = e.alert ? 2 : 1.4; c.setLineDash(e.alert ? [5, 5] : []); c.stroke(); c.setLineDash([]);
      if (e.relation && this.hover && (this.hover.id === a.id || this.hover.id === b.id)) { c.fillStyle = "#5d6b82"; c.font = "9px system-ui"; c.textAlign = "center"; c.fillText(e.relation, (a.x + b.x) / 2, (a.y + b.y) / 2 - 3); }
    }
    for (const n of fg.nodes) {
      if (n.pulse) { c.beginPath(); c.arc(n.x, n.y, n.r + 6 + Math.sin(t) * 4, 0, Math.PI * 2); c.strokeStyle = "rgba(239,68,68,.35)"; c.lineWidth = 2; c.stroke(); }
      c.beginPath(); c.arc(n.x, n.y, n.r, 0, Math.PI * 2); c.fillStyle = "#11151f"; c.fill(); c.strokeStyle = CAT_COLOR[n.cat]; c.lineWidth = this.hover?.id === n.id ? 4 : 3; c.stroke();
      c.fillStyle = "#e2e8f0"; c.font = "10px system-ui"; c.textAlign = "center"; c.textBaseline = "middle"; const lab = n.label.length > 16 ? n.label.slice(0, 15) + "…" : n.label;
      const tw = c.measureText(lab).width; c.fillText(lab, Math.min(Math.max(n.x, tw / 2 + 4), this.w - tw / 2 - 4), n.y + n.r + 11);   // etiqueta bajo el nodo, sin salirse del lienzo
      c.fillStyle = CAT_COLOR[n.cat]; c.font = "bold 10px system-ui"; c.fillText(CAT_LABEL[n.cat][0], n.x, n.y + 0.5);
    }
  }
}
