# `xlog/` — log-generation backend

The `xlog` customer container (formerly `phantom`). FastAPI + Strawberry GraphQL + the external `rosetta-ce` library. The single source of truth for log generation in Phantom — every faker / scenario / sender enum lives here, not in the MCP layer.

**Repo-wide rules live in the [root CLAUDE.md](../CLAUDE.md)**. This file holds only conventions LOCAL to xlog.

## Layout

| Path | What it is |
|------|------------|
| `main.py` | Mounts Strawberry GraphQL at `/` on the FastAPI app. |
| `app/schema.py` | All GraphQL queries + mutations. **Active workers live in a module-level `workers = {}` dict** — no persistence. Restarting the container drops every streaming worker; `listWorkers` is per-replica. |
| `app/types/datafaker.py` | Strawberry enums for worker types + faker formats. |
| `app/types/scenarios.py` | Scenario shape definitions. |
| `app/types/sender.py` | Destination + format enums. |
| `app/dynamic_schema.py` | v0.8.0+ schema-override value generator for `generate_fake_data_v2`. Priority: `observable_overrides` → `type_hint` → field-name pattern → Rosetta fallback. |
| `app/config.py` | Reads `config.yml` + env overrides. |
| `config.yml` | Worker count, log rotation, XSIAM mandatory/optional parsed fields. Mostly env-var overridden (`WORKERS_NUMBER`, `LOGGING_*`, `XSIAM_*`). |
| `scenarios/ready/*.json` | Pre-built scenario files. |
| `tests/` | pytest suite (~28 tests). |

## Single source of truth — log generation

The GraphQL endpoint is the **only** place log synthesis lives. The MCP server (`bundles/spark/mcp/`) calls it via `pkg/graphql_client.py`. **Do not duplicate faker logic into the MCP layer or any connector.** If you find yourself reaching for `rosetta-ce` outside this directory, you're wrong.

## External dependency — `rosetta-ce`

Log synthesis comes from the external `rosetta-ce` library (`Events`, `Observables`, `Sender`) — not in this repo. Format types, scenario shapes, and worker I/O are declared in `app/types/`.

## Webhook sender — non-Bearer auth header

The webhook sender uses header `Authorization: <WEBHOOK_KEY>` (RAW, not `Bearer`) — see `_get_webhook_headers` in `app/schema.py`. Any non-XSIAM webhook receiver must accept that form. **Never reformat this to `Authorization: Bearer <KEY>`** — it breaks every existing customer integration.

## Scenario file conventions

- Scenario files live in `scenarios/ready/*.json`.
- `createScenarioWorker` takes the filename **without `.json`** (e.g. `port_scan`, NOT `port_scan.json`).
- For inline scenarios use `createScenarioWorkerFromQuery` instead.

## Adding a new log format or destination

Touch BOTH:
1. The Strawberry enum in `app/types/datafaker.py` (worker type / faker format) or `app/types/sender.py` (destination).
2. The dispatch in `app/schema.py`.

If you only touch one, you'll ship an enum value that the dispatcher rejects, or a dispatch path that no client can reach. Both must change in the same commit.

## v0.8.0+ `generateFakeDataV2(requestInput, schemaOverride)`

The newer GraphQL field for fake-data synthesis. When `schemaOverride` is supplied, top-level keys + value generation come from the override (vendor-faithful records). When omitted, falls back to identical Rosetta behavior — strict backward-compat with `generateFakeData`.

The override engine is in `app/dynamic_schema.py`. Each field's value resolves in priority order: `observable_overrides` → `type_hint` → field-name pattern (`srcip` → IPv4, `sentbyte` → byte-count integer) → Rosetta fallback.

## Tests

```bash
cd xlog
python3 -m pytest -x   # ~28 tests
```

## Pre-deploy gate

Pytest for xlog runs as part of the agent build (CI) — the agent image bakes the MCP, not the xlog service, but xlog tests are part of the workflow. Locally run xlog tests with the snippet above when touching `app/schema.py`, `app/types/*.py`, or `app/dynamic_schema.py`.
