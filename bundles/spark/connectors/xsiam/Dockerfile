# guardian-connector-xsiam — per-connector image for the Cortex XSIAM
# connector. Built FROM guardian-connector-runtime.
#
# Wraps the Cortex XSIAM public API for investigation + EDR response:
# XQL queries, incidents/alerts/issues, assets, audit logs, datamodel,
# parsers, broker — plus endpoint isolate/scan/quarantine, script
# execution, and IOC + hash blocklisting. Auth is the Cortex public-API
# key pair (api_id → x-xdr-auth-id, api_key → Authorization); the
# connector appends /public_api/v1 to the configured api_url.
#
# Zero extra Python dependencies — httpx + pydantic + fastmcp are already
# in the guardian-connector-runtime base image. The connector source is
# pure stdlib + httpx; no compiled binaries, no bundled payloads. Talks
# only to the configured XSIAM tenant's public API.

ARG GUARDIAN_RUNTIME_VERSION=latest
FROM ghcr.io/kite-production/guardian-connector-runtime:${GUARDIAN_RUNTIME_VERSION}

LABEL org.opencontainers.image.source="https://github.com/kite-production/guardian"
LABEL org.opencontainers.image.description="Guardian xsiam connector container — Cortex XSIAM public-API tools: XQL queries, incidents/alerts/issues, assets, audit, datamodel, plus EDR response (endpoint isolate/scan/quarantine, script execution, IOC + hash blocklisting)."

# No extra deps. httpx + pydantic + fastmcp are in the base runtime.

COPY bundles/spark/connectors/xsiam/src /app/connectors/xsiam/src

ENV CONNECTOR_ID=xsiam
