# soar-playbooks — Cortex XSOAR playbook knowledge base

The Cortex XSOAR out-of-the-box **playbooks** from the
[demisto/content](https://github.com/demisto/content) repo (MIT-licensed),
filtered to SOC-relevant pack categories (~800 playbooks across ~77 products).
The Guardian agent searches this to find response/automation playbooks and,
later, as worked examples for *building* playbooks.

## Shape (per the operator's design)

- **The embedded `content` is a reviewed DESCRIPTION** of what the playbook does
  — its own description + inputs/outputs + the integrations/scripts it calls +
  product/use-case context. Semantic search matches *intent*, not raw YAML.
- **The raw playbook YAML is KEPT** in the `raw_yaml` field (not embedded), so
  the agent can retrieve the actual playbook.
- **Dual-labeled**: AXIS A `product` / `pack` / `support_tier` (mechanical, from
  `pack_metadata`); AXIS B investigation-type / use-case tags (from the pack's
  `useCases` + `categories`). Both surface as `/knowledge` filter chips (v0.2.20).
- Docs are JSON entries; deprecated playbooks are skipped.

## Generate / re-bake

```bash
# 1. Sparse-clone the playbooks (blobless — only Playbooks + pack_metadata):
git clone --depth 1 --filter=blob:none --no-checkout https://github.com/demisto/content /tmp/content
cd /tmp/content && git sparse-checkout set --no-cone '/Packs/*/Playbooks/*' '/Packs/*/pack_metadata.json' && git checkout
# 2. Generate + bake:
cd bundles/spark/kbs/_tools
python gen_soar_playbooks.py --content /tmp/content --out ../soar-playbooks/entries
python kb_embed.py ../soar-playbooks --embedder vertex-rest --project <gcp-project>
```

## Future enhancement

The descriptions are assembled deterministically from each playbook's own
fields (faithful, no hallucination). An optional LLM-polish pass could rewrite
them into crisper prose — tracked as a follow-up; the deterministic baseline is
already strong for retrieval.

## Attribution
See [`NOTICE.txt`](NOTICE.txt). Content © Palo Alto Networks / Demisto under the
MIT License; only playbook YAML is bundled (no vendor binaries/logos).
