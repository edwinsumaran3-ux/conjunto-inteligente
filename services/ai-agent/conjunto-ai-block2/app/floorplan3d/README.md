# FloorPlan 3D Pro

Módulo autocontenido para convertir planos 2D (PDF/PNG/JPG/WEBP) en una escena 3D utilizable por Conjunto Inteligente.

Incluye:
- CV heurístico con normalización, estimación informativa de inclinación (sin rotar la imagen ni las coordenadas de overlays), paredes direccionales, puertas, ventanas, habitaciones y OCR.
- Slot ONNX para un modelo U-Net entrenado.
- Generación GLB + especificación de escena para el visor WebGL del frontend.
- Análisis de cobertura de cámaras y zonas ciegas con línea de visión.
- Scripts de entrenamiento/exportación.

Endpoints:
- `GET /floorplan3d/engines`
- `POST /floorplan3d/convert`
- `POST /floorplan3d/coverage`
- `GET /floorplan3d/models/{name}`

La respuesta de conversión incluye `diagnostics.skew_deg` como estimación informativa.
No se corrige la inclinación de la imagen; las coordenadas de puertas, ventanas,
habitaciones y etiquetas permanecen en el sistema de píxeles original.
