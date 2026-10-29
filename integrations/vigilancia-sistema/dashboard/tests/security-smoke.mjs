// Smoke de seguridad del frontend, portado de OperationsPortal/tests/security-smoke.mjs
// (VigilanciaPlatform .NET). Verifica que index.html trae las cabeceras CSP
// mínimas exigidas y que no hay manejadores de eventos inline en HTML crudo
// (onclick="..." como atributo de string, distinto de JSX onClick={...}
// que compila a una referencia de función, no a HTML inyectado).
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const html = await readFile(new URL("../index.html", import.meta.url), "utf8");

assert.match(html, /Content-Security-Policy/, "falta meta Content-Security-Policy en index.html");
assert.match(html, /frame-ancestors 'none'/, "CSP debe incluir frame-ancestors 'none'");
assert.match(html, /script-src 'self'/, "CSP debe restringir script-src a 'self'");
assert.doesNotMatch(html, /\bon\w+\s*=\s*"/i, "no debe haber manejadores de eventos inline en HTML crudo");

console.log("frontend security smoke: PASS");
