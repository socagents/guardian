# Spec patch: YAML-on-disk runtime job definitions

> **Audience**: maintainers of `kite-production/spark-agents/docs/spec.md`.
> This file is a draft upstream-PR for `spec.md` v1.3 clarifying the
> storage convention for runtime jobs. It also serves as authoritative
> documentation for guardian's implementation while the upstream PR
> is in flight.

## Context

`spec.md` v1.2 §7.1 specifies the bundle file layout:

```
slack-triage-2.1.0.tar.zst
└── slack-triage/
    ├── manifest.yaml
    ├── jobs/
    │   └── daily-summary.yaml
    ...
```

…and §7.2 gives the manifest's `jobs:` block schema (cron, timezone,
action). But the spec **does not currently distinguish** between:

1. **Manifest jobs** — declared inline in `manifest.yaml:jobs[]`.
   Source of truth: the manifest itself. Reconciled at boot. Reverts
   to manifest values on every redeploy.
2. **Bundle-shipped job files** — `<bundle>/jobs/*.yaml` (per the
   §7.1 layout). Read at boot. **Same lifecycle as manifest jobs**:
   read-only at runtime; redeploy to change.
3. **Runtime jobs** — operator-created via the runtime API
   (`POST /api/v1/jobs` per §6.10 row 6). Today the spec says these
   live in the standalone scheduler's SQLite store with no on-disk
   YAML mirror — making them invisible to git, undiffable across
   operators, and lost if the SQLite volume is wiped while the
   bundle volume is kept.

The third category is the gap. The spec should say what happens to
runtime jobs *on disk*.

## Proposal

Extend §7.1 + §6.10 with a clear three-tier storage model:

```
Standalone deploy directory layout:

  <bundle>/                         (read-only at runtime)
    ├── manifest.yaml               # Tier 1: manifest jobs
    └── jobs/                       # Tier 2: bundle-shipped jobs
        └── *.yaml                  #         (also boot-replayed)

  <data_root>/                      (mutable at runtime)
    ├── jobs.db                     # SQLite — runtime state
    │                               # (next_due_at, last_status,
    │                               #  run_count, run history)
    └── jobs/                       # Tier 3: operator-created
        └── *.yaml                  #         runtime jobs
                                    #         (mirror of source='runtime'
                                    #          rows in jobs.db)
```

### Tier-by-tier semantics

| Tier | Source | YAML location | DB row source | Mutable at runtime? | Survives DB wipe? | Survives bundle wipe? |
|---|---|---|---|---|---|---|
| 1 | `manifest.yaml:jobs[]` | inline in manifest | `manifest` | ❌ — redeploy to change | ✅ (re-reconciled from manifest) | ❌ (manifest gone) |
| 2 | `<bundle>/jobs/*.yaml` | `<bundle>/jobs/<name>.yaml` | `manifest` | ❌ — redeploy to change | ✅ (re-reconciled from disk) | ❌ (bundle gone) |
| 3 | `POST /api/v1/jobs` | `<data_root>/jobs/<name>.yaml` | `runtime` | ✅ — PATCH/DELETE via API | ✅ (re-loaded from `<data_root>/jobs/`) | ✅ (data root persists across redeploys) |

The new Tier 3 row is the meaningful change: **operator-created
runtime jobs MUST persist as YAML files at `<data_root>/jobs/`,
mirrored on every CRUD operation**, in addition to the SQLite row.

### YAML schema (definition fields only)

```yaml
# Guardian runtime job definition (source='runtime').
# Edit + restart agent-runtime to apply. SQLite holds runtime state
# (last_fired_at, next_due_at) which is computed from this file at boot.
name: nightly-coverage-rollup
cron: "0 2 * * *"
timezone: UTC
enabled: true
run_once: false
action:
  type: prompt
  message: Generate a coverage report for the last 7 days
```

