# Arquitectura de referencia de hardware industrial

## Estado y alcance

Este documento convierte en base de ingeniería la arquitectura solicitada para campo, control local, edge y plataforma. Es un **diseño de referencia**, no un plano IFC/MEP aprobado, una lista de compra, una PCB liberada ni una certificación. No se conoce todavía el inventario real de edificios y activos, el diagrama unifilar, las señales, el ambiente, la revisión del ESP32 ni los requisitos de continuidad. Por tanto, las selecciones de modelos, cantidades, calibres, fuentes, protecciones, antenas y envolventes permanecen abiertas.

La opción B+A+C+B descrita en la información compartida se conserva como **alternativa recomendada para evaluar**: conjunto completo, ESP32 para adquisición con PLC independiente en procesos críticos, arquitectura híbrida local/nube y redundancia con conmutación probada. No es una autorización de compra ni confirma que el sitio tenga esos requisitos.

## Topología de cuatro niveles

```text
Campo / activos
  CI-ENV · CI-WATER · CI-PRESSURE · CI-ENERGY · CI-VIBRATION
  CI-SECURITY · CI-AIR
          │ entradas industriales aisladas / RS-485 / Ethernet
Control local
  ESP32: adquisición, diagnóstico y telemetría no crítica
  PLC/controlador industrial: proceso determinista y enclavamientos
          │ Ethernet segmentada / MQTT con TLS / Modbus donde aplique
Edge del conjunto
  broker local + gateway primario/secundario + cola durable
          │ HTTPS autenticado con identidad de gateway
Plataforma
  API ERP / gemelo BIM-MEP / almacenamiento / mantenimiento / IA gobernada
```

### Responsabilidad por nivel

| Nivel | Función y límite |
|---|---|
| Campo | Sensores adecuados al rango, ambiente y precisión exigidos. Los puntos se registran con ID, unidad, origen, calidad, zona y activo. |
| Control local | ESP32 para lectura y telemetría de riesgo bajo; PLC y hardware certificado para control determinista o funciones relacionadas con seguridad. No conectar GPIO a cargas de red, motores o bombas. |
| Edge | Broker privado, filtrado por identidad y ACL, buffer durable y reenvío idempotente. El respaldo debe cubrir fuentes de alimentación, switch, almacenamiento, red y credenciales, no solo duplicar el gateway. |
| Plataforma | La API, RLS, gemelo digital, colas, auditoría y roles gobiernan el procesamiento; la nube no es dependencia para que una función local de seguridad opere. |

## Familia modular de nodos

| Familia | Señales a especificar | Interfaces posibles (no selección de SKU) |
|---|---|---|
| CI-ENV | Temperatura, humedad; precisión y rango por zona | Sensor digital calibrado; bus industrial cuando cableado/distancia lo requieran |
| CI-WATER | Fuga, nivel, pulsos/caudal | Entrada supervisada, contacto seco, contador aislado o transmisor seleccionado |
| CI-PRESSURE | Presión y rango/precisión del circuito | Transductor industrial; interfaz acondicionada y aislada adecuada al sensor |
| CI-ENERGY | Variables eléctricas y calidad necesaria | Medidor certificado con Modbus; no conexión directa del microcontrolador a tensión de red |
| CI-VIBRATION | Vibración por banda, orientación y montaje | Acelerómetro y/o analizador industrial seleccionado por banda y criticidad |
| CI-SECURITY | Estado de puertas, presencia y tamper | Entrada supervisada y sensores compatibles con el sistema de seguridad aprobado |
| CI-AIR | CO₂ u otras variables ambientales | Sensor con rango, calibración e interfaz verificados |
| CI-GATEWAY | Concentración y store-and-forward | Gateway industrial con Ethernet, RS-485, almacenamiento local y supervisión |

Cada diseño de nodo debe definir alimentación nominal/transitorios, polaridad inversa, protección ESD/surge, aislamiento, puesta a tierra, conectores, gabinete/ingress rating, disipación, etiquetas, calibración, diagnóstico y mantenimiento. Estos valores dependen del sitio y no se inventan aquí.

## Resiliencia y estados degradados

| Fallo | Comportamiento requerido | Estado actual observado / trabajo restante |
|---|---|---|
| Sensor ausente o fuera de rango | Marcar calidad/falla; nunca fabricar una lectura | El backend clasifica calidad de telemetría; validar cada driver y alarma HIL |
| Pérdida de Wi-Fi del ESP32 | Seguir en estado seguro y reconectar sin ciclo de reinicio | El firmware ya no reinicia tras un timeout inicial; **no** tiene outbox persistente del nodo, así que puede perder eventos no publicados |
| Broker desconectado | Persistir antes de confirmar y reenviar con ID idempotente | El gateway C++ usa SQLite/WAL para el tramo broker→API; el ESP32 no confirma store-and-forward durable |
| Caída de Internet/API | Operación local y cola edge durable; alertar al vencer la retención | Existe el buffer del gateway; falta probar red caída/recuperada, límites y retención en el sitio |
| Gateway primario caído | Failover con estado/cursor recuperable y sin doble operación | Hay arquitectura y perfiles de gateway; no hay evidencia de conmutación física ni de clúster activo-activo |
| Alimentación interrumpida | UPS dimensionada, apagado ordenado y recuperación comprobada | No hay análisis de carga/tiempo de autonomía ni esquema eléctrico del sitio |
| DB perdida | Backup, réplica, retención y restauración probada con RPO/RTO aprobados | No se han aportado RPO/RTO ni evidencia de restauración del despliegue objetivo |
| OTA incompleta o defectuosa | Firma autorizada, particiones válidas, rollback probado y anillo de despliegue | El gestor OTA firmware actual no valida todavía un manifiesto de versión/hash; ver bloqueo de Secure Boot y particiones |

