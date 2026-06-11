# `bundles/spark/connectors/` — per-instance connectors

Each connector ships as its own image at customer release time. The agent dispatches to per-instance containers via HTTP, not in-process Python — crash isolation + independent versioning. `guardian-updater` (see [`../../../updater/CLAUDE.md`](../../../updater/CLAUDE.md)) starts/stops the per-instance containers.

**Repo-wide rules live in the [root CLAUDE.md](../../../CLAUDE.md)** — credential guardrail, contained-release discipline, bug-family audit. This file holds only conventions LOCAL to connector authoring.

## Layout

Each connector is a subdirectory named after itself:
- `xsoar/` — Cortex XSOAR case (incident) integration. Supports XSOAR 6 (on-prem, single API key in the Authorization header) and XSOAR 8 / Cortex cloud (API key + key id via `x-xdr-auth-id`, `/xsoar/public/v1` path prefix). Detection: `api_id` set → v8; else v6.
- `cortex-docs/` — Cortex documentation search
- `web/` — Web browsing via Playwright + headless Chromium (guardian-browser CDP)
- `_runtime/` — the shared `guardian-connector-runtime` base image source (not a connector itself; the others build `FROM` it).

`connector.schema.json` (top-level here) is the JSON-Schema validator every `connector.yaml` validates against at boot AND at upload time.

## Connector authoring (the 5-step pattern)

1. **`connector.yaml`** — declares the connector's metadata, runtime style, schema, tool list, config fields. Validates against `connector.schema.json`.
2. **`src/connector.py`** — the connector's entry point. Inherits from the `guardian-connector-runtime` base (`../../../guardian-connector-runtime/`).
3. **`src/<tool>.py` files** — per-tool implementations.
4. **`tests/`** — connector-local pytest suite.
5. **`Dockerfile`** — `FROM ghcr.io/kite-production/guardian-connector-runtime:latest`. CI builds + tags each connector image at customer release time.

## Runtime style

`runtimeMapping.style: container` is the only supported style as of v0.5.0. Each instance = one Docker container, managed by `guardian-updater`. The agent's tool dispatcher proxies calls over MCP-over-HTTP to `http://guardian-connector-<id>-<name>:9000`.

Pre-v0.5.0 `module` style (in-process Python inside the agent) is removed.

## Catalog boundary (v0.5.0+)

The agent has 4 MARKETPLACE tools available — these mutate catalog metadata:
- `marketplace_list` — read-only catalogue + install state
- `marketplace_install(connector_id)` — idempotent install row write
- `marketplace_uninstall(connector_id)` — refuses if any instances exist
- `connector_upload(yaml_content)` — validates + writes the user_connectors directory

The agent does NOT have INSTANCE tools — instances carry credentials, which are operator-only. See root § Catalog boundary ≠ credential boundary for the rule.

## Import-style discipline (v0.5.77 bug pattern)

Use `from src.X import Y` (with `src.` prefix) — NOT `from usecase.X import Y`. The latter only resolves with a specific PYTHONPATH that production deployments don't always have. v0.5.77 + v0.5.80 cleaned up the family of bugs caused by mixed import styles. When in doubt, grep for `from usecase\\.` across connectors before merging.

## User-uploaded connectors

The operator can upload custom `connector.yaml` via `POST /api/v1/marketplace/upload` (multipart) or `connector_upload(yaml_content)` (agent). Validation:
- Schema validation against `connector.schema.json` (same as bundle connectors).
- `id` must not collide with a bundle id (409 `id_collides_with_bundle`) or another user id (409 `id_already_exists`).
- YAML MUST declare an `image` field — the OCI reference to the operator's pre-published connector container. guardian-updater pulls this image when instances are created.

User connectors land at `/app/data/user_connectors/<id>/connector.yaml` (volume-persistent). `DELETE /api/v1/marketplace/<id>` removes them. Bundle connectors are 403-rejected on DELETE — image-baked, can't be removed at runtime; use Uninstall to hide them from instance creation.
