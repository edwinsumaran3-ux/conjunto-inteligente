// @vitest-environment node
import * as THREE from "three";
import { describe, expect, it } from "vitest";
import { createEquipmentProxyMeshes, fitCameraPose } from "./scene3d";

const identity = { globalId: "pump-guid", expressID: 7, name: "Bomba B1", ifcType: "IFCPUMP" };

function bounds(x: number, y: number, z: number) {
  return new THREE.Box3(new THREE.Vector3(0, 0, 0), new THREE.Vector3(x, y, z));
}

function unionBounds(meshes: THREE.Mesh[]) {
  const result = new THREE.Box3();
  meshes.forEach((mesh) => result.expandByObject(mesh));
  return result;
}

describe("representación 3D paramétrica de activos IFC", () => {
  it("mantiene una distancia de encuadre válida al enfocar un activo", () => {
    const pose = fitCameraPose(new THREE.Vector3(18, 14, 18), new THREE.Vector3(5, 4.5, -4), bounds(2, 1, 1));
    expect(pose.target.toArray()).toEqual([1, 0.5, 0.5]);
    expect(pose.position.distanceTo(pose.target)).toBeGreaterThan(5);
    expect(pose.position.x).toBeGreaterThan(pose.target.x);
    expect(pose.position.z).toBeGreaterThan(pose.target.z);
  });

  it("representa una bomba horizontal con piezas mecánicas y giro X", () => {
    const meshes = createEquipmentProxyMeshes(identity, bounds(2, 1, 1));
    const geometryTypes = new Set(meshes.map((mesh) => mesh.geometry.type));
    expect(meshes.length).toBeGreaterThan(12);
    expect(geometryTypes).toContain("CylinderGeometry");
    expect(geometryTypes).toContain("SphereGeometry");
    expect(geometryTypes).toContain("TorusGeometry");
    expect(meshes.length).toBeGreaterThan(40);
    expect(unionBounds(meshes).min.toArray().every((value) => value >= -0.02)).toBe(true);
    expect(unionBounds(meshes).max.toArray().every((value, axis) => value <= [2, 1, 1][axis] + 0.02)).toBe(true);
    expect(meshes.some((mesh) => Math.abs(mesh.rotation.z) > 1)).toBe(true);
    expect(new Set(meshes.map((mesh) => (mesh.material as THREE.MeshStandardMaterial).color.getHex())).size).toBeGreaterThan(2);
  });

  it("orienta el eje del motor Z cuando el IFC es más largo en profundidad", () => {
    const meshes = createEquipmentProxyMeshes(identity, bounds(1, 1, 2));
    expect(meshes.some((mesh) => Math.abs(mesh.rotation.x) > 1)).toBe(true);
    const result = unionBounds(meshes);
    expect(result.min.toArray().every((value) => value >= -0.02)).toBe(true);
    expect(result.max.toArray().every((value, axis) => value <= [1, 1, 2][axis] + 0.02)).toBe(true);
  });

  it("usa un cuerpo cilíndrico y anillos para tanques, no una caja", () => {
    const meshes = createEquipmentProxyMeshes({ ...identity, ifcType: "IFCTANK" }, bounds(1, 2, 1));
    expect(meshes.length).toBeGreaterThan(10);
    expect(meshes.some((mesh) => mesh.geometry.type === "CylinderGeometry")).toBe(true);
    expect(meshes.some((mesh) => mesh.geometry.type === "TorusGeometry")).toBe(true);
    expect(meshes.every((mesh) => mesh.geometry.type !== "BoxGeometry")).toBe(true);
  });

  it("no genera proxies para otras clases IFC", () => {
    expect(createEquipmentProxyMeshes({ ...identity, ifcType: "IFCWALL" }, bounds(2, 1, 1))).toEqual([]);
  });
});