# mitre-atlas — MITRE ATLAS (AI / ML security) knowledge base

[MITRE ATLAS](https://atlas.mitre.org) (Adversarial Threat Landscape for AI
Systems) is the ATT&CK-style framework for attacks on AI/ML systems — prompt
injection, model evasion, data poisoning, model theft, agent hijacking. Guardian
is itself an AI agent and customers increasingly run AI/LLM workloads, so ATLAS
is the canonical TTP language for investigating AI-targeting incidents.

Two doc categories:
- **`attack-technique`** (`AML.T####` / sub `AML.T####.###`) — description,
  tactics, mitigations, and the mapped ATT&CK Enterprise id when ATLAS declares
  one (cross-links into `mitre-attack-enterprise`).
- **`case-study`** (`AML.CS####`) — a real-world AI-incident report: summary, the
  step-by-step attack procedure (tactic → technique → what happened), target,
  actor, references. High-value grounded evidence.

Generated deterministically by [`../_tools/gen_atlas.py`](../_tools/gen_atlas.py)
from the official ATLAS data (never hand-edited); `framework_version` pins the
source. Embeddings are pre-computed and baked into the bundle (v0.2.17 keystone)
so the KB boots with zero Vertex calls.

## Regenerate / re-bake

```bash
cd bundles/spark/kbs/_tools
python gen_atlas.py --out ../mitre-atlas/entries
python kb_embed.py ../mitre-atlas --embedder vertex-rest --project <gcp-project>
```

## Attribution
See [`NOTICE.txt`](NOTICE.txt). ATLAS™ is a project of The MITRE Corporation;
Guardian is not endorsed or certified by MITRE.
