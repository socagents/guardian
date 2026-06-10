# Data source versioning, edit & rollback — design

**Date:** 2026-05-29
**Status:** Approved (operator, 2026-05-29) — ready for implementation plans
**Arc:** SP-4 / SP-5 / SP-6 (the "versioning arc"), deferred from the data-source quick-fix batch (v0.17.94–98)
**Spec mechanism note:** Per the project's spec-driven workflow, each sub-release also gets a GitHub issue whose body becomes its CHANGELOG entry. This doc is the arc-level design the sub-release issues reference.

---

## Problem / motivation

Operators want to **edit** a data source's `how_to_use` and schema, with **version history** and **rollback**, directly from the `/data-sources` card. Today:

- **Bundled (system) data sources are read-only** — the loader hard-codes "bundle always wins" and refuses to let anything shadow them. There is no edit path for them at all.
- **User-uploaded sources** can be edited in place (`update_user`) but with **no history** — an edit overwrites the YAML, losing the prior content.
- There is **no version store** anywhere.

The goal: a single, coherent versioning model where any data source can be edited (creating a new version), its history viewed, any version rolled back to (non-destructively), and any version exported — all without mutating the read-only bundle baseline.

## Decisions (operator-approved)

| Decision | Choice |
|---|---|
| **Scope** | **All sources** (system + user). One version model, keyed by source id, origin-agnostic. |
| **Rollback** | **Non-destructive** — rolling back to vK copies it forward as a new current; vK+1…vN stay in history. |
| **Edit surface** | **UI + agent MCP tool.** Operator edits from the card; the agent gets a catalog-side `data_sources_edit` tool. |
| **Overlay mechanism** | **Version store IS the overlay.** One SQLite store holds every snapshot incl. the current; the loader reads current-version-first, falling back to file. Bundle/user files stay pristine. |
| **Edit scope** | `how_to_use` + all schema columns: `name`, `type`, `description`, `example`, `is_meta`, `is_array`. |
| **Delete** | **No delete.** Edit + save + rollback only. |
| **Version trigger** | Every save = a new version (no separate "publish" step). |

## Data model

New store `data_source_versions.db` at `/app/data/` (volume-persisted, sibling of `data_sources.db`), fronted by `data_source_versions_store.py` (mirrors the existing `data_sources_store.py` pattern):

```sql
data_source_versions (
  data_source_id  TEXT    NOT NULL,   -- composite "pack/rule/dataset" (compose_data_source_id)
  version         INTEGER NOT NULL,   -- monotonic per source, starts at 1
  yaml_snapshot   TEXT    NOT NULL,   -- full data_source.yaml content at this version
  created_at      TEXT    NOT NULL,
  author          TEXT    NOT NULL,   -- "operator" | "agent" | "bundle-baseline"
  note            TEXT,               -- optional edit note
  is_current      INTEGER NOT NULL DEFAULT 0,  -- exactly one row per source
  PRIMARY KEY (data_source_id, version)
)
```

**Baseline rule.** The first time a source is edited, the store snapshots the *original file content* as **v1** (`author: bundle-baseline`), then writes the edit as **v2** (`is_current`). The pristine original is always recoverable; the bundle/user file on disk is never mutated.

**Loader overlay resolution.** `get_by_3tuple` / `list_all` resolve each source in order:
1. **version-store current** (if any version exists for this id) →
2. user YAML →
3. bundle YAML.

A source with no versions is served from its file exactly as today. This is the only behavioral change to the loader. If the version store is unavailable, the loader degrades to file resolution (the source still loads, just without overlay).

## Flows

- **Edit** (UI form *and* agent tool): validate the edited YAML against `data_source.schema.json` + the field-name-uniqueness check → if valid, snapshot as `vN+1`, set `is_current`, clear the prior current. System (bundled) sources surface a warning before save: "this is a system data source — your edit becomes an operator override." Invalid input is rejected *before* any snapshot is written.
- **Rollback** (non-destructive): roll back to `vK` → copy `vK`'s `yaml_snapshot` forward as a new `vN+1` (`is_current`, `note: "rolled back to vK"`). `vK+1…vN` remain in history. Roll-forward is always possible.
- **Export**: read any chosen version's `yaml_snapshot` verbatim. The export-version dropdown picks which (default: current).

## Surfaces

**Backend**
- `data_source_versions_store.py` (new): `snapshot(id, yaml, author, note)`, `get_current(id)`, `list_versions(id)`, `get_version(id, n)`, `rollback(id, k)`, baseline-on-first-edit.
- `data_sources_yaml_loader.py`: inject the version store; `get_by_3tuple`/`list_all` consult it for a current override.

