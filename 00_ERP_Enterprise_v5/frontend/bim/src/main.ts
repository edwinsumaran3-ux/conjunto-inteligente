import "./style.css";
import type * as THREE from "three";
import { IfcAPI } from "web-ifc";
import { openIfc } from "./ifcGeometry";
import { MEP_DISCIPLINES, MEP_LAYER_COLORS, MepLayer, MepNetwork, summarizeMepLayers } from "./mep";
import { Api, ApiError } from "./api";
import { Viewer, PickInfo } from "./scene3d";
import { buildSpatialTree, readPsets, TreeNode, countElements, Pset } from "./spatial";
import { TreeView, Health } from "./treeView";
import { GraphView } from "./graphView";
import { buildGraphModel, TwinGraph, TimelineStep, PointInfo, GNode } from "./graph";
import { toView, summarize, LivePoller, humanize, LIVE_TOPICS, LiveEvent } from "./workflow";
import { inspectorHtml, drawSeries, selectionLabelHtml } from "./inspector";
import { $, esc, icon, hydrateIcons, toast, sevClass } from "./ui";
import { AuthAttemptGate, clearAuthSession, readAuthSession, saveAuthSession } from "../../src/authSession";
import { configuredApiBase } from "../../src/apiBase";

hydrateIcons();
const initialSession = readAuthSession();
const api = new Api(configuredApiBase(), initialSession.token);
const E2E = new URLSearchParams(location.search).has("e2e");
$<HTMLInputElement>("api").value = api.base;
$<HTMLInputElement>("tok").value = api.token;
$<HTMLInputElement>("tenant").value = initialSession.tenantId;
$<HTMLInputElement>("email").value = initialSession.email;
const setMsg = (t: string) => { $("msg").textContent = t; };
let poller: LivePoller | null = null;
let authFailureNotified = false;
let loginPending = false;
let sessionValidated = false;
const authAttempts = new AuthAttemptGate();
function fail(e: unknown) {
  if (e instanceof ApiError && e.authVersion !== null && e.authVersion !== api.authVersion) return;
  if (e instanceof ApiError && e.status === 401 && e.path !== "/auth/login") {
    const failedToken = api.token;
    if (e.authVersion !== api.authVersion) return;
    const hadToken = Boolean(failedToken);
    authAttempts.begin();
    clearAuthSession(failedToken || undefined);
    api.token = "";
    sessionValidated = false;
    $<HTMLInputElement>("tok").value = "";
    setSessionUi();
    $("conn-panel").hidden = false;
    $("conn-toggle").setAttribute("aria-expanded", "true");
    poller?.stop();
    poller = null;
    if (!authFailureNotified) {
      const message = hadToken ? "Tu sesión venció. Inicia sesión para continuar." : "Inicia sesión para consultar el gemelo digital.";
      setMsg(message);
      toast(message, "bad", 6000);
      authFailureNotified = true;
      if (!modelLoaded) void loadSelected().then(() => setMsg(message));
    }
    console.error(e);
    return;
  }
  const m = e instanceof ApiError
    ? e.status === 401 && e.path === "/auth/login"
      ? "No se pudo iniciar sesión. Verifica el tenant, el correo y la contraseña."
      : `Error del API: ${e.message}`
    : `Error: ${(e as Error).message}`;
  setMsg(m); toast(m, "bad", 6000); console.error(e);
}

// ================= estado =================
const viewer = new Viewer($<HTMLCanvasElement>("cv"), $("view"));
let ifcApi: IfcAPI | null = null; let modelID = -1; let tree: TreeNode | null = null;
let twinGraph: TwinGraph | null = null; let steps: TimelineStep[] = []; let points: PointInfo[] = [];
let selExpress: number | null = null; let selNodeId: string | null = null; let showIfcNodes = false; let seq = 0;
const health = new Map<string, { node_id: string; name: string; score: number | null; sev: Health | null; anoms: number; worst: string | null }>();
const treeView = new TreeView($("ifc-tree"), (n) => selectTreeNode(n));
const ensureIfc = async () => { if (ifcApi) return ifcApi; ifcApi = new IfcAPI(); ifcApi.SetWasmPath(import.meta.env.BASE_URL, false); await ifcApi.Init(); return ifcApi; };
const loading = (on: boolean, t = "Procesando geometría…") => { $("loading").hidden = !on; $("loading-text").textContent = t; };

