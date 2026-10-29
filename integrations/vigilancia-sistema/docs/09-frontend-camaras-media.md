# 09 — Frontend de cámaras: grid, carruseles, captura y edición

## Grid regulable (1 a 24 cámaras)

`CameraGrid.tsx` + `useCameraChannels.ts`: los canales auto-descubiertos ocupan los
primeros slots; el resto hasta completar el layout elegido (1/4/9/16/24,
`LayoutSelector.tsx`) se muestra como "sin equipo", para que el operador vea de un
vistazo cuántos puntos de conexión están libres.

## Carruseles horizontal y vertical

`CameraCarouselHorizontal.tsx` / `CameraCarouselVertical.tsx` recorren los 24 canales
completos fuera del grid principal, con desplazamiento táctil y botones de paso.
`LayoutSelector` incluye el conmutador de orientación.

## PTZ, zoom y toolbar flotante táctil

`PTZControls.tsx` (pan/tilt/zoom digital) y `CameraFloatingToolbar.tsx` (botones
flotantes: capturar imagen, grabar video, grabar audio, ampliar) se muestran al
expandir cualquier tile (`CameraTile.tsx`). El zoom físico real requiere ONVIF PTZ
(ver `equipment_adapters/ptz_camera_adapter_boundary.py`); el zoom digital funciona
sin depender de hardware.

## Captura y grabación

`useMediaCapture.ts` usa Canvas (snapshot) y `MediaRecorder` (video/audio) nativos del
navegador — sin dependencias externas. `useCameraStream.ts` conecta un stream real
(HLS/WebRTC ya resuelto por `vision-ai`) cuando existe, o un feed demo sintético en
`<canvas>` mientras el slot no tenga equipo auto-conectado, para que toda la cadena de
UI (captura, grabación, edición) sea probable sin hardware físico presente.

## Edición

`VideoEditorPanel.tsx` permite marcar in/out sobre la reproducción y descargar el clip
completo; el recorte re-codificado (no solo marcado) requeriría un servicio de
post-producción en el backend, señalado explícitamente como pendiente en el propio
panel. `AudioRecorderPanel.tsx` lista y reproduce clips de audio grabados.

## Pizarra de equipos y auto-descubrimiento

Ver `docs/08-auto-descubrimiento-malla-sensores.md` para `EquipmentTopologyBoard.tsx`
y `AutoDiscoveryPanel.tsx`.
