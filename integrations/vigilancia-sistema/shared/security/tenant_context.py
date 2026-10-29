from dataclasses import dataclass

from starlette.requests import Request

DEFAULT_TENANT = "default-tenant"

# Portado de TenantAuthorization.cs, con la misma corrección que motivó el
# hardening v2.3 de esa plataforma: el header que manda el llamador NO se
# confía como identidad de tenant (`Sensors service no longer trusts caller
# tenant header`). Mientras no haya un IdP/JWT real conectado, este módulo es
# explícitamente un "operational-boundary": siempre resuelve DEFAULT_TENANT
# y dependency-injecta esa constante, dejando el punto de extensión listo
# para leer `claims["tenant_id"]` de un JWT verificado en cuanto exista un
# proveedor de identidad configurado. No pretende aislar tenants todavía.
@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    resolved_from: str  # "jwt-claim" | "boundary-default"


def resolve_tenant(request: Request) -> TenantContext:
    principal = getattr(request.state, "verified_jwt_claims", None)
    if principal and principal.get("tenant_id"):
        return TenantContext(tenant_id=principal["tenant_id"], resolved_from="jwt-claim")
    # Frontera operacional: sin verificación de JWT conectada, cualquier
    # X-Tenant-Id que mande el cliente se ignora deliberadamente.
    return TenantContext(tenant_id=DEFAULT_TENANT, resolved_from="boundary-default")
