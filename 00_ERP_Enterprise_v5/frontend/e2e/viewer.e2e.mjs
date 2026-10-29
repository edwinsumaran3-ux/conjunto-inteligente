// E2E en NAVEGADOR REAL (Chromium + WebGL) del Centro de Mando BIM contra el API real sembrado con scripts/seed_demo_twin.py.
// Variables: E2E_BASE (http://127.0.0.1:PORT), E2E_TENANT, E2E_EMAIL, E2E_PWD, E2E_OUT (carpeta de capturas), CHROME_PATH (opcional) o E2E_NODE_PATH (carpeta con @sparticuz/chromium + puppeteer-core).
import { createRequire } from "node:module"; import { pathToFileURL } from "node:url"; import fs from "node:fs"; import path from "node:path";
const req = createRequire(process.env.E2E_NODE_PATH ? path.join(process.env.E2E_NODE_PATH, "package.json") : import.meta.url);
const puppeteer = req("puppeteer-core");
let exe = process.env.CHROME_PATH, extra = [];
if (!exe) { const mod = await import(pathToFileURL(req.resolve("@sparticuz/chromium")).href); const ch = mod.default; exe = await ch.executablePath(); extra = ch.args; }
const { E2E_BASE: BASE, E2E_TENANT: TENANT, E2E_EMAIL: EMAIL, E2E_PWD: PWD, E2E_OUT: OUT = "e2e-out" } = process.env; fs.mkdirSync(OUT, { recursive: true });
const PUMP = "3tQ5UgSD11VOwa7ZfyDW$n", TANK = "13bz5Kktn94Ay9K8f9y71Q";
let n = 0; const ok = (c, m) => { if (!c) throw new Error("FALLO: " + m); console.log("  ✓", m); n++; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({ executablePath: exe, headless: "shell", args: [...extra, "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--no-sandbox", "--window-size=1920,1080"] });
const page = await browser.newPage(); await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });
const errors = []; page.on("pageerror", (e) => errors.push("pageerror: " + e.message)); page.on("console", (m) => { if (m.type() === "error") errors.push("console.error: " + m.text()); });
const shot = async (name) => { await sleep(350); await page.screenshot({ path: path.join(OUT, name + ".png") }); };
const idle = () => page.waitForFunction(() => document.getElementById("loading").hidden, { timeout: 30000 });
const stats = () => page.evaluate(() => window.__bim.stats());
const waitFor = (fn, msg, t = 25000, arg) => page.waitForFunction(fn, { timeout: t }, arg).catch(() => { throw new Error("TIMEOUT esperando: " + msg); });
const api = async (method, p, token, body) => { const r = await fetch(`${BASE}/api/v1${p}`, { method, headers: { "Content-Type": "application/json", ...(token ? { Authorization: "Bearer " + token } : {}) }, body: body ? JSON.stringify(body) : undefined }); if (!r.ok) throw new Error(`${method} ${p} -> ${r.status} ${await r.text()}`); return r.status === 204 ? {} : r.json(); };
const center = async (gid) => { const p = await page.evaluate((g) => window.__bim.project(g), gid); const b = await page.evaluate(() => { const r = document.getElementById("view").getBoundingClientRect(); return { x: r.left, y: r.top }; }); return { x: b.x + p.x, y: b.y + p.y }; };

