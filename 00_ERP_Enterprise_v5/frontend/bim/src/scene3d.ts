/** Visor 3D (three.js): mallas del IFC real, selección con resalte, rayos X, aislar, plano de corte, tinte por salud del gemelo y proyección a pantalla. */
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { IfcLoadResult } from "./ifcGeometry";
import { MEP_DISCIPLINES, MEP_LAYER_COLORS, MepLayer, MepNetwork, summarizeMepLayers } from "./mep";

export interface PickInfo { mesh: THREE.Mesh; globalId: string | null; expressID: number; name: string; ifcType: string; }
export interface EquipmentIdentity { globalId: string | null; expressID: number; name: string | null; ifcType: string; }
export function fitCameraPose(camera: THREE.Vector3, target: THREE.Vector3, bounds: THREE.Box3, padding = 3.4) {
  const center = bounds.getCenter(new THREE.Vector3()), size = Math.max(bounds.getSize(new THREE.Vector3()).length(), 1.5);
  const direction = camera.clone().sub(target).normalize();
  return { target: center, position: center.clone().add(direction.multiplyScalar(size * padding).add(new THREE.Vector3(0, size * 0.4, 0))) };
}
const SHELL = ["ifcwall", "ifcwallstandardcase", "ifcslab", "ifcroof", "ifccovering", "ifccurtainwall", "ifcwindow", "ifcdoor", "ifcplate", "ifcstair"];
const IFC_PREVIEW_COLORS: [RegExp, number][] = [
  [/ifcwall|ifcplate|ifcdoor/i, 0xc3cec7],
  [/ifcslab|ifcroof|ifcstair/i, 0x899991],
  [/ifcwindow|ifccurtainwall/i, 0x72a6aa],
  [/ifcpump|ifcvalve|ifcflowsegment/i, 0x528579],
  [/ifctank|ifcstorage/i, 0xa0ada7],
];

export function ifcDisplayColor(ifcType: string, source: THREE.Color): THREE.Color {
  const rgb = [source.r, source.g, source.b], neutralWhite = Math.min(...rgb) > 0.95 && Math.max(...rgb) - Math.min(...rgb) < 0.04;
  if (!neutralWhite) return source.clone();
  const fallback = IFC_PREVIEW_COLORS.find(([pattern]) => pattern.test(ifcType));
  return new THREE.Color(fallback?.[1] ?? 0x77877f);
}

