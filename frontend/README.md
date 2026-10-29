# Frontend · Centro de Mando

Referencia visual de alta fidelidad para el frontend de Conjunto Inteligente.

## Objetivo

Esta interfaz reproduce la composición de la referencia aprobada: consola oscura, cinco KPIs, mapa operativo 3D/planos, alertas, WhatsApp, servicios por área, visualizador de planos, detalle de servicio, cadena de suministro, flujo de proceso, reportes, app residente e integraciones.

## Integración

La pantalla está preparada para reemplazar sus datos de demostración por API REST/SignalR. Las acciones no presentan datos ficticios como si fueran datos productivos: cuando una integración real no está disponible se muestra como estado de integración.

## Ejecución

Abrir `centro-mando/index.html` directamente en un navegador moderno. No requiere CDN ni dependencias externas.

Para producción, esta referencia debe trasladarse a los componentes React/TypeScript del frontend y conectar cada panel a los endpoints documentados en `docs/API.md`.
