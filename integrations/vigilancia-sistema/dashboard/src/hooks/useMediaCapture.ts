import { useCallback, useRef, useState } from "react";
import type { RefObject } from "react";
import type { RecordingClip, Snapshot } from "../types/camera";

/**
 * Captura de imagen y grabación de video/audio sobre un <video> ya
 * conectado (real o demo, ver `useCameraStream`). Usa las APIs nativas del
 * navegador (Canvas para snapshot, MediaRecorder para clips) — no requiere
 * dependencias externas, y el resultado es reproducible/editable de
 * inmediato en `VideoEditorPanel`.
 */
export function useMediaCapture(channelId: string, videoRef: RefObject<HTMLVideoElement>) {
  const [isRecordingVideo, setIsRecordingVideo] = useState(false);
  const [isRecordingAudio, setIsRecordingAudio] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef(0);
  const audioStreamRef = useRef<MediaStream | null>(null);

  const captureSnapshot = useCallback((): Snapshot | null => {
    const video = videoRef.current;
    if (!video || video.readyState < 2) return null;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 320;
    canvas.height = video.videoHeight || 180;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return { id: crypto.randomUUID(), channelId, dataUrl: canvas.toDataURL("image/png"), takenAt: Date.now() };
  }, [channelId, videoRef]);

  const startVideoRecording = useCallback(() => {
    const video = videoRef.current;
    const source = (video?.srcObject as MediaStream | null) ?? null;
    if (!source) return;
    chunksRef.current = [];
    startedAtRef.current = Date.now();
    const rec = new MediaRecorder(source, { mimeType: "video/webm;codecs=vp8" });
    rec.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
    rec.start(250);
    recorderRef.current = rec;
    setIsRecordingVideo(true);
  }, [videoRef]);

  const stopVideoRecording = useCallback((): Promise<RecordingClip | null> => {
    return new Promise((resolve) => {
      const rec = recorderRef.current;
      if (!rec) return resolve(null);
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "video/webm" });
        setIsRecordingVideo(false);
        resolve({ id: crypto.randomUUID(), channelId, blobUrl: URL.createObjectURL(blob), kind: "video", durationMs: Date.now() - startedAtRef.current, createdAt: Date.now() });
      };
      rec.stop();
    });
  }, [channelId]);

  const startAudioRecording = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioStreamRef.current = stream;
    chunksRef.current = [];
    startedAtRef.current = Date.now();
    const rec = new MediaRecorder(stream);
    rec.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
    rec.start(250);
    recorderRef.current = rec;
    setIsRecordingAudio(true);
  }, []);

  const stopAudioRecording = useCallback((): Promise<RecordingClip | null> => {
    return new Promise((resolve) => {
      const rec = recorderRef.current;
      if (!rec) return resolve(null);
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        audioStreamRef.current?.getTracks().forEach((t) => t.stop());
        setIsRecordingAudio(false);
        resolve({ id: crypto.randomUUID(), channelId, blobUrl: URL.createObjectURL(blob), kind: "audio", durationMs: Date.now() - startedAtRef.current, createdAt: Date.now() });
      };
      rec.stop();
    });
  }, [channelId]);

  return { captureSnapshot, isRecordingVideo, startVideoRecording, stopVideoRecording, isRecordingAudio, startAudioRecording, stopAudioRecording };
}
