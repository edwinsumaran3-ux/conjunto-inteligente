import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const vite = fileURLToPath(new URL('../node_modules/vite/bin/vite.js', import.meta.url));
const children = [
  spawn(process.execPath, [vite, '--host', '127.0.0.1'], { stdio: 'inherit' }),
  spawn(process.execPath, [vite, '--config', 'vite.bim.config.ts', '--host', '127.0.0.1'], { stdio: 'inherit' }),
];

let stopping = false;

function stop(signal = 'SIGTERM') {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (child.exitCode === null && !child.killed) child.kill(signal);
  }
}

for (const child of children) {
  child.on('error', (error) => {
    console.error(`No se pudo iniciar un servidor Vite: ${error.message}`);
    process.exitCode = 1;
    stop();
  });
  child.on('exit', (code, signal) => {
    if (!stopping) {
      if (code !== 0) {
        console.error(`Un servidor Vite terminó inesperadamente (${signal || `código ${code ?? 'desconocido'}`}).`);
        process.exitCode = code ?? 1;
      }
      stop();
    }
  });
}

process.on('SIGINT', () => stop('SIGINT'));
process.on('SIGTERM', () => stop('SIGTERM'));