try {
  console.log("1) Carga sin sesión: modelo IFC real + árbol espacial + WebGL");
  await page.goto(`${BASE}/bim/?e2e=1`, { waitUntil: "networkidle0" }); await page.evaluate(() => window.__bim.ready);
  let s = await stats(); ok(s.meshes >= 17, `${s.meshes} mallas IFC dibujadas`); ok(s.tree >= 17, `árbol espacial con ${s.tree} elementos`); ok(s.frames > 0, "el visor dibujó cuadros con WebGL");
  ok(await page.evaluate(() => document.querySelectorAll(".tree-node").length) >= 8, "el árbol (proyecto/sitio/edificio/niveles) está en el DOM");
  ok((await page.evaluate(() => document.getElementById("pill-critical").textContent)).includes("—"), "sin sesión no inventa cifras de alertas");
  await shot("01_sin_sesion");

  console.log("2) Inicio de sesión real desde la interfaz");
  await page.click("#conn-toggle"); await page.type("#tenant", TENANT); await page.type("#email", EMAIL); await page.type("#pwd", PWD); await page.click("#login");
  await waitFor(() => document.getElementById("n-critical").textContent !== "—" && window.__bim.stats().health > 0, "KPIs y mapa de salud tras el login");
  await idle(); ok((await page.evaluate(() => document.getElementById("conn-label").textContent)) === "Conectado", "estado «Conectado»"); ok((await page.evaluate(() => document.getElementById("pwd").value)) === "", "la contraseña no queda en el DOM");
  const pills = await page.evaluate(() => [...document.querySelectorAll(".status-pill b")].map((e) => e.textContent)); ok(Number(pills[0]) >= 2 && Number(pills[1]) + Number(pills[2]) >= 1, `pastillas reales (sensores/alertas/críticas) = ${pills.join("/")}`);
  const tint = await page.evaluate(([p, t]) => ({ pump: window.__bim.viewer.byGlobal.get(p)[0].userData.tint, tank: window.__bim.viewer.byGlobal.get(t)[0].userData.tint }), [PUMP, TANK]);
  ok(tint.pump === 0xe5484d, "la bomba (anomalía alta) se tiñe de ROJO por su salud real"); ok(tint.tank === 0x2fbf71, "el tanque (sano) se tiñe de VERDE");
  await shot("02_conectado");

  console.log("3) Rayos X + clic sobre la bomba en el 3D");
  await page.click('[data-act="xray"]'); ok((await stats()).xray === true, "modo rayos X activo");
  let c = await center(PUMP); await page.mouse.move(c.x, c.y); await sleep(500);
  ok(await page.evaluate(() => !document.getElementById("tooltip3d").classList.contains("hidden")), "tooltip flotante visible al pasar sobre la bomba"); ok((await page.evaluate(() => document.getElementById("tt-body").textContent)).includes("Salud"), "el tooltip muestra la salud del gemelo");
  await page.mouse.click(c.x, c.y);
  await waitFor(() => document.querySelector("#detail h2")?.textContent.includes("Bomba") && document.querySelector(".sensor-card"), "inspector con la bomba y sus sensores");
  const insp = await page.evaluate(() => ({ h: document.querySelector("#detail h2").textContent, cards: document.querySelectorAll(".sensor-card").length, psets: [...document.querySelectorAll("details.pset summary")].map((e) => e.textContent), chips: [...document.querySelectorAll(".chip")].map((e) => e.textContent).join("|"), health: document.querySelector(".health b")?.textContent }));
  ok(/Bomba/.test(insp.h), `inspector: «${insp.h}»`); ok(insp.cards >= 1, "tarjeta de sensor con valor real"); ok(insp.psets.some((x) => x.includes("Pset_ManufacturerTypeInformation")), "Psets CRUDOS del archivo IFC (Pset_ManufacturerTypeInformation)");
  ok(/25\/100|2[0-9]\/100/.test(insp.health ?? ""), `índice de salud real: ${insp.health}`); ok(insp.chips.includes("gemelo: equipment"), "chip «gemelo: equipment»: el clic resolvió al equipo operativo, no al nodo técnico IFC");
  await waitFor(() => { const c = document.getElementById("spark"); return c && c.width > 0; }, "gráfico de historial"); ok(!(await page.evaluate(() => document.getElementById("sel-label").hidden)), "etiqueta flotante anclada a la selección");
  await shot("03_bomba_seleccionada");

  console.log("4) Grafo de conocimiento (física en canvas real)");
  await page.click('[data-target="tab-graph"]'); await waitFor(() => window.__bim.stats().graphNodes >= 5, "nodos del grafo"); s = await stats(); ok(s.graphNodes >= 5, `${s.graphNodes} nodos (ubicación, equipos, IoT, alerta, SST)`);
  await sleep(1800); const gn = await page.evaluate(() => window.__bim.graph.fg.nodes.map((x) => ({ id: x.id, cat: x.cat, x: x.x, y: x.y, label: x.label })));
  ok(["location", "bim", "iot", "alert", "sst"].every((k) => gn.some((x) => x.cat === k)), "categorías BIM/Ubicación/IoT/Alerta/SST presentes"); ok(gn.every((x) => Number.isFinite(x.x) && Number.isFinite(x.y)), "posiciones finitas (la simulación es estable)");
  const t0 = await page.evaluate(() => window.__bim.graph.fg.nodes.find((x) => x.cat === "location").x); await sleep(1200); await shot("04_grafo");
  const tank = gn.find((x) => /Tanque/.test(x.label)); const cr = await page.evaluate(() => { const r = document.getElementById("knowledge-canvas").getBoundingClientRect(); return { x: r.left, y: r.top }; });
  await page.mouse.click(cr.x + tank.x, cr.y + tank.y); await waitFor(() => document.querySelector("#detail h2")?.textContent.includes("Tanque"), "clic en un nodo del grafo selecciona el equipo (y su geometría) en el inspector"); ok(true, "clic en el nodo «Tanque» del grafo → inspector del tanque");
  ok((await stats()).selected >= 1, "…y selecciona su geometría en el visor 3D");

  console.log("5) Flujo operativo real (anomalía → diagnóstico → orden → SST)");
  await page.click('[data-target="tab-inspector"]'); await page.click('[data-act="home"]'); await sleep(500); c = await center(PUMP); await page.mouse.click(c.x, c.y); await waitFor(() => document.querySelector("#detail h2")?.textContent.includes("Bomba"), "re-seleccionar bomba");
  await page.click('[data-target="tab-workflow"]'); await waitFor(() => document.querySelectorAll(".wf-step").length >= 4, "etapas del flujo");
  const wf = await page.evaluate(() => ({ steps: [...document.querySelectorAll(".wf-step")].map((e) => e.className.replace("wf-step ", "") + ":" + e.querySelector("h4").textContent), sum: document.getElementById("wf-summary").textContent }));
  ok(wf.steps.some((x) => x.startsWith("active:Anomalía")), "anomalía ACTIVA"); ok(wf.steps.some((x) => x.startsWith("pending:Orden de mantenimiento")), "orden de mantenimiento PENDIENTE de aprobación humana"); ok(wf.steps.some((x) => x.startsWith("blocked:SST")), "actividad SST BLOQUEADA");
  ok(/bloqueo/.test(wf.sum), `resumen ejecutivo: «${wf.sum.slice(0, 60)}…»`); await shot("05_flujo");

  console.log("6) Eventos en vivo: una nueva anomalía llega sin recargar");
  const tok = await api("POST", "/auth/login", null, { email: EMAIL, password: PWD, tenant_id: TENANT }).then((r) => r.access_token); const g = await api("GET", "/digital-twin/graph", tok); const tankNode = g.nodes.find((x) => x.code === "TK1").id;
  const pts = await api("GET", `/digital-twin/nodes/${tankNode}/detail`, tok); const before = await page.evaluate(() => Number(document.getElementById("n-alerts").textContent) + Number(document.getElementById("n-critical").textContent));
  for (let i = 0; i < 5; i++) await api("POST", "/digital-twin/telemetry/samples", tok, { point_id: pts.points[0].id, value: 70 + i * 6, unit: "degC", observed_at: new Date(Date.now() - (4 - i) * 20000).toISOString(), source: "e2e", source_message_id: "e2e-" + Date.now() + i, sequence: 100 + i });
  await api("POST", "/digital-twin/diagnostics/evaluate", tok, { node_id: tankNode, window_minutes: 30, min_samples: 3 });
  await waitFor(() => document.querySelector("#live .item.new"), "evento en vivo en el panel", 20000); ok(true, "el evento aparece en «Actividad en vivo» sin recargar la página");
  await waitFor((b) => Number(document.getElementById("n-alerts").textContent) + Number(document.getElementById("n-critical").textContent) > b, "pastillas de alertas actualizadas", 20000, before); ok(true, "las pastillas de alertas suben solas");
  await waitFor(([t]) => window.__bim.viewer.byGlobal.get(t)[0].userData.tint !== 0x2fbf71, "el tanque deja de ser verde", 20000, [TANK]); ok(true, "el tanque cambia de color en el 3D en cuanto se detecta la anomalía");
  ok(await page.evaluate(() => document.querySelector(".toast") !== null), "aviso emergente (toast) mostrado"); await shot("06_evento_en_vivo");

  console.log("7) Herramientas del visor");
  await page.click('[data-target="tab-inspector"]'); await page.click('[data-act="home"]'); const full = (await stats()).visible;
  await page.click('[data-act="section"]'); await page.$eval("#section", (e) => { e.value = 45; e.dispatchEvent(new Event("input", { bubbles: true })); }); await sleep(300); ok((await stats()).section > 0.4 && (await stats()).section < 0.5, "plano de corte activo al 45 %");
  await shot("07_corte"); await page.click('[data-act="section"]'); ok((await stats()).section === null, "corte desactivado");
  await page.click('[data-act="wire"]'); ok((await stats()).wire && (await page.evaluate(() => window.__bim.viewer.group.children[0].material.wireframe)), "modo alámbrico aplicado a los materiales"); await page.click('[data-act="wire"]');
  await page.click('[data-act="xray"]'); await page.keyboard.press("x"); await page.keyboard.press("x"); await page.click('[data-act="xray"]');
  c = await center(PUMP); await page.mouse.click(c.x, c.y); await sleep(600); await page.click('[data-act="isolate"]'); ok((await stats()).visible < full && (await stats()).visible >= 1, `aislar deja ${(await stats()).visible} de ${full} elementos visibles`);
  await page.keyboard.press("Escape"); await sleep(300); ok((await stats()).visible === full && (await stats()).selected === 0, "Esc restaura la vista completa y limpia la selección");

  console.log("8) Búsqueda en el árbol y enlace de un elemento sin gemelo");
  await page.type("#tree-search", "bomba"); await sleep(300); const found = await page.evaluate(() => [...document.querySelectorAll(".tree-node .nm")].map((e) => e.textContent)); ok(found.some((x) => /Bomba/.test(x)) && !found.some((x) => /Tanque/.test(x)), "la búsqueda filtra el árbol conservando ancestros"); await page.$eval("#tree-search", (e) => { e.value = ""; e.dispatchEvent(new Event("input", { bubbles: true })); });
  await page.evaluate(() => window.__bim.viewer.home()); await sleep(500);
  const wall = await page.evaluate(() => { const v = window.__bim.viewer; const m = v.group.children.find((x) => /IfcWall/i.test(x.userData.ifcType) && !window.__bim.viewer.byGlobal.has("x")); const ms = [m]; return { gid: m.userData.globalId }; });
  await page.evaluate((g) => window.__bim.selectByGlobalId(g, false), wall.gid); await waitFor(() => document.getElementById("lnkgo"), "caja «Enlazar con equipo»"); ok(true, "un muro sin gemelo ofrece «Enlazar con equipo»");
  await page.select("#lnk", await page.$eval("#lnk option", (o) => o.value)); await page.click("#lnkgo"); await waitFor(() => [...document.querySelectorAll(".chip")].some((e) => e.textContent.includes("gemelo: equipment")), "enlace aplicado"); ok(true, "tras enlazar, el elemento resuelve a un equipo operativo");
  await shot("08_enlazado");

  const bad = errors.filter((e) => !/favicon|ERR_BLOCKED|DEPRECATED|GPU stall|GroupMarkerNotSet/i.test(e)); ok(bad.length === 0, `sin errores de consola ni excepciones (${bad.length})` + (bad.length ? ": " + bad.slice(0, 3).join(" || ") : ""));
  console.log(`\nE2E_NAVEGADOR_OK ${n} comprobaciones · capturas en ${OUT}`);
} catch (e) { await page.screenshot({ path: path.join(OUT, "FALLO.png") }).catch(() => undefined); console.error("\n✗", e.message, errors.length ? "\n  errores de página: " + errors.slice(0, 4).join(" || ") : ""); process.exitCode = 1; }
finally { await browser.close(); }
