# guardian-connector-xsoar — per-connector image for the Cortex XSOAR
# REST API wrapper. Built FROM guardian-connector-runtime.
#
# Wraps Cortex XSOAR's REST API for incident investigation: list +
# drill into cases, read the war room, document findings (entries +
# notes), update + close cases, and pull supporting context
# (indicators, evidence, incident fields). Dual-generation — XSOAR 6
# (on-prem, single Authorization key) and XSOAR 8 / Cortex cloud
# (api_key + key id via x-xdr-auth-id, /xsoar/public/v1 prefix);
# detection is config-driven via api_id.
#
# Zero extra Python dependencies — only httpx, which is already in the
# guardian-connector-runtime base image. The connector's source is pure
# stdlib + httpx; no compiled binaries, no bundled payloads. Talks only
# to the configured XSOAR tenant's REST API.

ARG GUARDIAN_RUNTIME_VERSION=latest
FROM ghcr.io/kite-production/guardian-connector-runtime:${GUARDIAN_RUNTIME_VERSION}

LABEL org.opencontainers.image.source="https://github.com/kite-production/guardian"
LABEL org.opencontainers.image.description="Guardian xsoar connector container — Cortex XSOAR REST API wrapper. Tools: xsoar_list_incidents, xsoar_get_incident, xsoar_get_war_room, xsoar_add_entry, xsoar_add_note, xsoar_update_incident, xsoar_close_incident, xsoar_list_incident_types, xsoar_get_incident_fields, xsoar_search_indicators, xsoar_save_evidence, xsoar_search_evidence, xsoar_health_check."

# No extra deps. httpx + pydantic are in the base runtime.

COPY bundles/spark/connectors/xsoar/src /app/connectors/xsoar/src

ENV CONNECTOR_ID=xsoar
