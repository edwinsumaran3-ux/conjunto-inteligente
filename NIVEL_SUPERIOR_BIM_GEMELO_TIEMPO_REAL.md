# Conjunto Inteligente — revisión y evolución BIM / Gemelo Digital / Skill UI

**Entrega de ingeniería:** UI-SUPERIOR-01  
**Estado:** ampliación parcial sobre la recuperación disponible; no equivale a certificación productiva.

## 1. Integridad del insumo y alcance real

El archivo ZIP de entrada no tenía directorio central ZIP legible. Se intentó recuperación y se extrajo un subconjunto mediante salvamento de entradas locales. La recuperación no conserva todos los archivos: por ejemplo, una prueba referencia `domain/cobie.py`, que no está presente en el árbol recuperado. Por ello se preservó el código recuperado, se mantuvo una copia `frontend/centro-mando/index.pre-nivel-superior.html` de la interfaz anterior y se añadieron artefactos nuevos sin eliminar intencionalmente módulos previos.

No afirmar que el ZIP original quedó íntegro ni que toda la plataforma pasó pruebas end-to-end. Para una fusión completa se necesita que el usuario vuelva a proporcionar el ZIP íntegro, idealmente verificando que `unzip -t archivo.zip` termine sin errores.

## 2. Cambios de esta iteración

- Se elevó `frontend/centro-mando/index.html` a un centro de mando responsive para escritorio y móvil, con navegación modular, KPIs, grafo del gemelo, capas visuales, salud de datos, eventos derivados de estados y accesos de ingeniería.
- La vista consume `GET {API_BASE}/digital-twin/graph` y representa los nodos/relaciones que devuelve el backend autenticado. Si no hay API o permisos válidos, indica desconexión y no presenta cifras operacionales inventadas.
- Se configuró consulta periódica del grafo cada 10 segundos. **Esto es polling de refresco, no streaming de telemetría en tiempo real garantizado.** Para operación realmente en tiempo real debe integrarse un canal de eventos autenticado (WebSocket/SSE o broker pub/sub) y sus métricas de latencia, reconexión y pérdida.
- La maqueta geométrica es explícitamente ilustrativa hasta que se importe y visualice geometría IFC real. No se presenta como modelo BIM cargado.
- El token se guarda en `sessionStorage` durante la sesión del navegador, no en almacenamiento persistente. Aun así, la versión de producción debe utilizar la sesión corporativa segura, HTTPS, CSP estricta y evitar credenciales duraderas en almacenamiento accesible por JavaScript.
- Se añadió esta revisión y una matriz de brechas y pruebas.

## 3. Capacidades BIM / gemelo digital observadas en el código recuperado

En `backend/app/modules/digital_twin/api/router.py` existen rutas para grafo, nodos, relaciones, telemetría, versiones de modelo, vínculos, referencias espaciales, snapshots, dispositivos/puntos, diagnósticos, cadenas de falla, solicitudes de mantenimiento, validación/importación IFC, CDE, COBie, IDS y auditoría de hojas COBie. Su presencia en el archivo no demuestra por sí sola que estén registradas en la aplicación, migradas en una base desplegada o protegidas y operativas de punta a punta.

El dominio recuperado incluye geometría/ubicación IFC, evaluación de requisitos BIM, ingestión IFC, telemetría operacional, diagnósticos y análisis de cadenas de falla. Debe verificarse contra migraciones, contratos, configuración de tenant, permisos y tests completos en la copia íntegra del proyecto.

## 4. Arquitectura objetivo superior

### BIM + gemelo digital

1. **CDE y versiones:** IFC/IFC4x3, COBie, IDS, documentos, hashes, origen, revisión y estados de aprobación; versionado inmutable y comparación entre revisiones.
2. **Modelo semántico:** edificio → torre → nivel → espacio → sistema → activo → dispositivo → punto de medición; relaciones con IDs estables, unidades, ubicación y procedencia.
3. **Vínculos físicos-digitales:** identificador de activo, sensor, fabricante, protocolo, ubicación, modelo/version, confianza del vínculo y fecha de verificación.
4. **Estado temporal:** valor observado, hora del sensor, hora de recepción, unidad original/canónica, calidad, motivo, retraso, correlación y retención.
5. **Motor de reglas y diagnóstico:** límites de ingeniería por activo, deduplicación, ventanas temporales, correlación de eventos, hipótesis explicables y evidencia citada.
6. **Mantenimiento:** evento → triage → orden propuesta → aprobación humana → proveedor → ejecución → evidencia antes/después → revisión → cierre y costo ERP.
7. **Auditoría:** quién/qué/cuándo/por qué, versión de regla/modelo, evidencia usada, cambio anterior/nuevo y resultado.

### Tiempo real de producción

