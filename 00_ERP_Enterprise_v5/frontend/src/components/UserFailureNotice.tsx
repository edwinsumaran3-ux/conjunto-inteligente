import type { UserFailure } from '../core/errors/userFailure';
export function UserFailureNotice({ failure, onRetry }: { failure: UserFailure; onRetry?: () => void }) {
  return <section role="alert" aria-live="assertive">
    <strong>{failure.message}</strong>
    {onRetry && failure.retryable ? <button type="button" onClick={onRetry}>Intentar nuevamente</button> : null}
  </section>;
}
