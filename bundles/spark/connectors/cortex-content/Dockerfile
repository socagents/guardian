# phantom-connector-cortex-content — per-connector image for the Cortex
# Content marketplace fetch connector. Built FROM phantom-connector-runtime.
#
# Adds zero extra Python dependencies — the connector uses only stdlib
# (urllib, json, pathlib, time) plus httpx (for GitHub API calls), and
# httpx is already in the base runtime image. The 24h file-backed
# response cache lives at /app/data/cortex-content-cache/ (volume-
# survives, shared with the host data dir via the runtime's read-only
# data mount).
#
# Why this connector exists as a per-instance container (v0.5.0+):
# every connector ships as container-style in v0.5.0's universal
# migration. cortex-content's tool surface is read-only public-API
# fetches against api.github.com + raw.githubusercontent.com — no
# secrets, no destructive operations. Container isolation gives it
# the same crash + resource isolation guarantees as the other
# connectors, with no behavioral cost.

ARG PHANTOM_RUNTIME_VERSION=latest
FROM ghcr.io/kite-production/phantom-connector-runtime:${PHANTOM_RUNTIME_VERSION}

LABEL org.opencontainers.image.source="https://github.com/kite-production/phantom"
LABEL org.opencontainers.image.description="Phantom cortex-content connector container — Palo Alto Networks Cortex Content marketplace fetch (XSIAM packs, ModelingRules, ParsingRules, CorrelationRules) from the public demisto/content GitHub repository."

# No extra deps. httpx is in the base runtime image.

COPY bundles/spark/connectors/cortex-content/src /app/connectors/cortex-content/src

ENV CONNECTOR_ID=cortex-content