export function createEquipmentProxyMeshes(identity: EquipmentIdentity, bounds: THREE.Box3): THREE.Mesh[] {
  const type = identity.ifcType.toLowerCase();
  if (type !== "ifcpump" && type !== "ifctank") return [];
  const size = bounds.getSize(new THREE.Vector3());
  if (size.x <= 0 || size.y <= 0 || size.z <= 0) return [];
  const center = bounds.getCenter(new THREE.Vector3()), meshes: THREE.Mesh[] = [];
  const materials = {
    enamel: new THREE.MeshStandardMaterial({ color: type === "ifcpump" ? 0x286d9b : 0x63868c, metalness: 0.52, roughness: 0.3 }),
    highlight: new THREE.MeshStandardMaterial({ color: 0x9bb7bb, metalness: 0.78, roughness: 0.25 }),
    dark: new THREE.MeshStandardMaterial({ color: 0x24343b, metalness: 0.55, roughness: 0.42 }),
    base: new THREE.MeshStandardMaterial({ color: 0x34484c, metalness: 0.68, roughness: 0.38 }),
  };
  const add = (geometry: THREE.BufferGeometry, material: THREE.Material, position: THREE.Vector3, rotation?: THREE.Euler, scale?: THREE.Vector3) => {
    const mesh = new THREE.Mesh(geometry, material); mesh.position.copy(position);
    if (rotation) mesh.rotation.copy(rotation); if (scale) mesh.scale.copy(scale);
    mesh.castShadow = true; mesh.receiveShadow = true; meshes.push(mesh); return mesh;
  };
  const box = (width: number, height: number, depth: number, position: THREE.Vector3, material = materials.base) => add(new THREE.BoxGeometry(width, height, depth), material, position);
  const cylinder = (radius: number, length: number, position: THREE.Vector3, axis: "x" | "y" | "z" = "y", material = materials.highlight, radial = 24) => {
    const rotation = axis === "x" ? new THREE.Euler(0, 0, Math.PI / 2) : axis === "z" ? new THREE.Euler(Math.PI / 2, 0, 0) : new THREE.Euler();
    return add(new THREE.CylinderGeometry(radius, radius, length, radial), material, position, rotation);
  };
  const ring = (radius: number, tube: number, position: THREE.Vector3, plane: "x" | "y" | "z" = "y") => {
    const rotation = plane === "x" ? new THREE.Euler(0, Math.PI / 2, 0) : plane === "y" ? new THREE.Euler(Math.PI / 2, 0, 0) : new THREE.Euler();
    return add(new THREE.TorusGeometry(radius, tube, 8, 32), materials.highlight, position, rotation);
  };

  if (type === "ifcpump") {
    const depth = Math.min(size.x, size.z), height = size.y;
    const shaftAxis: "x" | "z" = size.x >= size.z ? "x" : "z";
    const shaft = height * 0.19, caseRadius = Math.min(height * 0.23, depth * 0.29), floor = bounds.min.y;
    const baseY = floor + height * 0.06, shaftY = floor + height * 0.49;
    const x0 = center.x, z0 = center.z, baseLength = size.x * 0.9, baseDepth = size.z * 0.78;
    const pipeRadius = Math.min(height * 0.045, caseRadius * 0.2);
    const flange = (axis: "x" | "y" | "z", position: THREE.Vector3, radius: number) => {
      const thickness = Math.min(height * 0.035, radius * 0.32);
      cylinder(radius, thickness, position, axis, materials.highlight, 32);
      ring(radius * 0.92, thickness * 0.22, position, axis);
      for (let bolt = 0; bolt < 8; bolt++) {
        const angle = (bolt / 8) * Math.PI * 2, offset = radius * 0.76;
        const point = axis === "x"
          ? new THREE.Vector3(position.x, position.y + Math.cos(angle) * offset, position.z + Math.sin(angle) * offset)
          : axis === "y"
            ? new THREE.Vector3(position.x + Math.cos(angle) * offset, position.y, position.z + Math.sin(angle) * offset)
            : new THREE.Vector3(position.x + Math.cos(angle) * offset, position.y + Math.sin(angle) * offset, position.z);
        cylinder(thickness * 0.22, thickness * 1.2, point, axis, materials.dark, 8);
      }
    };
    box(baseLength, height * 0.055, baseDepth, new THREE.Vector3(x0, baseY, z0));
    for (const dx of [-0.34, 0.34]) for (const dz of [-0.24, 0.24]) {
      cylinder(height * 0.035, height * 0.19, new THREE.Vector3(x0 + size.x * dx, floor + height * 0.16, z0 + size.z * dz), "y", materials.dark, 12);
    }
    if (shaftAxis === "x") {
      const motorLength = size.x * 0.39, motorX = x0 - size.x * 0.19;
      cylinder(shaft, motorLength, new THREE.Vector3(motorX, shaftY, z0), "x", materials.enamel, 32);
      cylinder(shaft * 0.82, height * 0.09, new THREE.Vector3(motorX - motorLength * 0.49, shaftY, z0), "x", materials.dark, 32);
      cylinder(shaft * 0.9, height * 0.08, new THREE.Vector3(motorX + motorLength * 0.49, shaftY, z0), "x", materials.highlight, 32);
      for (const offset of [-0.11, -0.03, 0.05, 0.13]) ring(shaft * 0.92, height * 0.018, new THREE.Vector3(motorX + size.x * offset, shaftY, z0), "x");
      cylinder(shaft * 0.38, size.x * 0.18, new THREE.Vector3(x0 + size.x * 0.04, shaftY, z0), "x", materials.highlight, 24);
      const caseCenter = new THREE.Vector3(x0 + size.x * 0.23, shaftY, z0);
      add(new THREE.SphereGeometry(1, 32, 24), materials.enamel, caseCenter, undefined, new THREE.Vector3(caseRadius * 1.48, caseRadius * 1.22, caseRadius * 1.15));
      cylinder(caseRadius * 0.78, height * 0.075, new THREE.Vector3(x0 + size.x * 0.34, shaftY, z0), "x", materials.highlight, 32);
      cylinder(caseRadius * 0.2, height * 0.23, new THREE.Vector3(x0 + size.x * 0.23, floor + height * 0.79, z0), "y", materials.highlight, 20);
      cylinder(caseRadius * 0.33, height * 0.035, new THREE.Vector3(x0 + size.x * 0.23, floor + height * 0.91, z0), "y", materials.dark, 24);
      cylinder(caseRadius * 0.2, height * 0.16, new THREE.Vector3(x0 + size.x * 0.23, floor + height * 0.22, z0), "y", materials.highlight, 20);
      box(height * 0.19, height * 0.13, depth * 0.32, new THREE.Vector3(motorX, floor + height * 0.78, z0), materials.base);
      flange("x", new THREE.Vector3(x0 + size.x * 0.38, shaftY, z0), pipeRadius * 1.65);
      cylinder(pipeRadius, size.x * 0.13, new THREE.Vector3(x0 + size.x * 0.42, shaftY, z0), "x", materials.base);
      flange("x", new THREE.Vector3(x0 - size.x * 0.39, shaftY, z0), pipeRadius * 1.65);
      cylinder(pipeRadius, size.x * 0.12, new THREE.Vector3(x0 - size.x * 0.43, shaftY, z0), "x", materials.base);
      const riser = new THREE.Vector3(x0 + size.x * 0.23, floor + height * 0.83, z0);
      cylinder(pipeRadius, height * 0.16, new THREE.Vector3(riser.x, floor + height * 0.78, riser.z), "y", materials.base);
      flange("y", new THREE.Vector3(riser.x, floor + height * 0.94, riser.z), pipeRadius * 1.65);
      ring(pipeRadius * 1.6, height * 0.012, new THREE.Vector3(riser.x, floor + height * 0.82, riser.z), "x");
      const gauge = new THREE.Vector3(x0 + size.x * 0.24, floor + height * 0.67, z0 + size.z * 0.2);
      cylinder(height * 0.055, height * 0.025, gauge, "z", materials.highlight, 24);
      ring(height * 0.055, height * 0.009, gauge, "z");
      cylinder(height * 0.007, height * 0.03, new THREE.Vector3(gauge.x, gauge.y, gauge.z + height * 0.015), "z", materials.dark, 8);
    } else {
      const motorLength = size.z * 0.39, motorZ = z0 - size.z * 0.19;
      cylinder(shaft, motorLength, new THREE.Vector3(x0, shaftY, motorZ), "z", materials.enamel, 32);
      cylinder(shaft * 0.82, height * 0.09, new THREE.Vector3(x0, shaftY, motorZ - motorLength * 0.49), "z", materials.dark, 32);
      cylinder(shaft * 0.9, height * 0.08, new THREE.Vector3(x0, shaftY, motorZ + motorLength * 0.49), "z", materials.highlight, 32);
      for (const offset of [-0.11, -0.03, 0.05, 0.13]) ring(shaft * 0.92, height * 0.018, new THREE.Vector3(x0, shaftY, motorZ + size.z * offset), "z");
      cylinder(shaft * 0.38, size.y * 0.18, new THREE.Vector3(x0, shaftY, z0 + size.z * 0.04), "z", materials.highlight, 24);
      add(new THREE.SphereGeometry(1, 32, 24), materials.enamel, new THREE.Vector3(x0, shaftY, z0 + size.z * 0.23), undefined, new THREE.Vector3(caseRadius * 1.15, caseRadius * 1.22, caseRadius * 1.48));
      cylinder(caseRadius * 0.2, height * 0.23, new THREE.Vector3(x0, floor + height * 0.79, z0 + size.z * 0.23), "y", materials.highlight, 20);
      const caseCenter = new THREE.Vector3(x0, shaftY, z0 + size.z * 0.23);
      box(depth * 0.28, height * 0.13, height * 0.19, new THREE.Vector3(x0, floor + height * 0.78, motorZ), materials.base);
      flange("z", new THREE.Vector3(x0, shaftY, z0 + size.z * 0.39), pipeRadius * 1.65);
      cylinder(pipeRadius, size.z * 0.13, new THREE.Vector3(x0, shaftY, z0 + size.z * 0.43), "z", materials.base);
      flange("z", new THREE.Vector3(x0, shaftY, z0 - size.z * 0.39), pipeRadius * 1.65);
      cylinder(pipeRadius, size.z * 0.12, new THREE.Vector3(x0, shaftY, z0 - size.z * 0.43), "z", materials.base);
      const riser = new THREE.Vector3(x0, floor + height * 0.83, caseCenter.z);
      cylinder(pipeRadius, height * 0.16, new THREE.Vector3(riser.x, floor + height * 0.78, riser.z), "y", materials.base);
      flange("y", new THREE.Vector3(riser.x, floor + height * 0.94, riser.z), pipeRadius * 1.65);
      ring(pipeRadius * 1.6, height * 0.012, new THREE.Vector3(riser.x, floor + height * 0.82, riser.z), "z");
      const gauge = new THREE.Vector3(x0 + size.x * 0.2, floor + height * 0.67, z0 + size.z * 0.25);
      cylinder(height * 0.055, height * 0.025, gauge, "x", materials.highlight, 24);
      ring(height * 0.055, height * 0.009, gauge, "x");
      cylinder(height * 0.007, height * 0.03, new THREE.Vector3(gauge.x + height * 0.015, gauge.y, gauge.z), "x", materials.dark, 8);
    }
  } else {
    const radius = Math.min(size.x, size.z) * 0.34, floor = bounds.min.y, bodyHeight = size.y * 0.73;
    cylinder(radius, bodyHeight, new THREE.Vector3(center.x, floor + size.y * 0.51, center.z), "y", materials.enamel, 40);
    cylinder(radius * 1.07, size.y * 0.045, new THREE.Vector3(center.x, floor + size.y * 0.145, center.z), "y", materials.dark, 40);
    cylinder(radius * 1.07, size.y * 0.045, new THREE.Vector3(center.x, floor + size.y * 0.875, center.z), "y", materials.highlight, 40);
    for (const level of [0.29, 0.47, 0.65, 0.82]) ring(radius * 1.015, size.y * 0.012, new THREE.Vector3(center.x, floor + size.y * level, center.z));
    cylinder(radius * 0.28, size.y * 0.15, new THREE.Vector3(center.x, floor + size.y * 0.925, center.z), "y", materials.highlight, 24);
    for (const dx of [-0.67, 0.67]) for (const dz of [-0.67, 0.67]) {
      cylinder(size.y * 0.026, size.y * 0.25, new THREE.Vector3(center.x + radius * dx, floor + size.y * 0.13, center.z + radius * dz), "y", materials.dark, 12);
    }
    cylinder(radius * 0.11, size.y * 0.42, new THREE.Vector3(center.x + radius * 1.02, floor + size.y * 0.52, center.z), "y", materials.highlight, 12);
  }
  return meshes;
}

