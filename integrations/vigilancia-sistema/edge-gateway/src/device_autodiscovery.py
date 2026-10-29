import asyncio
import time
from dataclasses import dataclass, field

import httpx

# Firmas conocidas por puerto/cabecera para identificar marca y protocolo sin
# credenciales. En producción real esto se amplía con WS-Discovery (ONVIF,
# puerto 3702/UDP) y RTSP DESCRIBE; aquí se deja el punto de extensión listo
# (`SIGNATURES`) para añadir fabricantes sin tocar el resto del módulo.
SIGNATURES = [
    {"port": 80, "header_contains": "hikvision", "vendor": "Hikvision", "protocol": "ONVIF", "compatibility": "NATIVE"},
    {"port": 80, "header_contains": "dahua", "vendor": "Dahua", "protocol": "ONVIF", "compatibility": "NATIVE"},
    {"port": 554, "header_contains": "rtsp", "vendor": "Genérico RTSP", "protocol": "RTSP", "compatibility": "COMPATIBLE"},
    {"port": 8000, "header_contains": "onvif", "vendor": "ONVIF genérico", "protocol": "ONVIF", "compatibility": "COMPATIBLE"},
]
PROBE_PORTS = sorted({s["port"] for s in SIGNATURES})

@dataclass
class DiscoveredDevice:
    device_id: str
    device_class: str  # CAMERA | SENSOR_IR | SENSOR_LASER | GATEWAY | UNKNOWN
    vendor: str
    model: str
    protocol: str
    address: str
    compatibility: str  # NATIVE | COMPATIBLE | LIMITED | UNKNOWN
    zone: str = ""
    auto_connected: bool = False
    stream_url: str | None = None
    last_seen: float = field(default_factory=time.time)


class DeviceAutoDiscovery:
    """Escaneo activo de la red local para detectar equipos, identificar
    marca/modelo/protocolo por firma y conectarlos automáticamente.

    `probe_address` es el punto de extensión real (sondeo TCP + lectura de
    cabeceras HTTP). `scan` lo aplica sobre una lista de direcciones y
    mantiene un registro en memoria consultable por el dashboard incluso
    si el backend central no está disponible.
    """

    def __init__(self):
        self._registry: dict[str, DiscoveredDevice] = {}

    async def probe_address(self, address: str, zone: str = "") -> DiscoveredDevice | None:
        for port in PROBE_PORTS:
            try:
                async with httpx.AsyncClient(timeout=1.5) as c:
                    r = await c.get(f"http://{address}:{port}/", follow_redirects=False)
                    banner = (r.headers.get("server", "") + " " + r.text[:200]).lower()
            except Exception:
                continue
            for sig in SIGNATURES:
                if sig["port"] != port:
                    continue
                if sig["header_contains"] in banner:
                    device_class = "CAMERA" if sig["protocol"] in ("ONVIF", "RTSP") else "UNKNOWN"
                    return DiscoveredDevice(
                        device_id=f"disc-{address.replace('.', '-')}-{port}",
                        device_class=device_class, vendor=sig["vendor"], model="auto-detectado",
                        protocol=sig["protocol"], address=address, compatibility=sig["compatibility"], zone=zone,
                    )
        return None

    async def scan(self, addresses: list[str], zone: str = "") -> list[DiscoveredDevice]:
        results = await asyncio.gather(*(self.probe_address(a, zone) for a in addresses), return_exceptions=False)
        found = [r for r in results if r is not None]
        for d in found:
            self.auto_connect(d)
        return found

    def auto_connect(self, device: DiscoveredDevice) -> DiscoveredDevice:
        """Conexión automática: para dispositivos NATIVE/COMPATIBLE se
        construye de inmediato la URL de stream según el protocolo
        detectado, sin intervención manual del operador."""
        if device.protocol in ("ONVIF", "RTSP") and device.compatibility in ("NATIVE", "COMPATIBLE"):
            device.stream_url = f"rtsp://{device.address}:554/stream1"
            device.auto_connected = True
        device.last_seen = time.time()
        self._registry[device.device_id] = device
        return device

    def all(self) -> list[DiscoveredDevice]:
        return list(self._registry.values())

    def register_manual(self, device: DiscoveredDevice) -> DiscoveredDevice:
        """Alta manual (p. ej. sensores IR/láser que no hablan HTTP y se
        anuncian solo por MQTT heartbeat) para que también aparezcan en el
        inventario unificado de auto-descubrimiento."""
        self._registry[device.device_id] = device
        return device
