/** Inspector del elemento: HTML del panel y gráfico de historial. Los Psets son los CRUDOS del archivo IFC; el resto, datos reales del gemelo. */
import { esc, icon, sevClass } from "./ui";
import type { Pset } from "./spatial";

export interface InspectorData { name: string; ifcType: string; globalId: string | null; detail: any | null; psets: Pset[]; }

const healthColor = (s: number) => (s >= 70 ? "var(--green)" : s >= 40 ? "var(--orange)" : "var(--red)");
type OverlayHealth = { score: number | null; sev: "ok" | "warn" | "bad" | null; anoms: number } | undefined;
type OverlayPoint = { name: string; value: number | null; canonical_unit?: string | null };

export function selectionLabelHtml(name: string, health: OverlayHealth, points: OverlayPoint[], visualProxy = false): string {
  const readings = points.filter((p) => typeof p.value === "number" && Number.isFinite(p.value)).slice(0, 2);
  const summary = readings.length
    ? readings.map((p) => `${esc(p.name)} ${new Intl.NumberFormat("es-CO", { maximumFractionDigits: 1 }).format(p.value!)}${p.canonical_unit ? ` ${esc(p.canonical_unit)}` : ""}`).join(" · ")
    : health?.score != null ? `Salud ${Math.round(health.score)}/100`
      : health?.anoms ? `${health.anoms} anomalía(s) abierta(s)`
        : health ? "Salud sin calcular" : "Sin telemetría enlazada";
  return `<strong>${esc(name)}</strong><span class="sel-label-meta ${health?.sev ?? "none"}">${summary}${visualProxy ? " · Proxy visual IFC" : ""}</span>`;
}

export function inspectorHtml(d: InspectorData): string {
  const n = d.detail?.node, h = d.detail?.health, pts: any[] = d.detail?.points ?? [], an: any[] = d.detail?.anomalies ?? [];
  const alertMetrics = new Set(an.map((a) => String(a.metric)));
  const psetProps = d.psets.flatMap((p) => p.props);
  const manufacturer = psetProps.find((p) => /manufacturer/i.test(p.name))?.value;
  const model = psetProps.find((p) => /model(label|reference|number)?/i.test(p.name))?.value;
  let html = `<div class="asset-hero"><div class="asset-symbol">${icon("cube", 21)}</div><div class="asset-copy"><span class="asset-kicker">FICHA TÉCNICA · IFC</span><h2>${esc(n?.name ?? d.name ?? "Elemento")}</h2><div class="asset-meta">${[manufacturer, model].filter(Boolean).map((v) => `<span>${esc(v)}</span>`).join("") || `<span>${esc(d.ifcType || "Elemento IFC")}</span>`}</div></div></div><div class="chips"><span class="chip">${esc(d.ifcType || "IFC")}</span>` +
    (d.globalId ? `<span class="chip" title="GlobalId">${esc(d.globalId.length > 14 ? d.globalId.slice(0, 13) + "…" : d.globalId)}<button data-copy="${esc(d.globalId)}" title="Copiar GlobalId" aria-label="Copiar GlobalId">${icon("copy", 11)}</button></span>` : "") +
    (n ? `<span class="chip ok">${icon("link", 11)} gemelo: ${esc(n.node_type)}</span>` : `<span class="chip">sin gemelo</span>`) +
    (h ? `<span class="chip ${sevClass(h.severity)}">salud ${esc(h.severity)}</span>` : "") + `</div></div>`;
  if (h) {
    const score = typeof h.health_score === "number" && Number.isFinite(h.health_score) ? h.health_score : null;
    const color = score == null ? "var(--mut)" : healthColor(score);
    const anomalies = Number(h.open_anomalies ?? 0);
    html += `<div class="health-card"><div class="health-ring" style="--health-color:${color};--health-angle:${score == null ? 0 : Math.max(0, Math.min(100, score)) * 3.6}deg"><span>${score == null ? "—" : Math.round(score)}</span><small>${score == null ? "" : "/100"}</small></div><div class="health-copy"><span>Salud operacional</span><strong>${score == null ? "Sin calcular" : score >= 70 ? "En rango" : score >= 40 ? "Requiere atención" : "Crítico"}</strong><small>${anomalies} anomalía(s) abierta(s) · ${esc(h.severity ?? "sin severidad")}</small></div></div>`;
  }
  if (pts.length) {
    html += `<div class="sensor-data">` + pts.map((p, i) => `<div class="sensor-card${alertMetrics.size && /temp|vib|pres|flow/i.test(p.name + p.code) && alertMetrics.size ? " alert" : ""}${i === 0 ? " sel" : ""}" data-p="${p.id}" tabindex="0" role="button" aria-label="Ver historial de ${esc(p.name)}">` +
      `<h4>${icon(/temp/i.test(p.name) ? "thermo" : /power|energy|watt/i.test(p.name) ? "bolt" : "dot", 15)}${esc(p.name)}</h4><div class="value">${typeof p.value === "number" && Number.isFinite(p.value) ? new Intl.NumberFormat("es-CO", { maximumFractionDigits: 1 }).format(p.value) : "—"}<small> ${esc(p.canonical_unit ?? "")}</small></div><small>${esc(p.quality ?? "sin dato")}</small></div>`).join("") + `</div>`;
    html += `<div class="spark-box"><div class="spark-bar"><span id="spark-title">Historial del punto</span><select id="spark-range" aria-label="Rango del historial"><option value="60">1 h</option><option value="240">4 h</option><option value="1440" selected>24 h</option></select></div><canvas id="spark" class="sp" aria-label="Serie histórica de telemetría"></canvas><small class="data-source">Serie recibida del gemelo digital</small></div>`;
  } else html += `<div class="connection-hint">${icon("wifi", 17)}<div><strong>${n ? "Sin puntos de telemetría" : "Sin telemetría enlazada"}</strong><span>${n ? "Este nodo no tiene puntos asociados." : "Conecta este elemento a un nodo del gemelo para consultar lecturas e historial."}</span></div></div>`;
  if (n) {
    html += `<h3 class="sec">${icon("share", 13)} Gemelo digital</h3><div class="row"><span>Estado</span><span>${esc(n.status)}</span></div><div class="row"><span>Código</span><span class="mono">${esc(n.code)}</span></div>` +
      `<div class="row"><span>Aguas arriba</span><span>${d.detail.dependencies.upstream.length}</span></div><div class="row"><span>Aguas abajo</span><span>${d.detail.dependencies.downstream.length}</span></div>`;
    if (an.length) html += `<h3 class="sec">${icon("alert", 13)} Anomalías</h3>` + an.map((a) => `<div class="row"><span>${esc(a.metric)}</span><span class="sev-${sevClass(a.severity)}">${esc(a.severity)}</span></div>`).join("");
  }
  html += `<h3 class="sec">${icon("info", 13)} Property Sets (IFC)</h3>`;
  html += d.psets.length ? d.psets.map((p, i) => `<details class="pset"${i === 0 ? " open" : ""}><summary>${esc(p.set)}<span class="n">${p.props.length}</span></summary>${p.props.map((x) => `<div class="row"><span>${esc(x.name)}</span><span class="mono">${esc(x.value)}${x.unit ? " " + esc(x.unit) : ""}</span></div>`).join("")}</details>`).join("")
    : `<div class="muted">El elemento no declara Property Sets en el archivo.</div>`;
  const api = Object.entries(d.detail?.ifc?.properties ?? {}); if (api.length) html += `<details class="pset"><summary>Propiedades importadas al gemelo<span class="n">${api.length}</span></summary>${api.map(([k, v]) => `<div class="row"><span>${esc(k.split(".").pop())}</span><span class="mono">${esc(v)}</span></div>`).join("")}</details>`;
  return html + `<div id="linkbox"></div>`;
}

