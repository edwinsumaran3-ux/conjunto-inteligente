"""Typed application errors used by API services."""
class ApplicationError(Exception):
    code = "APPLICATION_ERROR"
    def __init__(self, message: str = "Request could not be completed"):
        super().__init__(message)

class AuthenticationError(ApplicationError):
    code = "AUTH_INVALID"

class AuthorizationError(ApplicationError):
    code = "FORBIDDEN"

class ConflictError(ApplicationError):
    code = "CONFLICT"

class IdempotencyConflict(ConflictError):
    code = "IDEMPOTENCY_KEY_REUSED"
