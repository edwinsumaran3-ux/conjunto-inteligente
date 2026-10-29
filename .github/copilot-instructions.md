# Instrucciones del proyecto

- Antes de cambiar arquitectura o contratos, consulta el [README raíz](../README.md) y la [matriz de trazabilidad y brechas](../docs/PROJECT_REQUIREMENTS_TRACEABILITY.md). Este monorepo contiene servicios separados; no presupongas que una sola composición inicia todo.
- Conserva los módulos existentes. Integra de forma aditiva, respeta sus gestores y patrones, y no elimines ni reemplaces capacidades sin autorización explícita.
- Mantén el aislamiento por conjunto (tenant) en cada API, consulta, evento, almacenamiento y métrica. Añade o conserva pruebas que demuestren que un tenant no accede a otro.
- No presentes datos de demostración, inferencias, simulaciones ni capacidades no probadas como estados reales. Verifica cada resultado y declara qué no se pudo validar.
- No ejecutes acciones físicas, aprobaciones, movimientos contables, cierres ni validaciones fiscales. El sistema solo puede preparar propuestas pendientes de aprobación humana conforme a la [política operativa del agente](../docs/AGENT_OPERATING_POLICY.md).
- No incorpores credenciales ni claves privadas al repositorio, a logs o a respuestas. No actives funciones irreversibles de Secure Boot o cifrado de flash sin hardware, claves y procedimiento de fábrica confirmados.
- Para trabajo de hardware, distingue diseño de referencia, simulación, compilación y prueba física. No declares producción ni alta disponibilidad hasta validar el hardware objetivo, la conmutación y la recuperación.
- Ejecuta la comprobación más pequeña que cubra el cambio; informa el comando y su resultado. Si faltan credenciales, herramientas o hardware, deja el bloqueo concreto.
- Mantén la documentación del componente y la matriz de trazabilidad sincronizadas con cambios funcionales.