// ================= conexión y estado global =================
const connected = () => sessionValidated && !!api.token;
function setSessionUi() {
  const email = readAuthSession().email; $("avatar").textContent = email ? email.slice(0, 2).toUpperCase() : "—"; $("avatar").title = email || "Sin sesión";
  $("conn-label").textContent = connected() ? "Conectado" : "Conexión";
}
async function kpis() {
  const o = await api.overview(); const k = (v: unknown, l: string, c = "") => `<div class="k ${c}"><b>${esc(v ?? "—")}</b><span>${l}</span></div>`;
  const sev = o.open_anomalies_by_severity ?? {}; const crit = (sev.critical ?? 0) + (sev.high ?? 0), other = o.open_anomalies - crit;
  $("n-sensors").textContent = String(o.points.total); $("n-alerts").textContent = String(Math.max(0, other)); $("n-critical").textContent = String(crit);
  $("kpis").innerHTML = k(o.nodes_total, "Nodos gemelo") + k(o.bim.models, "Modelos BIM") + k(o.bim.entities, "Entidades IFC") + k(`${o.points.good}/${o.points.total}`, "Puntos OK", o.points.good < o.points.total ? "warn" : "") +
    k(`${o.devices.online}/${o.devices.total}`, "Dispositivos en línea") + k(o.open_anomalies, "Anomalías abiertas", o.open_anomalies ? "bad" : "") + k(o.health.avg == null ? "—" : Math.round(o.health.avg), "Salud promedio", o.health.avg != null && o.health.avg < 40 ? "bad" : "") +
    k(`${o.bim.ids_pass}/${o.bim.ids_pass + o.bim.ids_fail}`, "IDS cumplidos", o.bim.ids_fail ? "warn" : "") + k(o.pending_work_requests, "OT pendientes", o.pending_work_requests ? "warn" : "");
}
async function connect(candidateToken = $<HTMLInputElement>("tok").value.trim(), attempt = authAttempts.begin()) {
  if (loginPending && candidateToken !== api.token) return;
  if (!candidateToken) {
    setMsg("Inicia sesión o introduce un token válido para consultar el gemelo digital.");
    $("conn-panel").hidden = false;
    $("conn-toggle").setAttribute("aria-expanded", "true");
    return;
  }
  api.base = $<HTMLInputElement>("api").value.trim();
  sessionValidated = false;
  api.token = candidateToken;
  sessionStorage.setItem("bim.api", api.base);
  $<HTMLInputElement>("tok").value = candidateToken;
  const authVersion = api.authVersion;
  const isCurrent = () => authAttempts.isCurrent(attempt) && api.authVersion === authVersion && api.token === candidateToken;
  try {
    await kpis();
    if (!isCurrent()) return;
    sessionValidated = true;
    const previous = readAuthSession();
    saveAuthSession({
      token: candidateToken,
      tenantId: $<HTMLInputElement>("tenant").value.trim() || previous.tenantId,
      email: $<HTMLInputElement>("email").value.trim() || previous.email,
    });
    await refreshModels();
    if (!isCurrent()) return;
    setSessionUi();
    $("conn-panel").hidden = true;
    $("conn-toggle").setAttribute("aria-expanded", "false");
    setMsg("Conectado al gemelo digital.");
    toast("Conectado al gemelo digital", "ok");
    authFailureNotified = false;
    await Promise.all([colorize(), loadGraph(), loadAnoms()]);
    if (isCurrent()) await startLive(attempt, authVersion);
  } catch (e) {
    if (isCurrent()) fail(e);
  }
}
let modelLoaded = false;
async function refreshModels(selectNewest = false) {
  const mvs = await api.modelVersions(); const sel = $<HTMLSelectElement>("mv"); const prev = sel.value || "demo"; const withFile = mvs.filter((m) => m.has_file);
  sel.innerHTML = '<option value="demo">Modelo demo (torre_demo.ifc)</option>' + withFile.map((m) => `<option value="${m.id}">${esc(m.model_key)} v${esc(m.version)} · ${m.entity_count} ent.</option>`).join("");
  if (selectNewest && withFile[0]) sel.value = withFile[0].id; else if ([...sel.options].some((o) => o.value === prev)) sel.value = prev;
  if (selectNewest || !modelLoaded || sel.value !== prev) await loadSelected();     // no recarga el mismo modelo ya mostrado (evita parpadeo y trabajo inútil)
}
async function loadSelected() {
  const v = $<HTMLSelectElement>("mv").value || "demo";
  try { if (v === "demo") await showModel(new Uint8Array(await (await fetch(`${import.meta.env.BASE_URL}torre_demo.ifc`)).arrayBuffer()), "modelo demo"); else await showModel(await api.modelFile(v), "modelo del gemelo"); } catch (e) { loading(false); fail(e); }
}

