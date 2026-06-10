# guardian-connector-cortex-docs — per-connector image for the Cortex
# public-documentation search/lookup connector. Built FROM
# guardian-connector-runtime.
#
# Adds zero extra Python dependencies — the upstream scripts use only
# stdlib (urllib, json, re, argparse, pathlib). The base runtime image
# already has httpx + pydantic which the embedded MCP needs to host the
# tool surface; the connector itself doesn't import either.
#
# Note: cortex-docs is currently `style: "module"` per connector.yaml,
# so this image is built as part of the v0.3.0+ digest-pinning manifest
# but is NOT instantiated as a per-instance container today. It exists
# for the v0.2 container-mode future (per docs/spec-per-instance-
# connector-containers.md) and so the cortex-docs connector code lives
# at the same FS path inside the agent container as the in-process
# loader expects (`/app/connectors/cortex-docs/src`). Mirroring the
# xsiam/cortex-xdr/web Dockerfile pattern keeps the surface uniform
# even though only some connectors are flipped to container mode.

ARG GUARDIAN_RUNTIME_VERSION=latest
FROM ghcr.io/kite-production/guardian-connector-runtime:${GUARDIAN_RUNTIME_VERSION}

LABEL org.opencontainers.image.source="https://github.com/kite-production/guardian"
LABEL org.opencontainers.image.description="Guardian cortex-docs connector container — Palo Alto Networks Cortex public-documentation search/lookup. Tools: cortex_search, cortex_suggest, cortex_xql_lookup, cortex_fetch_topic, cortex_fetch_toc, cortex_deep_research."

# No extra deps. The upstream scripts are stdlib-only.

COPY bundles/spark/connectors/cortex-docs/src /app/connectors/cortex-docs/src

ENV CONNECTOR_ID=cortex-docs
