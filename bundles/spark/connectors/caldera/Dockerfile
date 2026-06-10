# phantom-connector-caldera — per-connector image for the Caldera
# adversary-emulation connector, built FROM phantom-connector-runtime.
#
# No extra Python deps required: the caldera connector tools speak
# HTTP to the caldera backend service (http://caldera:8888) via httpx,
# which is already in the base image. The caldera SERVICE container
# (third_party/caldera/) is a completely separate image and is
# unaffected by Phase 1 work.

ARG PHANTOM_RUNTIME_VERSION=latest
FROM ghcr.io/kite-production/phantom-connector-runtime:${PHANTOM_RUNTIME_VERSION}

LABEL org.opencontainers.image.source="https://github.com/kite-production/phantom"
LABEL org.opencontainers.image.description="Phantom caldera connector container — adversary emulation, operations, abilities tools running as a per-instance MCP server."

COPY bundles/spark/connectors/caldera/src /app/connectors/caldera/src

ENV CONNECTOR_ID=caldera