function renderMepLayers(network: MepNetwork) {
  const summary = summarizeMepLayers(network), names: Record<MepLayer, string> = { water: "Agua", gas: "Gas", electrical: "Eléctrico", hvac: "HVAC", fire: "Incendio" };
  const color = (value: number) => `#${value.toString(16).padStart(6, "0")}`;
  const layers = $("mep-layers"); layers.hidden = false;
  layers.innerHTML = `<div class="mep-heading"><strong>Redes MEP</strong><span>${summary.systems} sistema(s) IFC</span></div>` +
    `<div class="mep-layer-list">${MEP_DISCIPLINES.map((layer) => {
      const count = summary.counts[layer], active = viewer.isMepLayerVisible(layer);
        const available = count > 0, pressed = available && active;
        return `<button type="button" class="mep-toggle${pressed ? " active" : ""}" data-mep-layer="${layer}" aria-pressed="${pressed}" title="${names[layer]} · ${count} componente(s) asignado(s)" ${available ? "" : "disabled"}><i style="--mep-color:${color(MEP_LAYER_COLORS[layer])}"></i>${names[layer]}<small>${count}</small></button>`;
    }).join("")}</div>` +
    `<div class="mep-summary">${summary.systems ? `${summary.connections} conexión(es) IFC verificadas` : "El IFC no contiene sistemas MEP agrupados"}${summary.unclassified ? ` · ${summary.unclassified} equipo(s) sin sistema` : ""}</div>`;
}

// ================= modelo =================
async function showModel(data: Uint8Array, label: string) {
  loading(true, `Procesando ${label}…`); const a = await ensureIfc(); if (modelID >= 0) { try { a.CloseModel(modelID); } catch { /* ya cerrado */ } }
  clearSelection(); const r = await openIfc(a, data); modelID = r.modelID; viewer.load(r); renderMepLayers(r.mep);
  if (!modelLoaded) { viewer.setXray(true); press("xray", true); }
  tree = await buildSpatialTree(a, modelID); treeView.setTree(tree); $("tree-count").textContent = `${countElements(tree)} elem.`;
  const [lo, hi] = viewer.heightRange(); void lo; void hi; setMsg(`${label}: ${r.meshes.length} elementos · ${r.schema}`); loading(false); modelLoaded = true;
  await colorize(); rebuildGraph(); if (E2E) (window as any).__bimReady?.();
}
const descendants = (n: TreeNode): number[] => [n.expressID, ...n.children.flatMap(descendants)];

// ================= salud del gemelo sobre el modelo =================
/** Estado visual = el PEOR entre la severidad de la anomalía abierta y el índice de salud (salud < 40 es crítica aunque la anomalía sea «media»). */
export const sevToHealth = (score: number | null, anoms: number, worst: string | null): Health | null => {
  const rank: Record<Health, number> = { ok: 0, warn: 1, bad: 2 }; let out: Health | null = null; const up = (h: Health) => { if (out == null || rank[h] > rank[out]) out = h; };
  if (anoms > 0) up(sevClass(worst) === "bad" ? "bad" : "warn"); if (score != null) up(score >= 70 ? "ok" : score >= 40 ? "warn" : "bad"); return out;
};
const HEX: Record<Health, number> = { bad: 0xe5484d, warn: 0xf0b429, ok: 0x2fbf71 };
async function colorize() {
  if (!connected()) return; let hm; try { hm = await api.healthMap(); } catch (e) { return fail(e); }
  viewer.clearTints(); health.clear(); const hmap = new Map<string, Health>();
  for (const e of hm) { const sev = sevToHealth(e.health_score, e.open_anomalies, e.worst_severity); health.set(e.global_id, { node_id: e.node_id, name: e.name, score: e.health_score, sev, anoms: e.open_anomalies, worst: e.worst_severity }); if (sev) { viewer.tint(e.global_id, HEX[sev]); hmap.set(e.global_id, sev); } }
  treeView.setHealth(hmap);
}
async function loadAnoms() {
  try { const a = await api.anomalies(60); $("anoms").innerHTML = a.length ? a.map((x: any) => `<div class="row"><span>${esc(x.node_name || x.node_code)} · ${esc(x.metric)}</span><span class="sev-${sevClass(x.severity)}">${esc(x.severity)}</span></div>`).join("") : '<div class="muted">Sin anomalías abiertas ✔</div>'; } catch (e) { fail(e); }
}

