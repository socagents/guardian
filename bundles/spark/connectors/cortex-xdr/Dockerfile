# guardian-connector-cortex-xdr — per-connector image for the
# Cortex XDR API wrapper. Built FROM guardian-connector-runtime.
#
# v0.5.61 (issue #36): wraps Cortex XDR's Public API for incident
# listing + XQL execution. Same auth pattern as XSIAM (Authorization
# + x-xdr-auth-id headers); uses uniform api_url / api_id / api_key
# config field names per v0.5.59 / issue #35.
#
# Zero extra Python dependencies — only httpx, which is already in
# the guardian-connector-runtime base image. The connector's source
# is pure stdlib + httpx; no Mimikatz, no compiled binaries, no
# bundled payloads. Read-only against the upstream XDR API.

ARG GUARDIAN_RUNTIME_VERSION=latest
FROM ghcr.io/kite-production/guardian-connector-runtime:${GUARDIAN_RUNTIME_VERSION}

LABEL org.opencontainers.image.source="https://github.com/kite-production/guardian"
LABEL org.opencontainers.image.description="Guardian cortex-xdr connector container — Cortex XDR API wrapper. Tools: xdr_get_cases_and_issues, xdr_get_incident_extra_data, xdr_run_xql_query, xdr_get_xql_results."

# No extra deps. httpx + pydantic are in the base runtime.

COPY bundles/spark/connectors/cortex-xdr/src /app/connectors/cortex-xdr/src

ENV CONNECTOR_ID=cortex-xdr
