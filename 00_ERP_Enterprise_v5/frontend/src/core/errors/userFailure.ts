export type UserFailureCode =
  | 'REQUEST_FAILED'
  | 'INTERNAL_ERROR'
  | 'REQUEST_TIMEOUT'
  | 'DEPENDENCY_UNAVAILABLE'
  | 'PARTIAL_OUTAGE'
  | 'RATE_LIMITED'
  | 'AUTHENTICATION_REQUIRED'
  | 'ACCESS_DENIED'
  | 'CONFLICT'
  | 'VALIDATION_FAILED';

export type UserFailure = {
  code: UserFailureCode;
  message: string;
  request_id?: string;
  incident_id?: string;
  retryable: boolean;
};

const SAFE_MESSAGES: Record<UserFailureCode, string> = {
  REQUEST_FAILED: 'No pudimos completar la operación. Estamos trabajando en nuestros protocolos de seguridad para darte un buen servicio.',
  INTERNAL_ERROR: 'Tuvimos un inconveniente interno. Estamos trabajando en nuestros protocolos de seguridad para darte un buen servicio.',
  REQUEST_TIMEOUT: 'La operación está tardando más de lo esperado. Estamos verificando el servicio; puedes intentarlo nuevamente.',
  DEPENDENCY_UNAVAILABLE: 'Un servicio necesario no está disponible temporalmente. Estamos trabajando para restablecerlo.',
  PARTIAL_OUTAGE: 'Algunas funciones están temporalmente limitadas. Estamos trabajando para restablecer el servicio completo.',
  RATE_LIMITED: 'Recibimos demasiadas solicitudes en poco tiempo. Espera un momento e inténtalo nuevamente.',
  AUTHENTICATION_REQUIRED: 'Tu sesión necesita ser verificada nuevamente.',
  ACCESS_DENIED: 'No tienes autorización para realizar esta operación.',
  CONFLICT: 'La operación no pudo completarse porque el estado del recurso cambió. Actualiza la información e inténtalo nuevamente.',
  VALIDATION_FAILED: 'Revisa la información indicada e inténtalo nuevamente.',
};

const SAFE_CORRELATION = /^[A-Za-z0-9._:-]{1,128}$/;

function safeCorrelation(value: unknown): string | undefined {
  return typeof value === 'string' && SAFE_CORRELATION.test(value) ? value : undefined;
}

const RETRYABLE = new Set<UserFailureCode>([
  'REQUEST_TIMEOUT', 'DEPENDENCY_UNAVAILABLE', 'PARTIAL_OUTAGE', 'RATE_LIMITED', 'INTERNAL_ERROR',
]);

function isCode(value: unknown): value is UserFailureCode {
  return typeof value === 'string' && value in SAFE_MESSAGES;
}

export function userFailureMessage(status: number, payload?: unknown): UserFailure {
  const candidate = (payload as { error?: { code?: unknown; request_id?: unknown; incident_id?: unknown; retryable?: unknown } } | undefined)?.error;
  const code: UserFailureCode = isCode(candidate?.code)
    ? candidate.code
    : status === 401 ? 'AUTHENTICATION_REQUIRED'
    : status === 403 ? 'ACCESS_DENIED'
    : status === 409 ? 'CONFLICT'
    : status === 422 ? 'VALIDATION_FAILED'
    : status === 408 || status === 504 ? 'REQUEST_TIMEOUT'
    : status === 429 ? 'RATE_LIMITED'
    : status >= 500 ? 'INTERNAL_ERROR'
    : 'REQUEST_FAILED';

  return {
    code,
    message: SAFE_MESSAGES[code],
    request_id: safeCorrelation(candidate?.request_id),
    incident_id: safeCorrelation(candidate?.incident_id),
    retryable: RETRYABLE.has(code),
  };
}

export function isTransientFailure(failure: UserFailure): boolean {
  return failure.retryable;
}