// ================= selección =================
function clearSelection() { selExpress = null; selNodeId = null; viewer.setSelection([]); $("sel-label").hidden = true; treeView.setActive(null); }
async function selectMeshes(ms: THREE.Mesh[], info: { name: string; ifcType: string; globalId: string | null; expressID: number | null }, fit = false) {
  viewer.setSelection(ms); selExpress = info.expressID; if (info.expressID != null) treeView.setActive(info.expressID); if (fit) viewer.fit(ms);
  points = [];
  const h = info.globalId ? health.get(info.globalId) : undefined; const lab = $("sel-label");
  const visualProxy = ms.some((mesh) => mesh.userData.visualProxy);
  const renderLabel = () => { lab.innerHTML = selectionLabelHtml(info.name || info.ifcType, h ? { score: h.score, sev: h.sev, anoms: h.anoms } : undefined, points, visualProxy); lab.className = `sel-label ${h?.sev === "bad" ? "bad" : h?.sev === "warn" ? "warn" : ""}`; };
  renderLabel(); lab.hidden = !ms.length; placeLabel();
  const token = ++seq; let psets: Pset[] = []; try { if (ifcApi && info.expressID != null) psets = await readPsets(ifcApi, modelID, info.expressID); } catch { /* sin psets */ }
  if (token !== seq) return; renderInspector({ ...info, psets }, null); activateTab("tab-inspector");
  if (!connected() || !info.globalId) return;
  try {
    const n = await api.lookup(info.globalId); if (token !== seq) return; selNodeId = n.node_id; const detail = await api.nodeDetail(n.node_id); if (token !== seq) return;
    points = (detail.points ?? []).map((p: any) => ({ id: p.id, name: p.name, value: p.value, canonical_unit: p.canonical_unit, quality: p.quality })); renderLabel(); renderInspector({ ...info, psets }, detail);
    if (String(n.node_type).startsWith("ifc")) await offerLink(info.globalId); else { await loadTimeline(n.node_id); rebuildGraph(); }
  } catch (e) { if (!(e instanceof ApiError && e.status === 404)) fail(e); else { selNodeId = null; $("detail").insertAdjacentHTML("beforeend", `<div class="muted" style="margin-top:12px">Este elemento no tiene nodo en el gemelo (importa el IFC con «materializar nodos»).</div>`); } }
}
function renderInspector(info: { name: string; ifcType: string; globalId: string | null; psets: Pset[] }, detail: any | null) {
  $("detail").innerHTML = inspectorHtml({ name: info.name, ifcType: info.ifcType, globalId: info.globalId, detail, psets: info.psets });
  $("detail").querySelectorAll<HTMLElement>("[data-copy]").forEach((b) => b.addEventListener("click", () => { void navigator.clipboard?.writeText(b.dataset.copy!); toast("GlobalId copiado", "ok", 1800); }));
  const cards = $("detail").querySelectorAll<HTMLElement>("[data-p]"); cards.forEach((c) => { const go = () => { cards.forEach((x) => x.classList.remove("sel")); c.classList.add("sel"); void spark(c.dataset.p!); }; c.addEventListener("click", go); c.addEventListener("keydown", (e) => { if (e.key === "Enter") go(); }); });
  const first = cards[0]; if (first) void spark(first.dataset.p!);
}
async function spark(pointId: string) {
  const minutes = Number(($("detail").querySelector("#spark-range") as HTMLSelectElement | null)?.value ?? 240); const c = $("detail").querySelector<HTMLCanvasElement>("#spark"); if (!c) return;
  try { const s = await api.series(pointId, minutes); const p = points.find((x) => x.id === pointId); const t = $("detail").querySelector("#spark-title"); if (t) t.textContent = `Historial · ${p?.name ?? ""}`; drawSeries(c, s.map((q: any) => q.value), p?.canonical_unit ?? ""); } catch (e) { fail(e); }
}
$("detail").addEventListener("change", (e) => { if ((e.target as HTMLElement).id === "spark-range") { const s = $("detail").querySelector<HTMLElement>(".sensor-card.sel"); if (s) void spark(s.dataset.p!); } });
async function selectTreeNode(n: TreeNode) {
  const ids = n.children.length ? descendants(n) : [n.expressID]; const ms = viewer.meshesOf(ids);
  await selectMeshes(ms, { name: n.name, ifcType: n.type, globalId: n.globalId, expressID: n.expressID }, true);
  if (n.children.length) { $("detail").insertAdjacentHTML("afterbegin", `<div class="chips" style="margin-bottom:10px"><span class="chip">${ms.length} elementos con geometría</span></div>`); }
}
async function pick(p: PickInfo) { await selectMeshes(viewer.byExpress.get(p.expressID) ?? [p.mesh], { name: p.name, ifcType: p.ifcType, globalId: p.globalId, expressID: p.expressID }); }
async function selectByGlobalId(gid: string, fit = true) { const ms = viewer.byGlobal.get(gid); if (!ms?.length) return false; const u = ms[0].userData; await selectMeshes(ms, { name: u.name, ifcType: u.ifcType, globalId: gid, expressID: u.expressID }, fit); return true; }