The YAML carries **definition** fields only — name, cron, timezone,
enabled, run_once, action. **It MUST NOT carry runtime state** like
`next_due_at`, `last_fired_at`, `last_status`, `run_count`,
`registered_at`, `removed`. State stays in the DB so the YAML diff
is quiet across cron ticks (the file changes only when the
operator changes the definition).

### Lifecycle contract

```
Boot:
  1. Reconcile <bundle>/jobs/ + manifest.yaml:jobs[]  → DB rows
                                                       source='manifest'
  2. Replay <data_root>/jobs/*.yaml                   → DB rows
                                                       source='runtime'
                                                       (idempotent: ON CONFLICT)

Create (POST /api/v1/jobs):
  1. Validate cron + action
  2. INSERT into jobs.db with source='runtime'
  3. AFTER successful INSERT, write <data_root>/jobs/<name>.yaml
     (atomic: tmp + rename)

Update (PATCH /api/v1/jobs/{name}):
  1. UPDATE jobs.db
  2. AFTER successful UPDATE, re-export the YAML mirror

Delete (DELETE /api/v1/jobs/{name}):
  1. DELETE jobs.db row + run history (runtime jobs)
     OR mark removed=1 (manifest jobs)
  2. For runtime jobs only: remove <data_root>/jobs/<name>.yaml

Boot reconciliation rules:
  - Manifest jobs (Tier 1+2) ALWAYS reset their cron/timezone/action
    from the manifest at every boot. This is by design — manifest is
    canonical.
  - Runtime jobs (Tier 3) survive boot reconciliation — the YAML
    mirror replay is idempotent (ON CONFLICT updates). Operators
    can edit the YAML on disk + restart to apply.
```

### Why YAML mirror, not "YAML as system of record"

The dual-write design (SQLite for runtime state, YAML for
definition) is deliberate. Three alternatives we explicitly rejected:

1. **YAML as the only store**. Bad — `next_due_at` updates every
   tick; rewriting a file on every cron tick wastes I/O and creates
   a noisy diff. Multi-process safety becomes nontrivial.
2. **SQLite as the only store** (the v1.2 status quo). Bad — runtime
   jobs are invisible to git, undiffable across operators, lost if
   the DB volume is wiped while the bundle volume is kept.
3. **Manifest-extension** (add a `runtimeJobs:` block to
   `manifest.yaml`). Bad — couples runtime ops to source code repo;
   redeploy to change; conflates two distinct lifecycles.

Dual-write keeps definition + state separate, each in the storage
medium that suits its access pattern.

### Defense-in-depth

- Job names MUST be filesystem-safe (no `/`, `\`, `..`, `.`).
  Validation runs at the API boundary (`POST /api/v1/jobs`) and
  again at the path-builder (belt-and-suspenders against curl-
  injected names).
- One malformed YAML file in `<data_root>/jobs/` MUST NOT abort
  boot. Log + skip + continue; operator fixes the file in place.
- YAML write is atomic (tmp file + rename) so a crash mid-write
  doesn't leave a corrupt file.
- A YAML write failure logs but does NOT roll back the SQLite
  insert — the job is still live in the DB and fires normally;
  the operator can re-export later.

## Reference implementation

See `bundles/spark/mcp/src/usecase/job_scheduler.py` in the
`kite-production/guardian` repo:

- `_write_job_yaml(row)` — atomic YAML write with the banner
- `_remove_job_yaml(name)` — delete the on-disk file
- `load_yaml_jobs()` — boot-time replay
- `_job_yaml_path(name)` — path validation
- Round-trip tests in `tests/test_job_yaml_roundtrip.py` (9 cases
  covering happy path + boot replay + idempotency + path traversal
  + malformed-file resilience).

## Backwards compatibility

The change is **additive**. Deploys that don't have a
`<data_root>/jobs/` directory continue to work — the boot loader
no-ops if the directory is absent. Deploys that do have it gain
git-trackable runtime job definitions.

The SQLite schema is unchanged. The `jobs` table's `source` column
already distinguishes manifest vs runtime; this proposal piggybacks
on that distinction for the disk-mirror policy.
