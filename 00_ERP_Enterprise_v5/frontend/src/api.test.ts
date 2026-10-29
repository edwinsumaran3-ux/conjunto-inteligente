import { afterEach, describe, expect, it, vi } from 'vitest';
import { DashboardApi, DashboardApiError } from './api';

afterEach(() => vi.unstubAllGlobals());

describe('DashboardApi', () => {
  it('requests the real overview with the active bearer token', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ nodes_total: 12 }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const api = new DashboardApi('', 'session-token');

    await expect(api.overview()).resolves.toMatchObject({ nodes_total: 12 });
    const requestUrl = new URL(String(fetchMock.mock.calls[0][0]), 'http://localhost');
    expect(requestUrl.pathname).toBe('/api/v1/digital-twin/overview');
    expect(requestUrl.searchParams.get('_request')).toBeTruthy();
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).get('Authorization')).toBe('Bearer session-token');
    expect(fetchMock.mock.calls[0][1]?.cache).toBe('no-store');
  });

  it('uses the tenant login endpoint and returns the access token', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ access_token: 'issued-token' }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const api = new DashboardApi('http://127.0.0.1:8000', '');

    await expect(api.login('tenant-1', 'user@example.com', 'password')).resolves.toBe('issued-token');
    expect(fetchMock.mock.calls[0][0]).toBe('http://127.0.0.1:8000/api/v1/auth/login');
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      tenant_id: 'tenant-1',
      email: 'user@example.com',
      password: 'password',
    });
  });

  it('uses tenant-scoped inventory, telemetry and model endpoints', async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [], total: 0, limit: 25, offset: 0 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    const api = new DashboardApi('', 'session-token');

    await expect(api.nodes({ limit: 25, offset: 0, search: 'Bomba 1' })).resolves.toMatchObject({ total: 0 });
    await expect(api.points()).resolves.toEqual([]);
    await expect(api.modelVersions()).resolves.toEqual([]);
    const requests = fetchMock.mock.calls.map(([url]) => new URL(String(url), 'http://localhost'));
    expect(requests.map((url) => url.pathname)).toEqual([
      '/api/v1/digital-twin/nodes',
      '/api/v1/digital-twin/points',
      '/api/v1/digital-twin/model-versions',
    ]);
    expect(requests[0].searchParams.get('search')).toBe('Bomba 1');
    expect(requests.every((url) => Boolean(url.searchParams.get('_request')))).toBe(true);
  });

  it('creates simulated sensors and sends idempotent runs through the tenant API', async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ device_id: 'device-1' }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ run_id: 'run-1', status: 'accepted' }), { status: 201 }));
    vi.stubGlobal('fetch', fetchMock);
    const api = new DashboardApi('', 'session-token');

    await api.createSimulatedDevice({
      node_id: 'node-1',
      profile_id: 'temperature',
      code: 'SIM-TEMP-1',
    });
    await api.runSimulation('device-1', 'alarm', 'run-1');

    const first = fetchMock.mock.calls[0];
    const second = fetchMock.mock.calls[1];
    expect(new URL(String(first[0]), 'http://localhost').pathname).toBe('/api/v1/digital-twin/simulations/devices');
    expect(first[1]?.method).toBe('POST');
    expect(JSON.parse(String(first[1]?.body))).toEqual({
      node_id: 'node-1',
      profile_id: 'temperature',
      code: 'SIM-TEMP-1',
    });
    expect(new URL(String(second[0]), 'http://localhost').pathname).toBe('/api/v1/digital-twin/simulations/devices/device-1/run');
    expect(JSON.parse(String(second[1]?.body))).toEqual({ scenario: 'alarm', run_id: 'run-1' });
    expect(new Headers(second[1]?.headers).get('Authorization')).toBe('Bearer session-token');
    expect(second[1]?.cache).toBe('no-store');
  });

  it('lists own operational orders for non-managers and creates a request', async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        items: [],
        total: 0,
        page: 1,
        page_size: 50,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id: 'order-1',
        code: 'MT-00000001',
        status: 'pending_approval',
      }), { status: 201 }));
    vi.stubGlobal('fetch', fetchMock);
    const api = new DashboardApi('', 'session-token');

    await expect(api.maintenanceOrders({ mine: true })).resolves.toMatchObject({ total: 0 });
    await expect(api.createMaintenanceOrder({
      title: 'Fuga en zona común',
      description: 'Goteo visible',
      category: 'hidrosanitario',
      severity: 'medium',
    })).resolves.toMatchObject({ code: 'MT-00000001' });

    expect(new URL(String(fetchMock.mock.calls[0][0]), 'http://localhost').pathname)
      .toBe('/api/v1/maintenance/orders/mine');
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).get('Authorization'))
      .toBe('Bearer session-token');
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
      title: 'Fuga en zona común',
      description: 'Goteo visible',
      category: 'hidrosanitario',
      severity: 'medium',
    });
  });

  it('uses optimistic order versions for approval and status transitions', async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id: 'order/1',
        status: 'scheduled',
        version: 2,
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id: 'order/1',
        status: 'in_progress',
        version: 3,
      }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    const api = new DashboardApi('', 'session-token');

    await expect(api.approveMaintenanceOrder('order/1', 1)).resolves.toMatchObject({ version: 2 });
    await expect(api.transitionMaintenanceOrder('order/1', 'in_progress', 2))
      .resolves.toMatchObject({ version: 3 });

    const approval = fetchMock.mock.calls[0];
    expect(new URL(String(approval[0]), 'http://localhost').pathname)
      .toBe('/api/v1/maintenance/orders/order%2F1/approve');
    expect(JSON.parse(String(approval[1]?.body))).toEqual({ expected_version: 1 });
    const transition = fetchMock.mock.calls[1];
    expect(transition[1]?.method).toBe('PATCH');
    expect(JSON.parse(String(transition[1]?.body))).toEqual({
      status: 'in_progress',
      expected_version: 2,
    });
  });

  it('loads maintenance directories and uses the administrative write contracts', async () => {
    const emptyPage = JSON.stringify({ items: [], total: 0, page: 1, page_size: 100 });
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(emptyPage, { status: 200 }))
      .mockResolvedValueOnce(new Response(emptyPage, { status: 200 }))
      .mockResolvedValueOnce(new Response(emptyPage, { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'resident-1', status: 'created' }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'resident-1', status: 'updated' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'vendor-1', status: 'created' }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'vendor/1', status: 'updated' }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    const api = new DashboardApi('', 'session-token');
    const residentInput = {
      user_id: 'user-1',
      full_name: 'Ana Residente',
      phone: null,
      unit_ids: ['unit-1'],
      primary_unit_id: 'unit-1',
    };
    const residentUpdate = {
      full_name: 'Ana Residente',
      phone: '+57 300 000 0000',
      active: true,
      unit_ids: ['unit-1'],
      primary_unit_id: 'unit-1',
    };
    const vendorInput = {
      name: 'Servicios Integrales',
      nit: '900123456',
      categories: ['electrico'],
      status: 'active' as const,
      documents_valid_until: null,
      rating: 4.5,
    };

    await api.maintenanceUnits({ q: 'Torre A' });
    await api.maintenanceResidents({ page: 2, q: 'Ana' });
    await api.maintenanceVendors({ q: 'Servicios' });
    await api.tenantUsers();
    await api.createMaintenanceResident(residentInput);
    await api.updateMaintenanceResident('resident-1', residentUpdate);
    await api.createMaintenanceVendor(vendorInput);
    await api.updateMaintenanceVendor('vendor/1', vendorInput);

    const urls = fetchMock.mock.calls.map(([url]) => new URL(String(url), 'http://localhost'));
    expect(urls.map((url) => url.pathname)).toEqual([
      '/api/v1/maintenance/units',
      '/api/v1/maintenance/residents',
      '/api/v1/maintenance/vendors',
      '/api/v1/users',
      '/api/v1/maintenance/residents',
      '/api/v1/maintenance/residents/resident-1',
      '/api/v1/maintenance/vendors',
      '/api/v1/maintenance/vendors/vendor%2F1',
    ]);
    expect(urls[0].searchParams.get('q')).toBe('Torre A');
    expect(urls[1].searchParams.get('page')).toBe('2');
    expect(urls[1].searchParams.get('q')).toBe('Ana');
    expect(fetchMock.mock.calls[4][1]?.method).toBe('POST');
    expect(JSON.parse(String(fetchMock.mock.calls[4][1]?.body))).toEqual(residentInput);
    expect(fetchMock.mock.calls[5][1]?.method).toBe('PUT');
    expect(JSON.parse(String(fetchMock.mock.calls[5][1]?.body))).toEqual(residentUpdate);
    expect(fetchMock.mock.calls[6][1]?.method).toBe('POST');
    expect(JSON.parse(String(fetchMock.mock.calls[6][1]?.body))).toEqual(vendorInput);
    expect(fetchMock.mock.calls[7][1]?.method).toBe('PUT');
    expect(new Headers(fetchMock.mock.calls[7][1]?.headers).get('Authorization')).toBe('Bearer session-token');
  });

  it('shows a safe message when the API fails', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'INTERNAL_ERROR', message: 'database password exposed' } }), { status: 500 }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const api = new DashboardApi('', 'session-token');

    const failure = await api.overview().catch((reason: unknown) => reason);

    expect(failure).toBeInstanceOf(DashboardApiError);
    if (failure instanceof DashboardApiError) {
      expect(failure.status).toBe(500);
      expect(failure.message).not.toContain('database password');
    }
  });
});
