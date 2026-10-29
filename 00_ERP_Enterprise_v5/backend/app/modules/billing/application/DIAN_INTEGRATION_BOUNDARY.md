# DIAN integration boundary

The billing module MUST NOT mark a document as DIAN-validated without a concrete configured transport returning a verified response.

Required future implementation sequence:
1. Render XML from the applicable current DIAN technical annex.
2. Generate CUFE/CUDE/CUDS according to the applicable document type and current annex.
3. Sign the XML using the configured certificate/key provider without persisting private key material in application tables.
4. Transmit to DIAN through a concrete adapter with bounded timeout/retry/circuit-breaker behavior.
5. Persist submission attempt, response code, response description, hash and identifiers.
6. Only then transition `SUBMITTING -> VALIDATED`.

`UnconfiguredDianTransport` is an explicit blocker, never a test acceptance substitute.

## Estado de implementación (V23)
Existe el **puerto** (`dian_transport.py`: `DianTransport`, `DianResponse`, `UnconfiguredDianTransport` implícito = 503) y el endpoint `POST /billing/invoices/{id}/submit`:
- sin `DIAN_TRANSPORT_ADAPTER` configurado => 503 y el documento no cambia;
- la respuesta debe traer hash del acuse y, si es ACCEPTED, el CUFE/CUDE; si no => 502 y no se valida;
- cada intento queda en `dian_submissions` (append-only) antes de transicionar `SUBMITTING -> VALIDATED|REJECTED`.
**Pendiente (requiere credenciales y anexo técnico vigentes):** el adaptador real (XML UBL, CUFE/CUDE, firma con certificado, envío SOAP/REST con reintentos y circuit breaker). La prueba usa un transporte SIMULADO marcado solo para pruebas; no sustituye la validación real.
