from dataclasses import dataclass, field

@dataclass(frozen=True)
class DroneModel:
    """Ficha de referencia de un modelo de dron profesional para
    seguridad/vigilancia. Son datos fácticos (fabricante, categoría,
    autonomía, si opera atado o libre) para que el operador elija un
    modelo real al registrar un equipo en `EquipmentRegistry`; no implica
    que el transporte del fabricante esté conectado — eso sigue siendo
    responsabilidad de `equipment_adapters/drone_adapter_boundary.py`
    (fail-closed hasta integrar el SDK correspondiente).
    """
    key: str
    vendor: str
    model: str
    category: str            # multirotor | vtol-hibrido | ala-fija-vtol | tethered
    tethered: bool            # opera atado a una estación (autonomía extendida por cable)
    max_flight_time_min: int | None
    max_altitude_m: int | None
    detection_range_km: float | None
    typical_use: list[str] = field(default_factory=list)


DRONE_CATALOG: list[DroneModel] = [
    DroneModel("dji-mavic-2-enterprise", "DJI", "Mavic 2 Enterprise", "multirotor", False, 31, 500, None,
               ["respuesta a emergencias", "búsqueda y rescate", "despliegue rápido"]),
    DroneModel("dji-matrice-30", "DJI", "Matrice 30 Series", "multirotor", False, 41, 7000, None,
               ["búsqueda y rescate", "vigilancia perimetral", "inspección"]),
    DroneModel("dji-matrice-300-rtk", "DJI", "Matrice 300 RTK", "multirotor", False, 55, 7000, None,
               ["vigilancia de instalaciones", "seguridad", "búsqueda nocturna", "respuesta a incendios"]),
    DroneModel("elistair-orion-2", "Elistair", "Orion 2", "tethered", True, None, 100, 10,
               ["vigilancia fronteriza", "monitoreo perimetral", "supervisión continua 24h"]),
    DroneModel("teal-golden-eagle", "Teal", "Golden Eagle", "multirotor", False, None, None, None,
               ["ISR (inteligencia, vigilancia, reconocimiento)", "localización de personas", "operación nocturna"]),
    DroneModel("easy-aerial-raptor", "Easy Aerial", "Raptor", "tethered", True, 45, None, None,
               ["misiones prolongadas atado", "vuelo libre bajo demanda", "regreso automático a estación"]),
    DroneModel("quantum-systems-vector", "Quantum-Systems", "Vector", "ala-fija-vtol", False, None, None, None,
               ["patrullaje de largo alcance", "despegue/aterrizaje vertical", "bajo ruido"]),
    DroneModel("quantum-systems-scorpion", "Quantum-Systems", "Scorpion", "vtol-hibrido", False, None, None, None,
               ["multi-helicóptero configurable", "misiones variadas"]),
    DroneModel("alpha-unmanned-a900", "Alpha Unmanned Systems", "Alpha 900", "vtol-hibrido", False, None, None, None,
               ["vigilancia marítima y terrestre", "despegue desde buques", "búsqueda y rescate"]),
    DroneModel("autel-dragonfish", "Autel Robotics", "DragonFish", "vtol-hibrido", False, None, None, None,
               ["orden público", "control de tráfico", "cámara térmica para inspección industrial"]),
    DroneModel("av2-pelican", "AV Systems", "AV-2 Pelican", "ala-fija-vtol", False, 17 * 60, 4500, None,
               ["vigilancia de fronteras y ferrocarriles", "inteligencia en tiempo real", "reconocimiento sigiloso"]),
]

_BY_KEY = {d.key: d for d in DRONE_CATALOG}

def get_model(key: str) -> DroneModel | None:
    return _BY_KEY.get(key)
