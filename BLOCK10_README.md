# BLOQUE 10 — Fleet + OTA + Edge Mesh + Store-and-Forward + HIL

Este bloque **se agrega sobre el Bloque 09 y no elimina sus archivos**.

Incluye:
- identidad/credenciales por dispositivo y revocación preparada;
- registro de firmware y manifiestos firmados;
- despliegues OTA por anillos canary/pilot/production/emergency;
- política de rollback y trazabilidad de deployment;
- topología mesh padre/hijo con health/latencia/pérdida;
- store-and-forward de eventos con hash, reintentos y dead-letter;
- watchdog que lleva un nodo armado a `safe` ante timeout;
- HIL determinista para pérdida de red, duplicados, clock skew y caída de gateway;
- RLS y aislamiento por tenant.

## Límite honesto
El HIL es un simulador controlado. No se afirma validación sobre ESP32, cámaras, drones, bombas, cerraduras ni actuadores físicos reales. OTA real requiere PKI/certificados y almacenamiento de artefactos configurados fuera del repositorio.
