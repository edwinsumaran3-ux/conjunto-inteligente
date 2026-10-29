// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthAttemptGate, clearAuthSession, readAuthSession, saveAuthSession } from "../../src/authSession";
import { Api } from "./api";

const storage = () => {
  const entries = new Map<string, string>();
  return {
    getItem: (key: string) => entries.get(key) ?? null,
    setItem: (key: string, value: string) => { entries.set(key, value); },
    removeItem: (key: string) => { entries.delete(key); },
    keys: () => [...entries.keys()],
  };
};

afterEach(() => vi.unstubAllGlobals());

describe("sesión compartida del dashboard y BIM", () => {
  it("migra las claves anteriores a una sola fuente de verdad", () => {
    const sessionStorage = storage();
    sessionStorage.setItem("bim.tok", "legacy-token");
    sessionStorage.setItem("bim.tenant", "tenant-1");
    sessionStorage.setItem("bim.email", "user@example.com");
    vi.stubGlobal("sessionStorage", sessionStorage);

    expect(readAuthSession()).toEqual({ token: "legacy-token", tenantId: "tenant-1", email: "user@example.com" });
    expect(sessionStorage.keys()).toEqual(["ci.auth-session"]);
  });

  it("una respuesta vencida no puede borrar el token de una sesión posterior", () => {
    const sessionStorage = storage();
    vi.stubGlobal("sessionStorage", sessionStorage);
    saveAuthSession({ token: "new-token", tenantId: "tenant-1", email: "user@example.com" });

    expect(clearAuthSession("old-token")).toBe(false);
    expect(readAuthSession().token).toBe("new-token");
  });

  it("dos intentos de conexión concurrentes solo permiten completar el más reciente", async () => {
    const gate = new AuthAttemptGate();
    const first = gate.begin();
    let finishFirst!: () => void;
    const firstConnection = new Promise<void>((resolve) => { finishFirst = resolve; });
    const second = gate.begin();
    finishFirst();
    await firstConnection;

    expect(gate.isCurrent(first)).toBe(false);
    expect(gate.isCurrent(second)).toBe(true);
  });

  it("una respuesta 401 antigua no invalida sesión nueva durante una reconexión", async () => {
    const sessionStorage = storage();
    vi.stubGlobal("sessionStorage", sessionStorage);
    saveAuthSession({ token: "old-token", tenantId: "tenant-1", email: "user@example.com" });

    let resolveResponse!: (response: Response) => void;
    vi.stubGlobal("fetch", vi.fn<typeof fetch>(() => new Promise((resolve) => { resolveResponse = resolve; })));
    const api = new Api("", "old-token");
    const oldRequest = api.overview();
    const oldAttempt = api.authVersion;

    api.token = "new-token";
    saveAuthSession({ token: "new-token", tenantId: "tenant-1", email: "user@example.com" });
    resolveResponse(new Response(JSON.stringify({ detail: "Invalid access token" }), { status: 401 }));

    await expect(oldRequest).rejects.toMatchObject({ status: 409, authVersion: oldAttempt });
    expect(clearAuthSession("old-token")).toBe(false);
    expect(readAuthSession().token).toBe("new-token");
  });
});