**REST** (`api/data_sources.py`, all catalog-side; + Next.js `app/api/agent/data-sources/**` proxies):
- `PUT …/{pack}/{rule}/{dataset}/edit` — body = edited `how_to_use` + `fields[]` (+ optional `note`); validate + snapshot.
- `GET …/{pack}/{rule}/{dataset}/versions` — version metadata list.
- `GET …/{pack}/{rule}/{dataset}/versions/{n}` — one version's full content.
- `POST …/{pack}/{rule}/{dataset}/rollback` — body `{version: k}`.
- `GET …/{pack}/{rule}/{dataset}/export?version=n` — extend the existing export with an optional version param.

**Agent MCP tools** (catalog-side, `mcp.tool()`-registered): `data_sources_edit`, `data_sources_list_versions`, `data_sources_rollback`. **Catalog-boundary check (CLAUDE.md):** editing schema/how_to_use is catalog metadata, NOT a SecretStore value → safe to register, same side of the boundary as `marketplace_install` / `connector_upload`. Each tool gets a docstring with an Args section + example payload (the agent picks fields from the docstring).

**UI** (`app/data-sources/page.tsx` DetailDrawer):
- **Edit** button (drawer header) → form: `how_to_use` textarea + editable fields table (name/type/description/example/is_meta/is_array). System sources → warning modal first.
- **Version dropdown** → select a prior version to view (read-only render of that snapshot); "Roll back to this version" on non-current versions.
- **Export** → small dropdown: "Current" + "Version…".
- Save → calls the edit endpoint → refetch the drawer.

## Sub-release decomposition (build order)

Each is a contained release with its own issue, CHANGELOG/release-notes entry, deployed smoke, and docs.

- **SP-4 — foundation + edit.** Version store + store module + loader overlay resolution + edit REST endpoint + `data_sources_edit` agent tool + UI edit form + system-source warning + save→version.
  *Acceptance:* edit any data source from the card OR via the agent; edits create versions; the original is preserved as v1; the deployed catalog/drawer serves the edited content.
- **SP-5 — history + rollback.** `versions` + `versions/{n}` endpoints + `data_sources_list_versions` / `data_sources_rollback` agent tools + drawer version dropdown (view any version) + non-destructive rollback action.
  *Acceptance:* view a source's full version history; roll back to any version; history is preserved (roll-forward works).
- **SP-6 — export-version picker.** `export?version=` + UI export dropdown ("Current" / "Version…").
  *Acceptance:* export any version's YAML; default export = current.

## Error handling

- Edit validates against `data_source.schema.json` + field-name uniqueness *before* snapshotting; invalid → 4xx, no version written.
- Rollback to a nonexistent version → 404.
- Concurrent edits → monotonic version increment; no lost versions (last write becomes current; intermediate versions retained).
- Loader degrades to file resolution if the version store is unavailable (source still loads).
- System-source edit without acknowledging the warning (UI) → blocked client-side; the REST/agent path still permits it (the warning is a UI affordance, not a server gate) — documented so the agent tool's docstring sets expectations.

## Testing

- Store unit tests: snapshot, baseline-on-first-edit, `get_current`, `list_versions`, `get_version`, non-destructive `rollback`, single-`is_current` invariant.
- Loader overlay test: store-current wins over user YAML wins over bundle; no-version source unchanged; store-down degrades to file.
- Edit endpoint: rejects schema-invalid + duplicate-field YAML before snapshot; accepts valid → new current version.
- Rollback: non-destructive (history length grows, target content becomes current).
- Export-by-version: returns the chosen snapshot verbatim.
- Agent tool dispatch: `data_sources_edit` / `_list_versions` / `_rollback` round-trip.
- Per-sub-release deployed smoke on phantom-vm (edit a source → confirm the drawer/catalog serves the edit; roll back → confirm; export a version).

## Documentation discipline (per sub-release)

- `/help/architecture#data-sources` — add the versioning subsystem (store, overlay resolution, version lifecycle, inter-service wiring).
- `/help/user` — the edit / version-history / rollback / export-version flows.
- `lib/journeys.ts` — "edit a data source", "roll back a data source" journeys.
- `CHANGELOG.md` + `lib/release-notes.ts` — per release.
- MCP tool docstrings in lockstep with the UI edit form (CLAUDE.md doc-discipline rule 9).

## Out of scope (this arc)

- Auto-applying upstream bundle upgrades to edited sources — the store's current overlays the bundle; a bundle change on image upgrade does NOT auto-merge into an edited source. The operator can roll back to re-baseline. (Future: a "bundle updated — review?" affordance.)
- Diff view between versions (history shows snapshots, not inline diffs). Future enhancement.
- Per-field-level version granularity (versions are whole-source snapshots).
- Delete (explicitly excluded by the operator).

## Spec self-review

- Placeholders: none.
- Consistency: rollback non-destructive throughout; "version store is the overlay" consistent across data model / loader / flows / surfaces.
- Scope: decomposed into SP-4/5/6, each independently shippable + testable.
- Ambiguity: edit scope enumerated explicitly; baseline rule explicit (v1 = original); concurrent-edit + store-down behavior specified.
