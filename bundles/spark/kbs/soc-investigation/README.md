# soc-investigation — SOC Investigation Knowledge Base

A curated, semantically-searchable **reference corpus** the Guardian
incident-investigation agent queries (`knowledge_search`) to *ground* its
analysis of Cortex XSOAR incidents. Two document categories:

- **`attack-technique`** — MITRE ATT&CK technique investigation guides
  (`id` = the ATT&CK id, e.g. `T1071.004`): how the technique manifests in
  telemetry, the investigation steps to confirm/refute it, the data sources to
  query, and pivot/related techniques.
- **`playbook`** — IR playbooks (`id` = `pb-<slug>`, e.g. `pb-ransomware`):
  when to use, triage, blast-radius scoping, containment, evidence to collect,
  and TRUE/FALSE-POSITIVE verdict criteria.

## How it differs from memory
**Knowledge** is curated reference material, shipped in the image and loaded at
boot (read-only at the agent surface). **Memory** is the agent's accumulated,
mutable, org-specific facts (crown-jewel hosts, prior incidents, validated
detections) written as it works. The agent *reads* knowledge to ground its
reasoning; it *writes* memory to remember this environment.

## Mechanics
Each `entries/*.md` is markdown + YAML frontmatter (`id`, `title`, `category`,
`tags`). At MCP boot, `kb_loader` parses every entry, embeds the content via the
Vertex `text-embedding-004` model (768-dim) — the same embedder memory uses —
and stores it in `kb.db`. `knowledge_search` embeds the query and returns the
nearest docs by cosine similarity. Declared in
`bundles/spark/manifest.yaml:knowledge.bundled[]`.

To add/update a doc: edit/add a file under `entries/`, rebuild the agent image;
the loader hash-detects changes and re-embeds only what changed.