export class Viewer {
  scene = new THREE.Scene(); cam = new THREE.PerspectiveCamera(50, 1, 0.1, 5000); renderer: THREE.WebGLRenderer; controls: OrbitControls;
  group: THREE.Group | null = null; byGlobal = new Map<string, THREE.Mesh[]>(); byExpress = new Map<number, THREE.Mesh[]>();
  private mepSummary = summarizeMepLayers({ systems: [], components: [], connections: [] });
  private mepVisibility = Object.fromEntries(MEP_DISCIPLINES.map((layer) => [layer, true])) as Record<MepLayer, boolean>;
  selected: THREE.Mesh[] = []; wire = false; xray = false; isolate = false; section: number | null = null;
  homePos = new THREE.Vector3(18, 14, 18); homeTarget = new THREE.Vector3(); bounds = new THREE.Box3(); frames = 0;
  private clip = new THREE.Plane(new THREE.Vector3(0, -1, 0), 100); private ray = new THREE.Raycaster(); private v = new THREE.Vector3(); private dirty = true;

  constructor(private canvas: HTMLCanvasElement, private host: HTMLElement) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true }); this.renderer.localClippingEnabled = true;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping; this.renderer.toneMappingExposure = 0.9;
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2)); this.scene.background = new THREE.Color(0x1b2422);
    const environment = new RoomEnvironment(), pmrem = new THREE.PMREMGenerator(this.renderer);
    this.scene.environment = pmrem.fromScene(environment, 0.04).texture; this.scene.environmentIntensity = 0.35; environment.dispose(); pmrem.dispose();
    this.cam.position.copy(this.homePos); this.controls = new OrbitControls(this.cam, canvas); this.controls.enableDamping = true; this.controls.dampingFactor = 0.07; this.controls.addEventListener("change", () => (this.dirty = true));
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x52635e, 0.72)); const sun = new THREE.DirectionalLight(0xfff4e7, 1.2); sun.position.set(10, 20, 8); this.scene.add(sun);
    const fill = new THREE.DirectionalLight(0xc9e6df, 0.32); fill.position.set(-12, 8, -10); this.scene.add(fill);
    const grid = new THREE.GridHelper(80, 80, 0x64736e, 0x3c4945); (grid.material as THREE.Material).transparent = true; (grid.material as THREE.Material).opacity = 0.32; (grid.material as THREE.Material).depthWrite = false; this.scene.add(grid);
    new ResizeObserver(() => this.resize()).observe(host); this.resize();
    const loop = () => { this.controls.update(); if (this.dirty) { this.renderer.render(this.scene, this.cam); this.dirty = false; this.frames++; } requestAnimationFrame(loop); }; loop();
  }
  resize() { const w = this.host.clientWidth, h = this.host.clientHeight; if (!w || !h) return; this.renderer.setSize(w, h, false); this.cam.aspect = w / h; this.cam.updateProjectionMatrix(); this.dirty = true; }
  invalidate() { this.dirty = true; }

  clear() {
    if (this.group) { this.scene.remove(this.group); this.group.traverse((o: any) => { o.geometry?.dispose(); o.material?.dispose?.(); }); }
    this.group = null; this.byGlobal.clear(); this.byExpress.clear(); this.selected = []; this.mepSummary = summarizeMepLayers({ systems: [], components: [], connections: [] }); this.rebuildOutlines(); this.dirty = true;
  }
  load(r: IfcLoadResult) {
    this.clear(); const g = new THREE.Group(), sources = new Map<number, { identity: EquipmentIdentity; meshes: THREE.Mesh[] }>();
    for (const m of r.meshes) {
      const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(m.positions, 3)); geo.setAttribute("normal", new THREE.BufferAttribute(m.normals, 3)); geo.setIndex(new THREE.BufferAttribute(m.indices, 1));
      const sourceColor = new THREE.Color(m.color[0], m.color[1], m.color[2]);
      const mat = new THREE.MeshStandardMaterial({ color: ifcDisplayColor(m.ifcType, sourceColor), transparent: m.color[3] < 1, opacity: m.color[3], side: THREE.DoubleSide, metalness: 0.08, roughness: 0.68 });
      const mesh = new THREE.Mesh(geo, mat); mesh.matrixAutoUpdate = false; mesh.matrix.fromArray(m.matrix);
      mesh.userData = { globalId: m.globalId, name: m.name, ifcType: m.ifcType, expressID: m.expressID, base: mat.color.getHex(), baseOpacity: m.color[3], tint: null as number | null };
      g.add(mesh); (this.byExpress.get(m.expressID) ?? this.byExpress.set(m.expressID, []).get(m.expressID)!).push(mesh);
      if (m.globalId) (this.byGlobal.get(m.globalId) ?? this.byGlobal.set(m.globalId, []).get(m.globalId)!).push(mesh);
      const source = sources.get(m.expressID) ?? { identity: { globalId: m.globalId, expressID: m.expressID, name: m.name, ifcType: m.ifcType }, meshes: [] };
      source.meshes.push(mesh); sources.set(m.expressID, source);
    }
    g.updateMatrixWorld(true);
    for (const { identity, meshes } of sources.values()) {
      const bounds = new THREE.Box3(); meshes.forEach((mesh) => bounds.expandByObject(mesh));
      const parts = createEquipmentProxyMeshes(identity, bounds);
      if (!parts.length) continue;
      meshes.forEach((mesh) => { mesh.userData.visualSource = true; mesh.visible = false; });
      for (const part of parts) {
        const material = part.material as THREE.MeshStandardMaterial;
        part.userData = { ...identity, base: material.color.getHex(), baseOpacity: 1, tint: null as number | null, visualProxy: true };
        g.add(part); (this.byExpress.get(identity.expressID) ?? []).push(part);
        if (identity.globalId) (this.byGlobal.get(identity.globalId) ?? []).push(part);
      }
    }
    this.mepSummary = summarizeMepLayers(r.mep);
    for (const component of r.mep.components) {
      if (component.discipline === "unknown" || component.systemExpressIDs.length === 0) continue;
      const layer = component.discipline;
      for (const mesh of this.byExpress.get(component.expressID) ?? []) {
        const material = mesh.material as THREE.MeshStandardMaterial;
        material.color.setHex(MEP_LAYER_COLORS[layer]); mesh.userData.base = MEP_LAYER_COLORS[layer]; mesh.userData.mepLayer = layer;
        material.needsUpdate = true;
      }
    }
    this.group = g; this.scene.add(g); g.updateMatrixWorld(true); this.bounds.setFromObject(g);
    const c = this.bounds.getCenter(new THREE.Vector3()), s = this.bounds.getSize(new THREE.Vector3()).length() || 10;
    this.homeTarget.copy(c); this.homePos.copy(c).add(new THREE.Vector3(s * 0.95, s * 0.62, s * 0.95)); this.cam.far = s * 30; this.cam.updateProjectionMatrix(); this.home();
    this.apply();
  }
  home() { this.controls.target.copy(this.homeTarget); this.cam.position.copy(this.homePos); this.controls.update(); this.dirty = true; }
  fit(meshes: THREE.Mesh[]) {
    if (!meshes.length) return this.home(); const box = new THREE.Box3(); meshes.forEach((m) => box.expandByObject(m)); if (box.isEmpty()) return;
    const pose = fitCameraPose(this.cam.position, this.controls.target, box); this.controls.target.copy(pose.target);
    this.cam.position.copy(pose.position); this.controls.update(); this.dirty = true;
  }
  meshesOf(expressIDs: Iterable<number>): THREE.Mesh[] { const out: THREE.Mesh[] = []; for (const id of expressIDs) out.push(...(this.byExpress.get(id) ?? [])); return out; }
  setMepLayerVisible(layer: MepLayer, visible: boolean) { this.mepVisibility[layer] = visible; this.apply(); }
  isMepLayerVisible(layer: MepLayer) { return this.mepVisibility[layer]; }
  getMepSummary() { return this.mepSummary; }

  // ---------- selección y estados visuales ----------
  private outlines: THREE.LineSegments[] = [];
  /** Contorno blanco sobre la selección (visible a través de las capas de rayos X) + resalte emisivo del color de salud. */
  private rebuildOutlines() {
    for (const o of this.outlines) { this.scene.remove(o); o.geometry.dispose(); (o.material as THREE.Material).dispose(); } this.outlines = [];
    for (const m of this.selected.filter((mesh) => !mesh.userData.visualSource && !mesh.userData.visualProxy).slice(0, 60)) { const l = new THREE.LineSegments(new THREE.EdgesGeometry(m.geometry, 25), new THREE.LineBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true, opacity: 0.95 })); l.matrixAutoUpdate = false; l.matrix.copy(m.matrix); l.renderOrder = 20; this.scene.add(l); this.outlines.push(l); }
    this.dirty = true;
  }
  setSelection(ms: THREE.Mesh[]) { this.selected = ms; this.apply(); this.rebuildOutlines(); }
  /** Tinta por salud del gemelo (hex) o restaura el color original (null). */
  tint(globalId: string, hex: number | null) { (this.byGlobal.get(globalId) ?? []).forEach((m) => (m.userData.tint = hex)); this.apply(); }
  clearTints() { this.group?.children.forEach((m) => (m.userData.tint = null)); this.apply(); }
  setWireframe(b: boolean) { this.wire = b; this.apply(); } setXray(b: boolean) { this.xray = b; this.apply(); } setIsolate(b: boolean) { this.isolate = b; this.apply(); }
  /** frac 0..1 sobre la altura del modelo; null desactiva el corte. */
  setSection(frac: number | null) { this.section = frac; if (frac != null) this.clip.constant = this.bounds.min.y + (this.bounds.max.y - this.bounds.min.y) * frac + 0.001; this.apply(); }
  private apply() {
    const sel = new Set(this.selected);
    this.group?.children.forEach((o) => {
      const m = o as THREE.Mesh, mat = m.material as THREE.MeshStandardMaterial, u = m.userData, isSel = sel.has(m);
      mat.color.setHex(u.tint ?? u.base); mat.emissive.setHex(isSel ? (u.tint ?? 0x2b4f8f) : 0x000000); mat.emissiveIntensity = isSel ? 0.5 : 1; mat.wireframe = this.wire; mat.clippingPlanes = this.section != null ? [this.clip] : [];
      const shell = SHELL.includes(String(u.ifcType).toLowerCase()), ghost = this.xray && shell && !isSel;
      const equip = this.xray && !shell;   // en rayos X el equipo va en la pasada transparente con orden mayor: se dibuja sobre las capas fantasma, sin lavarse
      const hiddenMepLayer = u.mepLayer && !this.mepVisibility[u.mepLayer as MepLayer];
      mat.transparent = ghost || equip || u.baseOpacity < 1; mat.opacity = ghost ? 0.14 : equip ? 0.999 : u.baseOpacity; mat.depthWrite = !ghost; m.renderOrder = equip ? 5 : 0; m.visible = !u.visualSource && !hiddenMepLayer && !(this.isolate && sel.size > 0 && !isSel); mat.needsUpdate = true;
    });
    this.dirty = true;
  }

  // ---------- picking y proyección ----------
  pickAt(clientX: number, clientY: number): PickInfo | null {
    if (!this.group) return null; const b = this.canvas.getBoundingClientRect(); const ndc = new THREE.Vector2(((clientX - b.left) / b.width) * 2 - 1, -((clientY - b.top) / b.height) * 2 + 1);
    this.ray.setFromCamera(ndc, this.cam);
    // en rayos X el clic atraviesa muros y losas translúcidos; un plano de corte activo descarta lo recortado
    const hit = this.ray.intersectObjects(this.group.children.filter((c) => c.visible && !(this.xray && SHELL.includes(String(c.userData.ifcType).toLowerCase()) && !this.selected.includes(c as THREE.Mesh))), false).find((h) => this.section == null || this.clip.distanceToPoint(h.point) >= -1e-6);   // ignora lo recortado por el plano de corte
    if (!hit) return null; const m = hit.object as THREE.Mesh, u = m.userData; return { mesh: m, globalId: u.globalId, expressID: u.expressID, name: u.name, ifcType: u.ifcType };
  }
  /** Centro del conjunto de mallas en píxeles CSS relativos al contenedor. */
  project(ms: THREE.Mesh[]): { x: number; y: number } | null {
    if (!ms.length) return null; const box = new THREE.Box3(); ms.forEach((m) => box.expandByObject(m)); box.getCenter(this.v); this.v.y = box.max.y; this.v.project(this.cam);
    if (this.v.z > 1) return null; return { x: (this.v.x * 0.5 + 0.5) * this.host.clientWidth, y: (-this.v.y * 0.5 + 0.5) * this.host.clientHeight };
  }
  /** Rango de altura del modelo (para el control de corte). */
  heightRange(): [number, number] { return [this.bounds.min.y, this.bounds.max.y]; }
  stats() { return { meshes: this.group?.children.length ?? 0, frames: this.frames, selected: this.selected.length, wire: this.wire, xray: this.xray, isolate: this.isolate, section: this.section, visible: this.group?.children.filter((c) => c.visible).length ?? 0 }; }
}