No usar “alta disponibilidad” como afirmación hasta superar pruebas de pérdida de cada dependencia compartida y registrar tiempos de detección, failover, recuperación, pérdida/duplicación de eventos y evidencia.

## Seguridad de campo y firmware

- Segmentar OT/IT; permitir solo flujos definidos. No exponer broker ni puertos de control a Internet.
- TLS en MQTT y HTTPS con verificación de CA/hostname. Credenciales distintas por identidad y capacidad de revocar/rotar; la verificación TLS del broker no reemplaza autenticación por dispositivo.
- Autenticar mensajes de campo según el modelo de claves aprobado; incluir tenant/device derivados de identidad confiable, secuencia monotónica durable, hora/calidad y esquema. Evitar claves globales compartidas.
- Secure Boot y cifrado NVS/flash dependen de variante/revisión y del proceso de fabricación. Custodia externa, recuperación y rotación son requisito previo; activar efuses o protecciones irreversibles solo con procedimiento aprobado y placa de producción identificada.
- La OTA debe autenticar publicación/firmware, aplicar comparación estricta de versiones y política anti-downgrade, admitir rollback, ser atómica, y probar cortes de red/alimentación. SHA-256 sin firma/autenticación del origen solo prueba igualdad con el hash recibido.
- El provisionamiento requiere identidad del técnico, autorización vigente, desafío de un solo uso, límites de intentos y auditoría. El repositorio no debe recibir claves privadas.

## Bloqueos medibles del hardware ESP32 actual

1. [`edge/esp32-firmware/edge/esp32/firmware/partitions.csv`](../edge/esp32-firmware/edge/esp32/firmware/partitions.csv) es el perfil de desarrollo con una app grande; [`partitions.release.csv`](../edge/esp32-firmware/edge/esp32/firmware/partitions.release.csv) reserva dos ranuras OTA de 832 KiB y 256 KiB de almacenamiento. Ambos mapas validan contra los 2 MiB informados. La imagen debug mide 1,282,457 bytes y excede cada ranura OTA; no sustituye la medición del build optimizado release. Falta confirmar por lectura la flash física.
2. El build release con `sdkconfig` aislado selecciona `ESP32_REV_MIN=0` y Secure Boot V1, y CMake lo rechaza (`Secure Boot v1 is not supported`). En ESP32 clásico, V2 RSA requiere revisión 3 o posterior. No subir revisión mínima por software: confirmar el chip real antes de configurarla.
3. No existe una clave de release disponible y no se generará ni compartirá una. El build firmado queda bloqueado hasta acordar emisor/custodia y un flujo compatible con el secure boot del hardware.
4. No hay placa identificada conectada: los puertos detectados fueron Bluetooth serial. No se ejecutó lectura de chip/flash, flasheo, burn de efuses ni prueba OTA en hardware.
5. El firmware usa pines ESP32 fijos para PIR, magnético y tamper. No se ha aprobado el acondicionamiento eléctrico ni la correspondencia física de esos pines con una placa industrial.

## Pruebas de calificación (cada una con ID, resultado y evidencia)

1. Inspección de BOM/compatibilidad, alimentación, aislamiento, temperatura, humedad, EMC y certificaciones aplicables al uso real.
2. Arranque repetido, reinicio espontáneo, pérdida/restauración de energía y revisión de integridad de NVS/cola.
3. Sensor desconectado, cortocircuitado, fuera de rango, unidad inválida y dato `STALE`.
4. Pérdida de Wi-Fi, Ethernet, MQTT, API y DNS; recuperar y reconciliar secuencias sin pérdidas o duplicados no explicados.
5. Caída de broker, switch, gateway, almacenamiento, DB y proveedor de energía; medir conmutación y restauración.
6. Autenticación inválida, tenant cruzado, nonce repetido, secuencia antigua, reloj fuera de tolerancia, credencial revocada y límites de tasa.
7. OTA válida/no válida, firma/hash incorrectos, versión downgrade, descarga truncada, reinicio/corte durante cada fase y rollback en cada variante de placa.
8. Prueba de carga de telemetría sostenida y ráfagas, memoria/almacenamiento llenos, retención, backup y restauración.
9. HIL con planos/versiones IFC reales y bindings aprobados; comprobar que topología no se comunica como impacto físico confirmado.
10. Prueba de continuidad y failover extremo a extremo con evidencia independiente; simulación no cuenta como prueba física.

## Datos necesarios antes de congelar diseño/BOM

- Listado de edificios, zonas, equipos y criticidad; inventario/GlobalId de IFC y activos CMMS enlazados.
- Puntos por activo: variable, rango, unidad, precisión, frecuencia, calidad, umbrales aprobados, ubicación y condición de calibración.
- Diagramas eléctricos, tensión/puesta a tierra, tableros, cargas, fuentes, UPS y normas/certificaciones exigibles.
- Protocolos de los equipos existentes, distancias, rutas de cable, interferencia RF, VLAN, fibra/switches y cobertura de respaldo.
- Condiciones ambientales e IP/NEMA requerido por ubicación; montaje y accesibilidad de mantenimiento.
- Modelo de hosting, RTO/RPO, retención, tasas de telemetría, canales de emergencia y roles humanos.
- Módulo/chip exacto, revisión, flash/RAM, interfaces disponibles y método de producción/programación.

Hasta recibir y validar esos datos, el entregable correcto es esta arquitectura y la matriz de requisitos; no una lista de compra o plano supuestamente definitivo.
