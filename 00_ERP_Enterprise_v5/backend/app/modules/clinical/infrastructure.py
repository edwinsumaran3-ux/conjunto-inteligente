"""Infrastructure boundary for future clinical interoperability adapters.

The core clinical module deliberately does not import external EHR/FHIR/HL7
providers. Concrete adapters must depend on explicit ports and preserve the
same tenant, audit, authorization and idempotency contracts.
"""
class ClinicalInfrastructureBoundary:
    """Marker used by architecture checks to keep external adapters isolated."""
    provider_protocol = 'explicit-adapter-only'
