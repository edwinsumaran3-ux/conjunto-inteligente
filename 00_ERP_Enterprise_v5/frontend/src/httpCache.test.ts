import { describe, expect, it } from 'vitest';
import { uncachedUrl } from './httpCache';

describe('authenticated API cache busting', () => {
  it('preserves query parameters and gives each request a distinct cache key', () => {
    const first = new URL(uncachedUrl('/api/v1/digital-twin/nodes?limit=25'), 'http://localhost');
    const second = new URL(uncachedUrl('/api/v1/digital-twin/nodes?limit=25'), 'http://localhost');

    expect(first.pathname).toBe('/api/v1/digital-twin/nodes');
    expect(first.searchParams.get('limit')).toBe('25');
    expect(first.searchParams.get('_request')).toBeTruthy();
    expect(second.searchParams.get('_request')).not.toBe(first.searchParams.get('_request'));
  });
});
