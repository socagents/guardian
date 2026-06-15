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
# One declared dependency (PyYAML — see requirements.txt) on top of the
# guardian-connector-runtime base (httpx + pydantic). PyYAML parses the
# playbook YAML for the v8 Core REST API import path (issue #46); it is
# already present transitively in the base, declared here for robustness.
# No compiled binaries, no bundled payloads. Talks only to the configured
# XSOAR tenant's REST API.

ARG GUARDIAN_RUNTIME_VERSION=latest
FROM ghcr.io/kite-production/guardian-connector-runtime:${GUARDIAN_RUNTIME_VERSION}

LABEL org.opencontainers.image.source="https://github.com/kite-production/guardian"
LABEL org.opencontainers.image.description="Guardian xsoar connector container — Cortex XSOAR REST API wrapper. Tools: xsoar_list_incidents, xsoar_get_incident, xsoar_get_war_room, xsoar_add_entry, xsoar_add_note, xsoar_update_incident, xsoar_close_incident, xsoar_list_incident_types, xsoar_get_incident_fields, xsoar_search_indicators, xsoar_save_evidence, xsoar_search_evidence, xsoar_import_playbook, xsoar_health_check."

# PyYAML is declared in requirements.txt (parses the playbook YAML for the
# Cortex 8 Core REST API import path). httpx + pydantic come from the base.
COPY bundles/spark/connectors/xsoar/requirements.txt /tmp/xsoar-requirements.txt
RUN pip install --no-cache-dir -r /tmp/xsoar-requirements.txt

COPY bundles/spark/connectors/xsoar/src /app/connectors/xsoar/src

ENV CONNECTOR_ID=xsoar
