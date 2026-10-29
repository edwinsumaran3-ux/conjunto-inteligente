// @vitest-environment node
import { describe, it, expect, vi, afterEach } from "vitest";
import { Api, ApiError, sevColor } from "./api";

const mockFetch = (status: number, body: unknown) => vi.fn(async (_u: string, _i?: RequestInit) => new Response(JSON.stringify(body), { status }));
afterEach(() => vi.unstubAllGlobals());

describe("cliente del API del gemelo", () => {
  it("enlaza un GUID IFC con un equipo: POST /bindings con el cuerpo exacto que exige el API", async () => {
    const f = mockFetch(201, { id: "b1" }); vi.stubGlobal("fetch", f);
    await new Api("http://x", "tok").linkElement("3tQ5UgSD11VOwa7ZfyDW$n", "node-1");
    const [url, init] = f.mock.calls[0]; expect(url).toBe("http://x/api/v1/digital-twin/bindings"); expect(init!.method).toBe("POST");
    expect(init!.cache).toBe("no-store");
    expect(JSON.parse(init!.body as string)).toEqual({ node_id: "node-1", identifier_system: "IFC", identifier_type: "GUID", identifier: "3tQ5UgSD11VOwa7ZfyDW$n" });
    expect((init!.headers as Record<string, string>).Authorization).toBe("Bearer tok");
  });
  it("login válido: devuelve el token para validarlo antes de guardarlo como sesión", async () => {
    const f = mockFetch(200, { access_token: "jwt-123" }); vi.stubGlobal("fetch", f); const a = new Api("", "");
    expect(await a.login("t1", "a@b.co", "Clave-123456")).toBe("jwt-123"); expect(a.token).toBe("");
    expect(JSON.parse(f.mock.calls[0][1]!.body as string)).toEqual({ email: "a@b.co", password: "Clave-123456", tenant_id: "t1" });
  });
  it("envía exactamente el token emitido por login al validar el endpoint protegido", async () => {
    const f = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: "issued-token" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ nodes_total: 1 }), { status: 200 }));
    vi.stubGlobal("fetch", f);
    const api = new Api("", "");
    api.token = await api.login("tenant-1", "user@example.com", "clave-segura");
    await api.overview();

    expect(new Headers(f.mock.calls[1][1]?.headers).get("Authorization")).toBe("Bearer issued-token");
    expect(f.mock.calls[1][1]?.cache).toBe("no-store");
  });
  it("credenciales incorrectas no establecen una sesión", async () => {
    const f = mockFetch(401, { detail: { code: "AUTH_INVALID" } }); vi.stubGlobal("fetch", f);
    const api = new Api("", "");
    await expect(api.login("t1", "a@b.co", "incorrecta")).rejects.toMatchObject({ status: 401, path: "/auth/login" });
    expect(api.token).toBe("");
  });
  it("un token vencido produce un 401 explícito y no se renueva de forma implícita", async () => {
    vi.stubGlobal("fetch", mockFetch(401, { detail: "Invalid access token" }));
    const api = new Api("", "expired-token");
    await expect(api.overview()).rejects.toMatchObject({ status: 401, authVersion: api.authVersion });
  });
  it("permite reconectar con un token que vuelve a validar el endpoint protegido", async () => {
    const f = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ nodes_total: 1 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ nodes_total: 1 }), { status: 200 }));
    vi.stubGlobal("fetch", f);
    const api = new Api("", "valid-token");
    await expect(api.overview()).resolves.toMatchObject({ nodes_total: 1 });
    await expect(api.overview()).resolves.toMatchObject({ nodes_total: 1 });
    expect(f).toHaveBeenCalledTimes(2);
    expect(f.mock.calls[0][0]).not.toBe(f.mock.calls[1][0]);
  });
  it("los errores del API no se tragan: ApiError con estado y ruta", async () => {
    vi.stubGlobal("fetch", mockFetch(404, { detail: "NO_TWIN_NODE_FOR_GLOBAL_ID" }));
    await expect(new Api("", "t").lookup("zzz")).rejects.toMatchObject({ status: 404, path: "/bim/lookup?global_id=zzz" }); await expect(new Api("", "t").lookup("zzz")).rejects.toBeInstanceOf(ApiError);
  });
  it("cada GET autenticado usa una URL distinta para no reutilizar respuestas de sesiones anteriores", async () => {
    const f = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ nodes_total: 1 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ nodes_total: 1 }), { status: 200 }));
    vi.stubGlobal("fetch", f);
    const api = new Api("", "session-token");
    await api.overview();
    await api.overview();

    expect(f.mock.calls[0][0]).not.toBe(f.mock.calls[1][0]);
    expect(new URL(String(f.mock.calls[0][0]), "http://localhost").pathname).toBe("/api/v1/digital-twin/overview");
    expect(new URL(String(f.mock.calls[0][0]), "http://localhost").searchParams.has("_request")).toBe(true);
  });
  it("descarta respuestas antiguas cuando ya se inició una sesión nueva", async () => {
    let resolveResponse!: (response: Response) => void;
    const f = vi.fn<typeof fetch>(() => new Promise((resolve) => { resolveResponse = resolve; }));
    vi.stubGlobal("fetch", f);
    const api = new Api("", "old-session");
    const request = api.overview();
    const oldVersion = api.authVersion;

    api.token = "new-session";
    resolveResponse(new Response(JSON.stringify({ detail: "Invalid access token" }), { status: 401 }));

    await expect(request).rejects.toMatchObject({ status: 409, authVersion: oldVersion });
    expect(api.authVersion).not.toBe(oldVersion);
  });
  it("el GlobalId se codifica en la URL (el '$' y '_' de los GUID IFC)", async () => {
    const f = mockFetch(200, {}); vi.stubGlobal("fetch", f); await new Api("", "t").lookup("3tQ5Ug$n/x");
    expect(String(f.mock.calls[0][0])).toContain("global_id=3tQ5Ug%24n%2Fx");
  });
  it("color por severidad: crítico/alto rojo, medio ámbar, sin anomalía verde", () => {
    expect(sevColor("critical")).toBe(0xe5484d); expect(sevColor("high")).toBe(0xe5484d); expect(sevColor("medium")).toBe(0xf0b429); expect(sevColor(null)).toBe(0x2fbf71);
  });
});
