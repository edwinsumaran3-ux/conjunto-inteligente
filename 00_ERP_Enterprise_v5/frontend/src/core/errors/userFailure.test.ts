import { describe, expect, it } from 'vitest';
import { userFailureMessage } from './userFailure';

describe('userFailureMessage', () => {
  it('never exposes server-provided internal text', () => {
    const failure = userFailureMessage(500, { error: { code: 'INTERNAL_ERROR', message: 'SQL password leaked' } });
    expect(failure.message).not.toContain('SQL password');
    expect(failure.message).toContain('protocolos de seguridad');
  });

  it('maps infrastructure failures to safe user messages', () => {
    expect(userFailureMessage(503, { error: { code: 'DEPENDENCY_UNAVAILABLE' } }).message).toContain('servicio');
    expect(userFailureMessage(504).retryable).toBe(true);
  });

  it('preserves only non-secret correlation identifiers', () => {
    const failure = userFailureMessage(500, { error: { code: 'INTERNAL_ERROR', request_id: 'req-1', incident_id: 'inc-1' } });
    expect(failure.request_id).toBe('req-1');
    expect(failure.incident_id).toBe('inc-1');
  });
});
