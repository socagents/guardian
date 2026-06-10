# Spec patch: KB backends, runtime CRUD seam, and operator UI conventions

> **Audience**: maintainers of `kite-production/spark-agents/docs/spec.md`.
> Draft upstream-PR for `spec.md` v1.3, clarifying three things the
> v1.2 spec leaves under-specified about knowledge bases:
>
>   1. **The brute-force escape hatch** — when standalone deploys
>      outgrow O(N) cosine, what's the spec-blessed path?
>   2. **The multi-impl seam** — what does it take to register a
>      non-default KB backend (Lance, OpenSearch, pgvector) without
>      breaking bundle portability?
>   3. **The runtime-CRUD seam** — how does Tier-3 (operator-added KB
>      content at runtime) compose with the existing manifest-shipped
>      Tier-1+2 KBs, and what does it mean for the on-disk layout?
>
> Also serves as authoritative documentation for guardian's
> implementation while the upstream PR is in flight.

## Context

`spec.md` v1.2 §6.4 + §6.10 + §8.1 already nails the *interface* for
KBs:

- Capability registry row `knowledge` with two impls: `SqliteKnowledgeBase`
  (standalone) + `OpenSearchKnowledgeBase` (platform).
- Standalone storage at `<data_root>/kb.db` — single SQLite file,
  multi-KB rows keyed by `kb_name + doc_id`, embedding stored as
  packed `float32` BLOBs, brute-force cosine over all rows.
- Bundle layout: `manifest.knowledge.bundled[].path: ./kbs/<name>/`
  + per-KB `schema.json`. Boot loader hashes each file's bytes and
  re-embeds only on hash change.

What the spec **does not yet say**:

| Question | v1.2 status |
|---|---|
| What's the standalone path past brute-force? | Silent — implies "swap the impl" but no guidance |
| Can a bundle declare an alternate vector backend? | No extension point |
| Can operators add docs at runtime? | Implicit `kbWrites: []` says no, but Tier-3 demand is real |
| What's the operator-facing UI surface for KBs? | Silent (no UI shipped) |

This patch addresses all four.

## Proposal A: sqlite-vec as the "next stop" past brute-force

Brute-force cosine works through ~10K rows comfortably. Past that,
search latency becomes operator-noticeable. The spec should bless
**`sqlite-vec`** (the modern fork of `sqlite-vss`, Alex Garcia, 2024)
as the standalone-tier ANN escape hatch — same `kb.db` file, same
deployment topology, optional 700 KB extension that adds HNSW.

### Manifest extension (additive, opt-in)

```yaml
knowledge:
  bundled:
    - name: "guardian-soc"
      path: "./kbs/guardian-soc/"
      schema: "./kbs/guardian-soc/schema.json"
      # New v1.3 field. Default: "brute". Bundle authors opt in
      # per-KB based on row-count budget.
      vector_index: "hnsw"
```

### Lifecycle

```
Boot:
  IF vector_index == "hnsw":
    1. Try to load sqlite-vec extension (CREATE VIRTUAL TABLE ... USING vec0)
    2. On load failure: log a warning, fall back to brute-force scan
       (don't abort boot — the agent stays usable)
    3. On success: create per-KB vec0 virtual table; populate from
       kb_documents.embedding column
  ELSE: brute-force as today

Search:
  IF hnsw populated for this kb_name:
    SELECT ... FROM vec_<kb> WHERE embedding MATCH ? AND k = ?
  ELSE: brute-force
```

### Why sqlite-vec, not LanceDB / pgvector / OpenSearch in standalone

| Backend | Image cost | RAM floor | Cold start | Suitable for standalone? |
|---|---|---|---|---|
| Brute-force (today) | 0 | ~10 MB | <100 ms | ✅ up to ~10K rows |
| **sqlite-vec** | +700 KB ext | ~10 MB | <100 ms | ✅ up to ~1M rows |
| LanceDB | +120 MB | ~150 MB | ~2 s | ❌ heavy for single-tenant |
| pgvector | +200 MB image | ~512 MB | ~5 s | ❌ separate container |
| OpenSearch | +1 GB image | ~2 GB JVM | ~30 s | ❌ JVM heap on the deploy host |

The spec already keeps platform-tier backends (LanceDB / pgvector /
OpenSearch) for the *amortized-across-tenants* case. The standalone
tier's value prop is "one tarball, one container, no externals" —
adding Postgres or OpenSearch breaks that. sqlite-vec preserves the
deployment shape and gets ~100× speedup at 100K rows.

## Proposal B: per-KB embedding model override

v1.2 has a single bundle-level `memory.embeddingProvider` /
`memory.embeddingModel`. KBs inherit it. Two pain points:

1. Some KBs benefit from *code-tuned* embedders (e.g. CodeBERT for SQL
   examples), others from text-tuned. Locking the bundle to one model
   forces a worst-case compromise.
2. Migrating an existing KB to a new model requires either (a) wiping
   `kb.db` and re-embedding everything, or (b) running side-by-side
   embedders during cutover. Spec is silent on either.

### Proposal

Allow a per-KB override:

```yaml
knowledge:
  bundled:
    - name: "xql-examples"
      path: "./kbs/xql-examples/"
      schema: "./kbs/xql-examples/schema.json"
      # New v1.3 field (optional). Falls back to memory.embeddingModel.
      embedding:
        provider: "google"
        model: "text-embedding-004"
        dims: 768
```

