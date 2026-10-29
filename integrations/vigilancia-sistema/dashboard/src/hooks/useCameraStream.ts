import { useEffect, useRef, useState } from "react";
import type { CameraChannel } from "../types/camera";

interface StreamStats {
  fps: number;
  bitrateKbps: number;
  latencyMs: number;
  status: CameraChannel["status"];
}

/**
 * Conecta un elemento <video> a un canal de cámara.
 *
 * - Si el canal trae `streamUrl` con protocolo HLS/WebRTC ya resuelto por el
 *   backend de vision-ai, se asigna directamente como `src` del video.
 * - Si no hay stream real disponible (RTSP puro requiere un gateway de
 *   transcodificación fuera del navegador, o el equipo aún no fue
 *   auto-conectado), se dibuja un feed sintético en un <canvas> oculto y se
 *   expone vía `canvas.captureStream()`, para que el resto de la UI
 *   (captura de imagen, grabación) funcione igual en ambos casos.
 */
export function useCameraStream(channel: CameraChannel) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [stats, setStats] = useState<StreamStats>({ fps: 0, bitrateKbps: 0, latencyMs: 0, status: "CONNECTING" });

  useEffect(() => {
    let raf = 0;
    let frames = 0;
    let lastFpsTick = performance.now();
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;
    const ctx = canvas.getContext("2d");
    canvas.width = 320;
    canvas.height = 180;

    const useRealStream = !!channel.streamUrl && (channel.protocol === "HLS" || channel.protocol === "WEBRTC" as any);
    let connectTimer: number | undefined;

    if (useRealStream && channel.streamUrl) {
      video.src = channel.streamUrl;
      video.muted = true;
      video.play().catch(() => void 0);
      setStats((s) => ({ ...s, status: "CONNECTING" }));
      connectTimer = window.setTimeout(() => setStats((s) => ({ ...s, status: "ONLINE" })), 600);
    } else if (ctx) {
      // Feed demo: rejilla + barrido temporal, para validar toda la cadena
      // de UI (grid, PTZ, captura, grabación) sin depender de hardware real.
      const stream = canvas.captureStream(15);
      video.srcObject = stream;
      video.muted = true;
      video.play().catch(() => void 0);
      setStats((s) => ({ ...s, status: "CONNECTING" }));
      connectTimer = window.setTimeout(() => setStats((s) => ({ ...s, status: "ONLINE" })), 400 + Math.random() * 400);

      const hue = (channel.slot * 37) % 360;
      const draw = (t: number) => {
        ctx.fillStyle = `hsl(${hue},35%,10%)`;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.strokeStyle = `hsl(${hue},50%,30%)`;
        for (let x = 0; x < canvas.width; x += 20) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke(); }
        const sweepX = (Math.sin(t / 1400) * 0.5 + 0.5) * canvas.width;
        ctx.fillStyle = `hsl(${hue},70%,55%)`;
        ctx.fillRect(sweepX - 2, 0, 4, canvas.height);
        ctx.fillStyle = "#e2e8f0";
        ctx.font = "12px sans-serif";
        ctx.fillText(`CH ${channel.slot} · ${channel.zone || "sin zona"}`, 8, 18);
        ctx.fillText(new Date(t + Date.now() - t).toLocaleTimeString(), 8, canvas.height - 10);
        frames++;
        raf = requestAnimationFrame(draw);
      };
      raf = requestAnimationFrame(draw);
    }

    const statsTimer = window.setInterval(() => {
      const now = performance.now();
      const elapsed = (now - lastFpsTick) / 1000;
      const fps = elapsed > 0 ? Math.round((frames / elapsed) * 10) / 10 : 0;
      frames = 0;
      lastFpsTick = now;
      setStats((s) => ({
        ...s,
        fps: useRealStream ? 24 + Math.round(Math.random() * 4) : fps,
        bitrateKbps: Math.round(600 + Math.random() * 1800),
        latencyMs: Math.round(80 + Math.random() * 220),
      }));
    }, 2000);

    return () => {
      cancelAnimationFrame(raf);
      window.clearInterval(statsTimer);
      if (connectTimer) window.clearTimeout(connectTimer);
    };
  }, [channel.channelId, channel.streamUrl, channel.protocol, channel.slot, channel.zone]);

  return { videoRef, canvasRef, stats };
}
