# R3.C — Per-Data-Source YAML + CRUD + Bundled Migration (v0.13.0)

**Status**: Approved 2026-05-23 — autonomous implementation in progress. Operator instructed to "finish as much as you can" + run E2E with temp syslog.

## Goal

Convert the bundled 197-pack catalog from baked `catalog.json` + per-pack `pack_metadata.json` to a per-data-source YAML format, AND add operator-uploadable data sources following the same shape. Single canonical format for everything in the marketplace: bundled and user.

## Non-goals

- Schema evolution beyond `schema_version: 1`
- Cross-deployment export/import (defers to /settings/backup-restore)
- Operator-authored extensions of bundled packs (custom YAMLs are standalone sources)
- Retiring `catalog.json` (kept as backward-compat read path during transition)

## YAML schema (decisions locked in brainstorm)

Identity: **3-tuple** (`pack_name` / `rule_name` / `dataset_name`) — preserves compatibility with the entire existing system.

Field types: **comprehensive controlled vocab** including `string_short`, `string_long`, `json`, `enum`, `regex`, plus the IP/port/hash/datetime/email/etc. set. Unknown types fall back to xlog's existing field-name pattern matching.

Logo: **SVG-preferred, raster fallback** up to 512×512, 50KB pre-base64, transparent bg, embedded inline as base64.

Origin: **`bundle` vs `user`** label on every entry — UI surfaces a badge; agent reasoning distinguishes.

Similarity check on upload: **Levenshtein-2 + substring** match against existing vendors; operator gets a "did you mean Amazon?" prompt + chooses group-or-create.

See full schema example in the design doc.

## Storage layout

```
bundles/spark/data-sources/                     # bundled (in repo, image-baked)
  data_source.schema.json                       # JSON Schema validator
  <pack_id>/
    data_source.yaml                            # the spec
    logo_light.svg                              # optional sidecar (overrides YAML's inline logo)

/app/data/user_data_sources/                    # operator-uploaded (volume-persistent)
  <pack_id>/
    data_source.yaml                            # uploaded YAML
```

Loader reads BOTH directories. Collision rule: `bundle` always wins for same id (operator can't override bundled packs; they create new ids).

## REST + MCP surface

```
POST   /api/v1/data-sources/user/preview        # validate + similarity check; returns prompt
POST   /api/v1/data-sources/user                # commit upload (accept_token from preview)
GET    /api/v1/data-sources/user                # list operator-uploaded
GET    /api/v1/data-sources/user/<id>           # one operator-uploaded source
DELETE /api/v1/data-sources/user/<id>           # remove operator-uploaded
```

PUT (update) deferred — operator re-uploads with the same id.

## Phased delivery

- **R3.C.0 (v0.13.0)** — Schema + migration + loader + validator. Bundled packs as YAML; end-user behavior unchanged.
- **R3.C.1 (v0.13.1)** — Upload endpoints + similarity check + origin labeling.
- **R3.C.2 (v0.13.2)** — UI upload dialog on /data-sources.
- **R3.C.3 (v0.13.3)** — E2E test with temp syslog server.

Operator approved "go with recommendations; finish as much as you can." Each sub-arc ships as a customer tag when its capability acceptance is met.

## E2E test (per operator request)

1. Start a temp syslog server (Python UDPServer inside xlog container)
2. Upload a custom data_source.yaml — small "AcmeCorp" vendor with 5 fields
3. Install via `data_sources_install`
4. Call `phantom_create_data_worker` with `schema_override` + UDP destination
5. Server captures datagrams; validate fields match the uploaded YAML's declarations
6. Cleanup