/** Gráfico de historial con ejes mínimos, etiqueta de último valor y punto final. */
export function drawSeries(canvas: HTMLCanvasElement, values: number[], unit = "") {
  const dpr = Math.min(window.devicePixelRatio || 1, 2), w = canvas.clientWidth || 300, h = 70; canvas.width = w * dpr; canvas.height = h * dpr; const x = canvas.getContext("2d")!; x.setTransform(dpr, 0, 0, dpr, 0, 0); x.clearRect(0, 0, w, h);
  x.font = "10px system-ui"; x.fillStyle = "#9aa9a2"; if (values.length < 2) { x.fillText("Sin datos suficientes en el rango", 8, 36); return; }
  const lo = Math.min(...values), hi = Math.max(...values), pad = 6, span = hi - lo || 1; const X = (i: number) => pad + (i / (values.length - 1)) * (w - pad * 2 - 34), Y = (v: number) => h - 12 - ((v - lo) / span) * (h - 26);
  x.strokeStyle = "#36433e"; x.lineWidth = 1; [lo, (lo + hi) / 2, hi].forEach((v) => { x.beginPath(); x.moveTo(pad, Y(v)); x.lineTo(w - pad - 34, Y(v)); x.stroke(); });
  const grad = x.createLinearGradient(0, 0, 0, h); grad.addColorStop(0, "rgba(101,169,255,.35)"); grad.addColorStop(1, "rgba(101,169,255,0)");
  x.beginPath(); values.forEach((v, i) => (i ? x.lineTo(X(i), Y(v)) : x.moveTo(X(i), Y(v)))); x.lineTo(X(values.length - 1), h - 12); x.lineTo(X(0), h - 12); x.closePath(); x.fillStyle = grad; x.fill();
  x.beginPath(); values.forEach((v, i) => (i ? x.lineTo(X(i), Y(v)) : x.moveTo(X(i), Y(v)))); x.strokeStyle = "#65a9ff"; x.lineWidth = 2; x.stroke();
  const last = values[values.length - 1]; x.beginPath(); x.arc(X(values.length - 1), Y(last), 4, 0, Math.PI * 2); x.fillStyle = "#f4b85f"; x.fill();
  x.fillStyle = "#e5ece8"; x.textAlign = "left"; x.fillText(`${Math.round(last * 10) / 10}${unit ? " " + unit : ""}`, w - 34 - pad + 4, Y(last) + 3); x.fillStyle = "#9aa9a2"; x.fillText(String(Math.round(hi * 10) / 10), pad, 10); x.fillText(String(Math.round(lo * 10) / 10), pad, h - 1);
}
