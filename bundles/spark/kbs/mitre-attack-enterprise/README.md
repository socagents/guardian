# mitre-attack-enterprise — MITRE ATT&CK (Enterprise / IT) knowledge base

The complete MITRE ATT&CK **Enterprise** matrix as a semantically-searchable
reference corpus — one doc per technique and sub-technique. The Guardian
incident-investigation agent searches it (`knowledge_search`) to ground its
analysis of Cortex XSIAM/XSOAR alerts, which carry ATT&CK technique ids.

- **Generated deterministically** from the official ATT&CK STIX bundle by
  [`../_tools/gen_mitre.py`](../_tools/gen_mitre.py) — never hand-edited, so it
  stays a faithful mirror and regenerates cleanly on each MITRE refresh (~2×/yr).
- Each doc carries the technique's **description**, **tactic(s)**, **platforms**,
  **detection** (v19 moved detection into linked Detection-Strategy → Analytic →
  data-component objects; the generator walks those), and **mitigations**.
- `id` = the ATT&CK id (`T1059`, `T1059.001`); `category` = `attack-technique`.

## How it differs from soc-investigation

`soc-investigation` is 30 **hand-written narrative** investigation guides + IR
playbooks ("how a good analyst thinks"). This KB is **exhaustive, terse
reference** — every one of the ~697 Enterprise techniques, machine-extracted.
Complementary: the agent reads `soc-investigation` for *how to investigate well*
and `mitre-attack-enterprise` for *what exactly is T1059.001 / its detection /
its mitigations*. The small technique-id overlap is intentional, not a dedup
target.

## Regenerating (on a MITRE release)

```bash
cd bundles/spark/kbs/_tools
python gen_mitre.py --domain enterprise --out ../mitre-attack-enterprise/entries
# then re-bake embeddings so installs stay fast (v0.2.17 keystone):
python kb_embed.py ../mitre-attack-enterprise --embedder vertex-rest --project <gcp-project>
```

`framework_version` in each doc's front-matter pins the source version.

## Embeddings

Embeddings are **pre-computed and baked into the docs** (`embedding` +
`embedding_model` front-matter, via `kb_embed.py`) so the ~697-doc KB boots with
**zero Vertex calls** — see the v0.2.17 keystone. A bake whose model doesn't
match the runtime embedder is ignored (the loader re-embeds), so a stale bake is
self-healing.

## Attribution

See [`NOTICE.txt`](NOTICE.txt). ATT&CK® is © The MITRE Corporation, reproduced
under the ATT&CK Terms of Use; Guardian is not endorsed or certified by MITRE.
