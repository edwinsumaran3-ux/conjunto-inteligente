import json
import os

class SensorMesh:
    """Topología de adyacencia sensor→cámaras vecinas para la comunicación
    en cadena descrita como requisito: al interrumpirse una barrera
    láser/IR, las cámaras contiguas al punto de intrusión deben
    reorientarse de inmediato, sin esperar un viaje de ida y vuelta al
    backend central (autonomía de borde).

    La topología se carga desde `MESH_TOPOLOGY_JSON` (variable de entorno
    con un JSON `{sensor_id: [camera_id, ...]}`) o desde un archivo local;
    si no hay nada configurado, cae a un mapa vacío y simplemente no
    cascadea (el evento igual se reenvía al pipeline central).
    """

    def __init__(self, topology_path: str = "/var/lib/edge/mesh_topology.json"):
        self.topology_path = topology_path
        self._map: dict[str, list[str]] = self._load()

    def _load(self) -> dict[str, list[str]]:
        raw = os.getenv("MESH_TOPOLOGY_JSON")
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
        if os.path.exists(self.topology_path):
            try:
                with open(self.topology_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def reload(self):
        self._map = self._load()

    def neighbors(self, sensor_id: str) -> list[str]:
        return list(self._map.get(sensor_id, []))

    def register_link(self, sensor_id: str, camera_ids: list[str]):
        """Permite registrar adyacencias dinámicamente (p. ej. tras un
        auto-descubrimiento que infiere cercanía por zona)."""
        self._map[sensor_id] = sorted(set(self._map.get(sensor_id, []) + camera_ids))
        try:
            os.makedirs(os.path.dirname(self.topology_path), exist_ok=True)
            with open(self.topology_path, "w", encoding="utf-8") as f:
                json.dump(self._map, f)
        except OSError:
            pass

    def cascade_commands(self, sensor_id: str, zone: str) -> list[dict]:
        """Devuelve los comandos MQTT locales de reorientación de cámara
        para cada vecino del sensor que disparó el evento."""
        return [
            {"topic": f"cameras/{cam_id}/focus", "payload": {"source_sensor": sensor_id, "zone": zone, "reason": "perimeter_cascade"}}
            for cam_id in self.neighbors(sensor_id)
        ]
