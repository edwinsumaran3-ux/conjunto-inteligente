-- 0004 · Fiabilidad de mensajería: outbox transaccional y dead-letter.

-- Outbox: el worker inserta aquí EN LA MISMA TRANSACCIÓN que el evento.
-- Si la publicación a RabbitMQ falla tras el commit, el relay la reintenta;
-- antes el incidente se perdía porque la redelivery ya no republicaba.
CREATE TABLE IF NOT EXISTS event_outbox (
  outbox_id      BIGSERIAL PRIMARY KEY,
  aggregate_type TEXT NOT NULL,
  aggregate_id   TEXT NOT NULL,
  exchange       TEXT NOT NULL,
  routing_key    TEXT NOT NULL DEFAULT '',
  payload        JSONB NOT NULL,
  headers        JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  available_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  published_at   TIMESTAMPTZ,
  attempts       INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  last_error     TEXT
);
CREATE INDEX IF NOT EXISTS ix_event_outbox_pending ON event_outbox(available_at, outbox_id) WHERE published_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_event_outbox_published ON event_outbox(published_at) WHERE published_at IS NOT NULL;

-- Mensajes que no se pudieron procesar (venenosos o con 2 intentos fallidos).
CREATE TABLE IF NOT EXISTS dead_letter_messages (
  dlq_id         BIGSERIAL PRIMARY KEY,
  source_service TEXT NOT NULL,
  queue_name     TEXT NOT NULL,
  message_id     TEXT,
  headers        JSONB NOT NULL DEFAULT '{}'::jsonb,
  body           TEXT NOT NULL,
  body_sha256    TEXT NOT NULL,
  error_class    TEXT NOT NULL,
  error_message  TEXT NOT NULL,
  redelivered    BOOLEAN NOT NULL DEFAULT FALSE,
  status         TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','REPLAYED','DISCARDED')),
  received_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at    TIMESTAMPTZ,
  resolved_by    TEXT
);
CREATE INDEX IF NOT EXISTS ix_dlq_status_received ON dead_letter_messages(status, received_at DESC);
CREATE INDEX IF NOT EXISTS ix_dlq_queue ON dead_letter_messages(queue_name, received_at DESC);
