import { afterEach, describe, expect, it, vi } from 'vitest';
import { configuredApiBase } from './apiBase';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe('configuredApiBase', () => {
  it('prefers the API base saved for this browser session', () => {
    vi.stubGlobal('sessionStorage', {
      getItem: vi.fn(() => 'https://api.example.test'),
    });
    vi.stubEnv('VITE_API_BASE_URL', 'https://fallback.example.test');

    expect(configuredApiBase()).toBe('https://api.example.test');
  });

  it('uses the configured environment base when no session override exists', () => {
    vi.stubGlobal('sessionStorage', {
      getItem: vi.fn(() => null),
    });
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.test');

    expect(configuredApiBase()).toBe('https://api.example.test');
  });

  it('keeps same-origin routing when no API base is configured', () => {
    vi.stubGlobal('sessionStorage', {
      getItem: vi.fn(() => null),
    });
    vi.stubEnv('VITE_API_BASE_URL', '');

    expect(configuredApiBase()).toBe('');
  });
});
