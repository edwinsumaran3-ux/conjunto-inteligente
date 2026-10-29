# 11 — Catálogo de referencia de drones

`services/agent-orchestrator/src/drone_catalog.py` incorpora once modelos de dron
profesionales para seguridad y vigilancia (DJI Mavic 2 Enterprise, DJI Matrice 30, DJI
Matrice 300 RTK, Elistair Orion 2, Teal Golden Eagle, Easy Aerial Raptor,
Quantum-Systems Vector y Scorpion, Alpha Unmanned Systems A-900, Autel DragonFish, AV
Systems AV-2 Pelican), con fabricante, categoría, autonomía aproximada y uso típico,
como referencia fáctica para elegir un modelo real al dar de alta un equipo.

Fuente de los datos técnicos: página comparativa de Red Proventum
(dronesindustriales.net, "Diez Drones para Seguridad y Vigilancia"). Los datos se
transcribieron como especificaciones (fabricante/autonomía/uso), no como el texto de
la página.

**Importante**: registrar un modelo del catálogo (`POST /equipment/drones`) solo
adjunta ese contexto informativo al `EquipmentRegistry` — el adaptador sigue siendo
fail-closed (`equipment_adapters/drone_adapter_boundary.py`) hasta integrar el SDK real
del fabricante correspondiente. Ver `docs/10-fusion-unificacion-plataforma.md` para el
patrón de comandos firmados que gobierna cualquier ejecución futura sobre estos
equipos.
