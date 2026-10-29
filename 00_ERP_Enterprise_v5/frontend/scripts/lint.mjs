import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../src/', import.meta.url));
const forbidden = [
  [/console\.log\s*\(/g, 'debug console output'],
  [/\bdebugger\s*;/g, 'debugger statement'],
  [/<script[^>]+src=["']https?:/gi, 'remote script dependency'],
];
let failed = false;

async function walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) await walk(path);
    else if (/\.(ts|tsx|js|jsx)$/.test(entry.name)) {
      const text = await readFile(path, 'utf8');
      for (const [pattern, label] of forbidden) {
        pattern.lastIndex = 0;
        if (pattern.test(text)) {
          console.error(`lint violation: ${label}: ${path}`);
          failed = true;
        }
      }
    }
  }
}
await walk(root);
if (failed) process.exit(1);
console.log('frontend lint: PASS');