The boot loader sets up one Embedder instance per distinct
(provider, model, dims) tuple and routes each KB's upserts to its
own. The schema adds an `embedding_model_id` column to
`kb_documents` so cross-model search becomes a hard error rather
than silent garbage.

## Proposal C: Runtime-CRUD seam (Tier 3)

Today's spec models KBs as immutable bundle artifacts. Operator
demand is for the same Tier-3 escape hatch we landed for jobs (see
`spec-patch-yaml-job-defs.md`): the manifest ships base content,
runtime adds + edits land in `<data_root>/kb/<name>/` as YAML/MD,
both flow into the same `kb.db`.

### Three-tier KB model (mirrors jobs)

```
<bundle>/                                 (Tier 1+2: ships with bundle)
  ├── manifest.yaml                       # knowledge.bundled[]
  └── kbs/<name>/
      ├── schema.json
      └── entries/*.md                    # operator-curated, git-trackable

<data_root>/                              (mutable at runtime)
  ├── kb.db                               # SqliteKnowledgeBase
  └── kb/<name>/                          # Tier 3: runtime-added entries
      └── entries/*.md                    # mirror of source='runtime' rows
                                          # written via POST /api/v1/kbs/{name}/entries
```

### Lifecycle contract

```
Boot:
  1. Reconcile <bundle>/kbs/*/entries/         → kb.db (source='manifest')
  2. Replay <data_root>/kb/*/entries/          → kb.db (source='runtime')
                                                 (idempotent: ON CONFLICT)

Create entry (POST /api/v1/kbs/{name}/entries):
  1. Validate against schema.json
  2. Compute doc_id (frontmatter.id or hash of content)
  3. INSERT into kb.db with source='runtime'
  4. AFTER insert: write <data_root>/kb/{name}/entries/<doc_id>.md
     (atomic: tmp + rename)

Update / delete: same pattern, mirrored to disk.

Boot reconciliation rules:
  - Manifest entries (Tier 1+2): cron/category/etc. ALWAYS reset
    from disk at every boot. Operator changes are lost on redeploy.
  - Runtime entries (Tier 3): survive boot reconciliation —
    <data_root>/kb/ replay is idempotent.
```

### Capability gate

```yaml
capabilities:
  kbReads: ["guardian-soc", "xql-examples"]
  kbWrites:
    - "operator-runbooks"   # Tier-3 KB; agent can write here
```

When `kbWrites[]` is empty (the v1.2 default), the runtime simply
doesn't expose `POST /api/v1/kbs/{name}/entries` — back-compat
preserved.

## Proposal D: Operator-facing UI conventions

v1.2 ships no operator UI for KBs. Guardian is filling the gap — the
agent has a `/knowledge` route with two read-only tabs (Entries +
Try search) and stubs for two future tabs (Import + Settings) gated
on Tier-3. Spec should document the convention so other bundles
converge.

### Recommended routes (single-tenant standalone)

```
/knowledge                   list of loaded KBs
/knowledge/{name}            detail; tabs: Entries | Try search | (Import) | (Settings)
```

Multi-tenant deploys (the spark-platform case) prepend
`/w/{workspace}/` per spark_ui's existing convention.

### Recommended API surface (already in spec §6.10)

```
GET    /api/v1/kbs                      # list summaries (name, doc_count, latest_loaded_at)
GET    /api/v1/kbs/{name}/docs          # paginated browse (no content)
GET    /api/v1/kbs/{name}/docs/{id}     # full doc (audited)
POST   /api/v1/kbs/{name}/search        # KB-scoped semantic search
POST   /api/v1/kbs/search               # cross-KB semantic search
```

Plus, when `kbWrites[name]`:
```
POST   /api/v1/kbs/{name}/entries
PATCH  /api/v1/kbs/{name}/entries/{id}
DELETE /api/v1/kbs/{name}/entries/{id}
POST   /api/v1/kbs/{name}/imports       # bulk: CSV / JSONL / MD dir
```

## Reference implementation

In `kite-production/guardian`:

- `bundles/spark/mcp/src/usecase/kb_store.py` — `SqliteKnowledgeBase`
  (multi-KB, brute-force cosine, source-hash change detection)
- `bundles/spark/mcp/src/usecase/kb_loader.py` — boot reconciliation
- `bundles/spark/mcp/src/usecase/vertex_embedder.py` — `text-embedding-004`
  with LRU cache + TextHash fallback
- `bundles/spark/mcp/src/api/kb.py` — REST endpoints
- `bundles/spark/kbs/xql-examples/` — first migrated KB (161 entries,
  ported from a Chroma + Nomic-MoE outlier; demonstrates the
  spec-compliant pattern)
- `mcp/agent/app/knowledge/` — operator browser (list + detail with
  Entries/Search tabs)
- `mcp/agent/app/api/agent/knowledge/` — thin proxies

## Backwards compatibility

All four proposals are **additive**:

- Bundles that don't set `vector_index` keep brute-force (today's
  default).
- Bundles that don't set per-KB `embedding` inherit the bundle-level
  model (today's default).
- Bundles with `kbWrites: []` (v1.2 default) don't expose Tier-3
  endpoints — back-compat exact.
- The UI routes are new; there's no existing convention to break.

The SQLite schema change for Proposal B (`embedding_model_id` column)
is the only breaking-ish detail; deploys with existing `kb.db` files
get a v1.3-marker migration that backfills the column with the
v1.2-era bundle-level model.