// ================= enlace geometría <-> equipo operativo =================
async function offerLink(globalId: string) {
  let nodes: any[] = []; try { nodes = (twinGraph ?? (twinGraph = await api.graph())).nodes.filter((n) => !String(n.node_type).startsWith("ifc") && !["site", "building", "floor", "storey", "space", "zone"].includes(n.node_type)); } catch (e) { return fail(e); }
  const box = $("linkbox"); box.innerHTML = `<div class="linkbox"><h3>${icon("link", 14)} Enlazar con equipo</h3><div class="muted">Este elemento aún no está enlazado a un equipo del gemelo: al enlazarlo mostrará salud, telemetría y anomalías.</div>
    <select id="lnk" aria-label="Equipo operativo">${nodes.length ? nodes.map((n) => `<option value="${n.id}">${esc(n.name)} · ${esc(n.node_type)} (${esc(n.code)})</option>`).join("") : "<option value=''>No hay equipos operativos</option>"}</select>
    <button id="lnkgo" class="btn primary wide" ${nodes.length ? "" : "disabled"}>Enlazar</button></div>`;
  $("lnkgo").onclick = async () => { const nid = $<HTMLSelectElement>("lnk").value; if (!nid) return;
    try { await api.linkElement(globalId, nid); toast("Elemento enlazado: ahora muestra datos del equipo", "ok"); await colorize(); await selectByGlobalId(globalId, false); } catch (e) { fail(e); } };
}

// ================= puntero: clic, tooltip y etiqueta =================
const cv = $<HTMLCanvasElement>("cv"); let down = [0, 0]; let hoverRaf = 0;
cv.addEventListener("pointerdown", (e) => { down = [e.clientX, e.clientY]; });
cv.addEventListener("pointerup", (e) => { if (Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return; const p = viewer.pickAt(e.clientX, e.clientY); if (p) void pick(p); else { clearSelection(); } });
cv.addEventListener("pointermove", (e) => {
  if (hoverRaf) return; hoverRaf = requestAnimationFrame(() => { hoverRaf = 0; if (e.buttons) { $("tooltip3d").classList.add("hidden"); return; }
    const p = viewer.pickAt(e.clientX, e.clientY), tt = $("tooltip3d"); if (!p) { tt.classList.add("hidden"); cv.style.cursor = "default"; return; } cv.style.cursor = "pointer";
    const h = p.globalId ? health.get(p.globalId) : undefined, b = $("view").getBoundingClientRect(); tt.classList.remove("hidden"); tt.style.left = `${e.clientX - b.left}px`; tt.style.top = `${e.clientY - b.top}px`;
    $("tt-title").textContent = p.name || p.ifcType; $("tt-status").textContent = p.ifcType.replace(/^IFC/i, "");
    $("tt-body").innerHTML = h ? `<div class="${h.sev === "bad" ? "bad" : h.sev === "ok" ? "ok" : ""}">${icon("heart", 12)} Salud ${h.score == null ? "—" : Math.round(h.score)}/100${h.anoms ? ` · ${h.anoms} anomalía(s)` : ""}</div><div>${esc(h.name)}</div>` : connected() ? "Sin gemelo enlazado" : "Inicia sesión para ver el gemelo";
  });
});
cv.addEventListener("pointerleave", () => $("tooltip3d").classList.add("hidden"));
function placeLabel() { const lab = $("sel-label"); const p = viewer.project(viewer.selected); if (!p) { lab.hidden = true; return; } lab.hidden = false; lab.style.left = `${p.x}px`; lab.style.top = `${p.y}px`; }
(function labelLoop() { if (viewer.selected.length) placeLabel(); requestAnimationFrame(labelLoop); })();
$<HTMLElement>("mep-layers").addEventListener("click", (event) => {
  const button = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-mep-layer]"); if (!button || button.disabled) return;
  const layer = button.dataset.mepLayer as MepLayer, visible = !viewer.isMepLayerVisible(layer);
  viewer.setMepLayerVisible(layer, visible); button.setAttribute("aria-pressed", String(visible)); button.classList.toggle("active", visible);
});

