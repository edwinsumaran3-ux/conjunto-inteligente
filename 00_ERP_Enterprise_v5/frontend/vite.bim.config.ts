import { defineConfig } from "vite";
// Visor BIM independiente: se sirve en /bim (FastAPI monta frontend/dist/bim) o en dev con `npm run dev:bim`.
// Keep the dependency optimizer separate from the dashboard's Vite process.
export default defineConfig({ root: "bim", base: "/bim/", publicDir: "public", cacheDir: "../node_modules/.vite-bim", build: { rollupOptions: { output: { manualChunks: { three: ["three"], ifc: ["web-ifc"] } } }, outDir: "../dist/bim", emptyOutDir: true, chunkSizeWarningLimit: 2500 },
  server: { port: 5174, strictPort: true, proxy: { "/api": "http://127.0.0.1:8000" } } });
