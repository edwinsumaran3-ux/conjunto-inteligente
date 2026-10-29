# Laboratorio IoT de sensores virtuales

## Propósito y límites

El laboratorio permite desarrollar y probar el flujo operativo antes de comprar o instalar sensores. Registra dispositivos de tipo `virtual_sensor`, crea puntos en el gemelo digital y envía muestras a las tablas y servicios de telemetría existentes. No crea una pila de IoT paralela.

Toda muestra del simulador lleva `source=virtual-sensor-simulator`, `data_origin=simulated` y `hardware_connected=false`. Los escenarios de humo y ascensor son demostraciones sintéticas. No se conectan a equipos, no representan una condición física real y no pueden accionar actuadores.

La simulación no requiere ni implementa un broker MQTT. Para hardware, la API ofrece una ruta HTTPS de pasarela física autenticada con Ed25519; MQTT y la conexión a un broker siguen sin estar implementados.

## Uso desde el centro de mando

1. Inicia sesión en el dashboard y crea o importa nodos del gemelo digital.
2. Abre **Sensores y señales**.
3. Selecciona un nodo, un tipo de sensor y, opcionalmente, un código.
4. Crea el sensor virtual.
5. Ejecuta **Lectura normal** para probar el flujo esperado o **Simular alarma** para generar una condición de prueba.
6. Revisa las lecturas, la calidad y el diagnóstico. Si se detecta una desviación, consulta **Incidencias y mantenimiento**.

Un identificador de ejecución nuevo se genera para cada acción de la interfaz. La API también acepta un `run_id` fijo para que los reintentos de una misma operación no dupliquen las muestras.

## Contratos de API

Todos los endpoints requieren la sesión autenticada del tenant:

- `GET /api/v1/digital-twin/simulations/catalog`: perfiles y límites de ingeniería disponibles.
- `GET /api/v1/digital-twin/simulations/devices`: dispositivos virtuales del tenant actual y su última lectura.
- `POST /api/v1/digital-twin/simulations/devices`: crea el dispositivo y su punto en una transacción.
- `POST /api/v1/digital-twin/simulations/devices/{device_id}/run`: genera cinco muestras sintéticas, las ingresa mediante el procesamiento operativo existente y evalúa el nodo.
- `POST /api/v1/digital-twin/telemetry/samples/batch`: valida e ingresa de forma atómica hasta 500 muestras con claves de idempotencia obligatorias.

## Ingesta por lotes para escalar

Las pasarelas pueden agrupar mensajes en solicitudes de hasta 500 muestras. Cada lote se valida por completo antes de insertar, limita la búsqueda de puntos al tenant autenticado, normaliza unidades y clasifica calidad con las mismas reglas de la ingesta individual. La escritura usa un `INSERT` multi-fila, evita duplicados concurrentes mediante la restricción única existente, y actualiza cada estado de punto y dispositivo una vez por lote. Si una clave de mensaje ya existe con otro contenido, o una muestra es inválida, se rechaza el lote en vez de aceptar una parte silenciosamente. Las reejecuciones con contenido idéntico responden como duplicadas.

La ingesta por lotes reduce viajes a la base de datos; no reemplaza una cola duradera ni pretende procesar cargas ilimitadas dentro de una petición HTTP. Para volumen continuo superior al presupuesto del API deben añadirse consumidores asíncronos con backpressure, límites de tasa por tenant/dispositivo, métricas de cola y pruebas de carga con infraestructura de producción.

## Pasarela física autenticada

`POST /api/v1/edge-transport/telemetry/batch` recibe hasta 500 muestras firmadas. La firma Ed25519 cubre el cuerpo completo y el envelope `{gateway_id, nonce, sequence, payload}` con la serialización canónica del transporte; el `payload` se normaliza al esquema JSON de la API, incluidas las fechas ISO-8601. Debe enviarse además `X-Edge-Tenant-Id`; el tenant debe coincidir con la credencial activa de la pasarela. El nonce y la secuencia se validan y registran dentro de la misma transacción que la telemetría.

La pasarela debe estar asignada a un nodo BIM. Solo puede publicar puntos asociados a ese nodo o a sus descendientes dentro del mismo tenant. El servidor reemplaza `source`, antepone el ID de la pasarela al ID de mensaje y fuerza los metadatos de procedencia física, por lo que los campos declarados por el dispositivo no pueden etiquetar telemetría como simulada ni atribuirla a otra pasarela. Un gateway no asignado, deshabilitado, una credencial inválida, un replay o un punto fuera de su ámbito se rechazan. Si una nueva petición firmada retransmite una muestra idéntica con el mismo `source_message_id`, la telemetría se deduplica aunque la petición use un nonce y una secuencia de transporte nuevos.