// ================= barra de herramientas del visor =================
const press = (act: string, on: boolean) => $("toolbar").querySelector(`[data-act="${act}"]`)?.setAttribute("aria-pressed", String(on));
function act(a: string) {
  if (a === "home") { viewer.home(); return; } if (a === "wire") { viewer.setWireframe(!viewer.wire); press("wire", viewer.wire); } if (a === "xray") { viewer.setXray(!viewer.xray); press("xray", viewer.xray); }
  if (a === "isolate") { if (!viewer.selected.length && !viewer.isolate) { toast("Selecciona un elemento para aislarlo", "info", 2500); return; } viewer.setIsolate(!viewer.isolate); press("isolate", viewer.isolate); }
  if (a === "section") { const on = viewer.section == null; $("section-wrap").hidden = !on; viewer.setSection(on ? Number($<HTMLInputElement>("section").value) / 100 : null); press("section", on); }
}
$("toolbar").addEventListener("click", (e) => { const b = (e.target as HTMLElement).closest<HTMLElement>("[data-act]"); if (b) act(b.dataset.act!); });
$("section").addEventListener("input", () => { const v = Number($<HTMLInputElement>("section").value); $("section-val").textContent = `${v}%`; viewer.setSection(v / 100); });
document.addEventListener("keydown", (e) => {
  const t = e.target as HTMLElement; if (["INPUT", "SELECT", "TEXTAREA"].includes(t.tagName) || e.ctrlKey || e.metaKey) return;
  const k = e.key.toLowerCase(); if (k === "h") act("home"); else if (k === "w") act("wire"); else if (k === "x") act("xray"); else if (k === "i") act("isolate"); else if (k === "f") viewer.fit(viewer.selected); else if (k === "escape") { clearSelection(); if (viewer.isolate) act("isolate"); }
});

// ================= pestañas =================
function activateTab(id: string) {
  document.querySelectorAll<HTMLElement>(".tab-btn").forEach((b) => { const on = b.dataset.target === id; b.classList.toggle("active", on); b.setAttribute("aria-selected", String(on)); });
  document.querySelectorAll<HTMLElement>(".tab-content").forEach((c) => c.classList.toggle("active", c.id === id));
  if (id === "tab-graph") { rebuildGraph(); graph.start(); } else graph.stop(); if (id === "tab-workflow") void loadTimeline(selNodeId);
}
document.querySelectorAll<HTMLElement>(".tab-btn").forEach((b) => b.addEventListener("click", () => activateTab(b.dataset.target!)));

