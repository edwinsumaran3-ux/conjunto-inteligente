export type AuthSession = {
  token: string;
  tenantId: string;
  email: string;
};

const SESSION_KEY = 'ci.auth-session';
const LEGACY_KEYS = ['bim.tok', 'bim.tenant', 'bim.email'] as const;
const EMPTY_SESSION: AuthSession = { token: '', tenantId: '', email: '' };

function removeLegacyKeys(): void {
  LEGACY_KEYS.forEach((key) => sessionStorage.removeItem(key));
}

export function readAuthSession(): AuthSession {
  const stored = sessionStorage.getItem(SESSION_KEY);
  if (stored) {
    try {
      const value: unknown = JSON.parse(stored);
      if (value && typeof value === 'object') {
        const session = value as Partial<AuthSession>;
        if (
          typeof session.token === 'string'
          && typeof session.tenantId === 'string'
          && typeof session.email === 'string'
        ) {
          removeLegacyKeys();
          return { token: session.token, tenantId: session.tenantId, email: session.email };
        }
      }
    } catch {
      sessionStorage.removeItem(SESSION_KEY);
    }
    sessionStorage.removeItem(SESSION_KEY);
  }

  const legacy: AuthSession = {
    token: sessionStorage.getItem('bim.tok') || '',
    tenantId: sessionStorage.getItem('bim.tenant') || '',
    email: sessionStorage.getItem('bim.email') || '',
  };
  if (legacy.token || legacy.tenantId || legacy.email) {
    saveAuthSession(legacy);
    return legacy;
  }
  removeLegacyKeys();
  return EMPTY_SESSION;
}

export function saveAuthSession(session: AuthSession): void {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  removeLegacyKeys();
}

export function clearAuthSession(expectedToken?: string, preserveIdentity = true): boolean {
  const current = readAuthSession();
  if (expectedToken !== undefined && current.token !== expectedToken) return false;
  if (preserveIdentity && (current.tenantId || current.email)) {
    saveAuthSession({ ...current, token: '' });
  } else {
    sessionStorage.removeItem(SESSION_KEY);
    removeLegacyKeys();
  }
  return true;
}

export class AuthAttemptGate {
  private attempt = 0;

  begin(): number {
    this.attempt += 1;
    return this.attempt;
  }

  isCurrent(attempt: number): boolean {
    return this.attempt === attempt;
  }
}
