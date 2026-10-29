import json
import aio_pika

class ChainCommunicator:
    """Puente entre el orquestador de agentes y el resto de la malla
    (edge-gateway → MQTT → dispositivos). Publica en `actions.fanout`;
    el edge-gateway consume ese exchange y traduce cada acción aprobada
    a un mensaje MQTT `actions/execute` que el firmware ejecuta.

    Esta clase nunca decide si una acción se ejecuta: solo transporta
    acciones ya resueltas (aprobadas por humano o auto-aprobadas por ser
    no destructivas) hacia el borde de la red.

    Nota de topología: la cascada láser/IR → cámaras vecinas (reorientación
    inmediata al interrumpirse una barrera) NO se coordina desde aquí — vive
    en `edge-gateway/src/sensor_mesh.py` y se dispara localmente en el borde,
    sin esperar un viaje de ida y vuelta a este servicio central (autonomía
    de borde). Este comunicador solo transporta el resto de las acciones ya
    resueltas por el loop de agentes (alarmas, bloqueos, notificaciones,
    grabación) hacia dispositivos que no están gobernados por
    `EquipmentRegistry` (ver `agent_loop.py::_dispatch`).
    """

    def __init__(self, channel: aio_pika.Channel):
        self.channel = channel
        self.exchange: aio_pika.Exchange | None = None

    async def start(self):
        self.exchange = await self.channel.declare_exchange("actions.fanout", aio_pika.ExchangeType.FANOUT, durable=True)

    async def dispatch(self, action_id: str, action_type: str, target_device_id: str | None, zone: str | None, payload: dict):
        if self.exchange is None:
            raise RuntimeError("ChainCommunicator no inicializado: llama a start() primero")
        body = json.dumps({
            "action_id": action_id, "action_type": action_type,
            "target_device_id": target_device_id, "zone": zone, "payload": payload,
        }, separators=(",", ":")).encode()
        await self.exchange.publish(
            aio_pika.Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT, content_type="application/json"),
            routing_key="",
        )