// ================= grafo de conocimiento =================
const graph = new GraphView($<HTMLCanvasElement>("knowledge-canvas"), $("g-tip"), (n) => void onGraphSelect(n));
async function loadGraph() { if (!connected()) return; try { twinGraph = await api.graph(); } catch (e) { fail(e); } }
/** Sin sesión, el grafo se construye con la estructura espacial del propio IFC (sigue siendo real). */
function treeToGraph(t: TreeNode): TwinGraph {
  const nodes: TwinGraph["nodes"] = [], edges: TwinGraph["edges"] = []; const spatial: Record<string, string> = { IFCSITE: "site", IFCBUILDING: "building", IFCBUILDINGSTOREY: "storey", IFCSPACE: "space" };
  const walk = (n: TreeNode, parent: TreeNode | null) => { if (n.type === "IFCPROJECT") { n.children.forEach((c) => walk(c, null)); return; } nodes.push({ id: String(n.expressID), node_type: spatial[n.type] ?? "equipment", code: n.type, name: n.name });
    if (parent) edges.push({ from_node: String(parent.expressID), to_node: String(n.expressID), relation: "CONTAINS" }); n.children.forEach((c) => walk(c, n)); };
  walk(t, null); return { nodes, edges };
}
function rebuildGraph() {
  let g: TwinGraph | null = connected() ? twinGraph : null; if (!g && tree) g = treeToGraph(tree); if (!g) return;
  const m = buildGraphModel(g, { showIfc: showIfcNodes, focusId: connected() ? selNodeId : null, points, steps }); graph.setModel(m.nodes, m.edges);
}
async function onGraphSelect(n: GNode) {
  if (n.id.startsWith("sst:")) { activateTab("tab-workflow"); return; } if (n.id.startsWith("an:")) { activateTab("tab-workflow"); return; } if (n.id.startsWith("pt:")) { activateTab("tab-inspector"); return; }
  if (!connected()) { const ms = viewer.meshesOf([Number(n.id)]); if (ms.length) await selectMeshes(ms, { name: n.label, ifcType: n.ref ?? "", globalId: ms[0].userData.globalId, expressID: Number(n.id) }, true); return; }
  try { const d = await api.nodeDetail(n.twinId ?? n.id); const gid = d.ifc?.global_id; if (gid && (await selectByGlobalId(gid))) return; selNodeId = n.twinId ?? n.id; points = (d.points ?? []).map((p: any) => ({ id: p.id, name: p.name, value: p.value, canonical_unit: p.canonical_unit, quality: p.quality })); renderInspector({ name: d.node.name, ifcType: d.node.node_type, globalId: null, psets: [] }, d); activateTab("tab-inspector"); } catch (e) { fail(e); }
}
$<HTMLInputElement>("g-ifc").addEventListener("change", (e) => { showIfcNodes = (e.target as HTMLInputElement).checked; rebuildGraph(); });
$("g-reheat").addEventListener("click", () => graph.reheat());

// ================= flujo operativo y actividad en vivo =================
async function loadTimeline(nodeId: string | null) {
  const sum = $("wf-summary"), box = $("wf-timeline");
  if (!connected()) { sum.className = "wf-summary"; sum.innerHTML = "<b>Sin sesión</b>Conéctate para ver el flujo operativo del equipo."; box.innerHTML = ""; return; }
  if (!nodeId) { sum.className = "wf-summary"; sum.innerHTML = "<b>Selecciona un equipo</b>Haz clic en un equipo del visor, del árbol o del grafo para ver su flujo operativo."; box.innerHTML = ""; return; }
  try { const t = await api.timeline(nodeId); steps = t.steps; const v = toView(steps), s = summarize(v);
    sum.className = `wf-summary ${s.blocked ? "bad" : s.awaitingHuman ? "warn" : ""}`; sum.innerHTML = `<b>${esc(s.headline)}</b>${v.length} etapa(s) registradas para este equipo`;
    box.innerHTML = v.length ? v.map((x) => `<div class="wf-step ${x.state}"><div class="wf-icon">${icon(x.state === "completed" ? "check" : x.icon, 11)}</div><div class="wf-content"><h4>${esc(x.title)}</h4><p>${esc(x.detail)}</p><span class="when">${esc(x.when)}</span></div></div>`).join("") : '<div class="muted">Este equipo no tiene actividad registrada.</div>'; } catch (e) { fail(e); }
}
const liveItem = (e: LiveEvent, fresh = false) => { const h = humanize(e); return `<div class="item tone-${h.tone}${fresh ? " new" : ""}"><span class="d"></span><div>${esc(h.text)}<small>#${e.sequence} · ${esc(e.topic)}</small></div></div>`; };
async function startLive(attempt: number, authVersion: number) {
  const isCurrent = () => authAttempts.isCurrent(attempt) && api.authVersion === authVersion && connected();
  poller?.stop();
  const activePoller = new LivePoller((t, a, l) => api.replay(t, a, l), async (ev) => {
    const box = $("live"); box.insertAdjacentHTML("afterbegin", ev.map((e) => liveItem(e, true)).reverse().join("")); ev.forEach((e) => { const h = humanize(e); if (h.tone === "bad" || h.tone === "warn") toast(h.text, h.tone === "bad" ? "bad" : "warn"); });
    if (ev.some((e) => e.topic === "twin.anomaly.detected")) { $("pill-critical").classList.add("flash"); setTimeout(() => $("pill-critical").classList.remove("flash"), 2600); }
    await Promise.all([kpis(), colorize(), loadAnoms(), selNodeId ? loadTimeline(selNodeId) : Promise.resolve()]);
  });
  poller = activePoller;
  try {
    const hist = await activePoller.prime(8);
    if (!isCurrent() || poller !== activePoller) return;
    $("live").innerHTML = hist.length ? hist.reverse().map((e) => liveItem(e)).join("") : '<div class="muted">Sin eventos recientes. Se mostrarán aquí en cuanto ocurran.</div>';
    activePoller.start(5000, fail);
  } catch (e) {
    if (isCurrent()) fail(e);
  }
}

