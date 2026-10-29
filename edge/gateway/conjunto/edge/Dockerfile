# ── Build ────────────────────────────────────────────────
FROM ubuntu:24.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake ninja-build pkg-config git ca-certificates \
    libssl-dev libsqlite3-dev libpaho-mqtt-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY . /src/edge

WORKDIR /src/edge
RUN cmake --preset=release && cmake --build --preset=release -j

# ── Runtime ──────────────────────────────────────────────
FROM ubuntu:24.04 AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlite3-0 libpaho-mqtt1.3 libssl3t64 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /src/edge/build/release/gateway/conjunto-edge-gateway /usr/local/bin/conjunto-edge-gateway

ENV EDGE__BUFFER_PATH=/data/edge-events.db
VOLUME ["/data"]
EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/conjunto-edge-gateway"]