El endpoint prueba autenticidad e integridad de la solicitud, no calibración, seguridad operacional ni veracidad física del sensor. La credencial debe provisionarse y rotarse fuera del flujo de ingestión. MQTT y las colas duraderas todavía requieren implementación y validación específica.

La admisión física tiene límites por gateway aplicados atómicamente por PostgreSQL y compartidos entre instancias de la API. De forma predeterminada permite hasta 120 solicitudes y 10 000 muestras por minuto por pasarela; al exceder cualquiera devuelve `429 EDGE_TELEMETRY_RATE_LIMITED` con `Retry-After: 60`. Se configuran con `EDGE_TELEMETRY_MAX_REQUESTS_PER_MINUTE` y `EDGE_TELEMETRY_MAX_SAMPLES_PER_MINUTE`. El contador se reinicia por ventana de reloj de un minuto y ocupa una fila por gateway, no crece por minuto. La política limita telemetría firmada aceptada; no reemplaza protección de red/WAF contra tráfico anónimo ni límites globales por tenant.

El anti-replay mantiene además el máximo `last_sequence` en la fila del gateway. Las solicitudes firmadas serializan por gateway; la secuencia debe ser estrictamente creciente y actualiza el watermark en la misma transacción del evento, heartbeat, pull firmado o lote de telemetría. El historial de nonce se conserva 30 días y se purga oportunistamente en lotes máximos de 1000 filas por petición autenticada; por ello un historial vencido ya no permite aceptar una secuencia antigua. El almacenamiento de auditoría es acotado para gateways activos, mientras los gateways inactivos pueden conservar su último bloque de historial hasta que vuelvan a enviar una solicitud.

Ejemplo de creación:

```json
{
  "node_id": "UUID-de-un-nodo-del-tenant",
  "profile_id": "temperature",
  "code": "SIM-TORRE-A-TEMP-01",
  "name": "Temperatura virtual sala de bombas"
}
```

Ejemplo de ejecución:

```json
{
  "run_id": "UUID-nuevo-por-ejecucion",
  "scenario": "alarm"
}
```

`scenario` admite `normal` y `alarm`. El perfil de presencia no admite alarma. La respuesta incluye el estado de cada muestra y, cuando hay datos suficientes, el identificador y resultado del diagnóstico determinista. Las muestras sintéticas se pueden consultar con las mismas vistas y endpoints de telemetría que las demás lecturas.

## Idempotencia y límites de seguridad

- Los mensajes se identifican con `sim:{device_id}:{run_id}:{sample_index}` y aprovechan la unicidad de `source_message_id` existente.
- Reutilizar un `run_id` con un escenario diferente se rechaza con `409`.
- El listado, creación y consulta respetan el tenant autenticado y las políticas RLS vigentes.
- El endpoint de simulación solo opera sobre dispositivos etiquetados `data_origin=simulated`.
- El endpoint físico solo acepta gateways con credencial Ed25519 activa y alcance BIM asignado; los controles de replay se serializan por fila de gateway.
- Ningún flujo de simulación autoriza comandos en `physical_edge` ni sustituye los enclavamientos de seguridad.
- Las anomalías resultantes son diagnósticos de pruebas y deben tratarse como tales durante las demostraciones.

## Catálogo implementado

Temperatura, humedad, fuga de agua, presencia, humo, consumo eléctrico, presión, vibración, calidad del aire y estado de ascensor. Cada perfil declara unidad, límites, comportamiento normal y si permite generar una alarma sintética.

El simulador genera cinco valores deterministas por ejecución; el último representa el valor de alarma en ese escenario. Por eso repetir el mismo `run_id` es reproducible. Los puntos se mantienen asociados al nodo seleccionado, sin fabricar edificios, espacios, geometría BIM o dispositivos físicos.

## Validación pendiente antes de hardware

Las pruebas automatizadas cubren generación reproducible, límites, perfiles de seguridad y el contrato HTTP del frontend. La ejecución contra una instancia real de PostgreSQL valida además migraciones, RLS, permisos por tenant, persistencia, anomalías y publicación de eventos. La integración física requerirá pruebas adicionales con los dispositivos y pasarelas seleccionados, certificados y configuración de red.