// ================= conexión, carga de archivos y refresco =================
$("conn-toggle").addEventListener("click", () => { const p = $<HTMLElement>("conn-panel"); p.hidden = !p.hidden; $("conn-toggle").setAttribute("aria-expanded", String(!p.hidden)); });
$("login").addEventListener("click", async () => {
  if (loginPending) return;
  loginPending = true;
  const attempt = authAttempts.begin();
  poller?.stop();
  poller = null;
  api.token = "";
  sessionValidated = false;
  clearAuthSession(undefined, true);
  saveAuthSession({
    token: "",
    tenantId: $<HTMLInputElement>("tenant").value.trim(),
    email: $<HTMLInputElement>("email").value.trim(),
  });
  $<HTMLInputElement>("tok").value = "";
  setSessionUi();
  const loginButton = $<HTMLButtonElement>("login");
  loginButton.disabled = true;
  api.base = $<HTMLInputElement>("api").value.trim();
  sessionStorage.setItem("bim.api", api.base);
  try {
    const token = await api.login($<HTMLInputElement>("tenant").value.trim(), $<HTMLInputElement>("email").value.trim(), $<HTMLInputElement>("pwd").value);
    if (!authAttempts.isCurrent(attempt)) return;
    $<HTMLInputElement>("tok").value = token;
    $<HTMLInputElement>("pwd").value = "";
    api.token = token;
    await connect(token, attempt);
  } catch (e) {
    if (authAttempts.isCurrent(attempt)) fail(e);
  } finally {
    loginPending = false;
    loginButton.disabled = false;
  }
});
$("conn").addEventListener("click", () => { if (!loginPending) void connect($<HTMLInputElement>("tok").value.trim()); });
$("mv").addEventListener("change", loadSelected); $("up").addEventListener("click", () => $("file").click());
$<HTMLInputElement>("file").addEventListener("change", async (e) => {
  const f = (e.target as HTMLInputElement).files?.[0]; if (!f) return; const bytes = new Uint8Array(await f.arrayBuffer());
  try { await showModel(bytes, f.name); if (!connected()) { toast("Modelo cargado solo en el visor. Inicia sesión para importarlo al gemelo.", "info"); return; }
    setMsg("Importando al gemelo digital…"); await api.importIfc(new TextDecoder().decode(bytes), f.name); toast("IFC importado al gemelo", "ok"); await refreshModels(true); await Promise.all([loadGraph(), kpis()]); } catch (er) { loading(false); fail(er); }
});
$<HTMLInputElement>("tree-search").addEventListener("input", (e) => treeView.filter((e.target as HTMLInputElement).value));
setInterval(() => { if (connected() && !document.hidden) { kpis().catch(fail); colorize().catch(fail); } }, 30000);   // red de seguridad: lo inmediato llega por eventos
setSessionUi(); $("mv").innerHTML = '<option value="demo">Modelo demo (torre_demo.ifc)</option>';
const boot = initialSession.token ? connect(initialSession.token, authAttempts.begin()) : loadSelected(); void boot;

// ================= ganchos de prueba (solo con ?e2e=1) =================
if (E2E) (window as any).__bim = {
  ready: new Promise<void>((r) => ((window as any).__bimReady = r)), viewer, graph, treeView,
  selectByGlobalId, act, activateTab, stats: () => ({ ...viewer.stats(), tree: countElements(tree), graphNodes: graph.nodeCount(), health: health.size, connected: connected(), selNodeId, steps: steps.length }),
  project: (gid: string) => { const ms = viewer.byGlobal.get(gid); return ms ? viewer.project(ms) : null; },
};