- Ingesta edge/broker (MQTT/OPC-UA/HTTP según dispositivo) con identidad de dispositivo, firma o autenticación mutua, límites de tasa, idempotencia y secuencias.
- Pub/sub (por ejemplo Redis Streams, NATS o Kafka según escala) para desacoplar ingestión, reglas, notificaciones y proyección UI.
- WebSocket/SSE autenticado para cambios incrementales; heartbeat, reconexión con backoff, `Last-Event-ID`/cursor, detección de huecos y sincronización completa al reconectar.
- La UI debe mostrar **última observación**, **última recepción**, **frescura**, **calidad** y **estado de conexión** por señal. Sin datos recientes, mostrar “obsoleto/desconocido”, nunca convertirlo en “normal”.
- Objetivos SLO a definir por criticidad (p. ej. P95 evento→UI), con pruebas de carga, pérdida de broker, desconexión edge y recuperación.

### Skill UI y agentes

Cada herramienta/skill debe declarar: ID y versión; propósito; esquema de entrada/salida; scopes/permisos; tenant; precondiciones; timeout; presupuesto de ejecución; nivel de riesgo; fuentes/evidencias; idempotency key; modo de simulación claramente etiquetado; aprobación requerida; resultado estructurado; trazabilidad; política de reintento; compensación y evaluación offline. No se debe permitir que un agente invente una lectura, modifique controles físicos o compre/contrate sin autorización explícita.

### Seguridad y gobierno

- Aislamiento multi-tenant comprobado en cada query, job, stream y caché.
- RBAC/ABAC por edificio, módulo y acción; mínimo privilegio para skills.
- Gestión de secretos fuera del frontend; rotación; TLS; validación de payload; límites de tamaño; rate limiting y protección replay.
- Registro de auditoría append-only, correlación distribuida, métricas y trazas OpenTelemetry.
- Retención y acceso a imágenes/cámaras sujetos a política, consentimiento y normativa aplicable.
- Backups probados, restauración, migraciones reversibles cuando sea posible y recuperación ante desastre.

## 5. Matriz de brechas

| Área | Observado en recuperación | Siguiente criterio de aceptación |
|---|---|---|
| Centro de mando | UI nueva, adaptable; consulta de grafo configurable | Pruebas de navegador móvil/escritorio, accesibilidad y fallos de API |
| BIM | Rutas y módulos de dominio presentes | Importar IFC real, validar geometría/IDS, conservar versión/hash y probar archivos malformados |
| Gemelo | Grafo de nodos/relaciones y snapshots en API | Modelo semántico completo, vínculos verificados, snapshots temporales y comparación de versiones |
| Tiempo real | Refresco del grafo cada 10 s | Canal SSE/WebSocket/broker, latencia medida, cursor, reconexión y huecos |
| Telemetría | Endpoints de ingesta/consulta presentes | Normalización, calidad, frescura, deduplicación, límites y pruebas de carga |
| Agentes / Skill UI | Componentes y rutas de diagnóstico presentes parcialmente | Contratos versionados, permisos, evidencia, aprobaciones, evaluaciones y sandbox |
| Mantenimiento | Endpoint de solicitud desde diagnóstico presente | Workflow completo, aprobación humana, proveedores, evidencia y cierre ERP |
| Seguridad | Dependencias de autenticación/tenant referenciadas en router | Verificar código base completo, pruebas negativas, RLS, scopes y aislamiento de streams |
| Persistencia | Consultas SQL y tablas `twin_*` referenciadas | Confirmar migraciones, índices, constraints, RLS, retención y restauración |
| Pruebas | Hay tests del dominio | Suite completa, integración con PostgreSQL, frontend E2E, carga, caos y seguridad |

## 6. Validación ejecutada en la copia recuperada

- JavaScript del nuevo HTML: `node --check` correcto.
- Compilación sintáctica Python del módulo de gemelo: `python -m compileall` completó sin error en los archivos presentes.
- Suite de pruebas de gemelo digital: **bloqueada en recolección** porque falta `backend/app/modules/digital_twin/domain/cobie.py`, requerido por `test_cobie_and_ids.py`. La ausencia es consistente con la recuperación parcial; no se debe atribuir a un fallo funcional confirmado del ZIP original.
- No se ejecutaron pruebas de integración contra PostgreSQL, dispositivos, broker, credenciales reales ni despliegue. No hay base para afirmar disponibilidad de producción.

## 7. Puerta de aceptación antes de producción

1. Recuperar ZIP íntegro y comparar inventario/hashes contra esta copia.
2. Ejecutar migraciones en entorno limpio y actualización desde una base con datos.
3. Probar aislamiento tenant y permisos negativos en todos los endpoints y canales en tiempo real.
4. Cargar modelos IFC de referencia y comprobar geometría, jerarquía, IDs, coordenadas y resultados IDS/COBie.
5. Simular sensor obsoleto, reloj desfasado, valores fuera de rango, duplicados, pérdida de red y recuperación.
6. Ejecutar Playwright/Cypress en móvil y escritorio, pruebas de accesibilidad, carga y caos.
7. Confirmar métricas/SLO, alertas, backups/restauración, documentación operativa y aprobación humana de acciones críticas.

**Conclusión:** la iteración fortalece la interfaz y define el camino técnico para BIM/gemelo/skills. La plataforma completa todavía no puede certificarse como “tiempo real productivo” mientras falten el ZIP íntegro, la conexión de eventos en streaming y la validación end-to-end del despliegue.
