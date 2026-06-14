# Knowledge-Base Expansion — Design Spec

**Date:** 2026-06-14
**Status:** Approved (operator answered the 4 scope questions; arc greenlit)
**Foundation:** v0.2.16 (the `soc-investigation` KB) — shipped + released.

## Goal

Grow Guardian's knowledge layer from one hand-curated KB into a family of
ecosystem-scoped reference KBs (full MITRE ATT&CK across IT/OT/Mobile + MITRE
ATLAS for AI) **plus** a curated, dual-labeled SOAR-playbooks KB sourced from
`demisto/content`. Each ships as its own contained release.

## Operator intent (normalized from voice)

- KEEP `soc-investigation`, but EXPAND MITRE coverage to the *entire* framework.
- MITRE is a FAMILY → **separate KBs per ecosystem** (IT=Enterprise, OT=ICS,
  AI=ATLAS, Mobile), NOT one KB with labels.
- Add a SEPARATE **SOAR-playbooks KB** from `github.com/demisto/content`: pull
  every playbook+pack, **review each and write a semantic description that we
  EMBED** (search matches the description, not raw YAML), **KEEP the raw YAML**
  in the KB, and **DUAL-LABEL**: (1) product/pack origin, (2) investigation-type
  / attack-type / use-case. Future payoff: the agent uses these as worked
  examples when it learns to *build* playbooks.

## Operator decisions (this session)

1. **Tag v0.2.16 now** as the foundation — DONE (released).
2. **Approve the phased arc, keystone first** — v0.2.17 (pre-computed
   embeddings) ships before any large KB.
3. **Build ICS + Mobile**, ship **disabled/customer-gated**.
4. **SOAR playbooks: SOC-relevant categories**, LLM-assisted review + human
   spot-check (~600–1,200 playbooks, not the full ~1–3k long tail).

## Research findings (workflow `kb-expansion-research`)

### MITRE framework family (STIX v18.0, 2025-10-28)
| KB | Ecosystem | Docs (tech+sub) | Source | Notes |
|---|---|---|---|---|
| `mitre-attack-enterprise` | IT | ~691 (216+475) | `mitre-attack/attack-stix-data` → `enterprise-attack.json` | Flagship. **v18 deprecated `x_mitre_detection` + Data Sources** → pull detection from Detection-Strategy/Analytic objects + Data Components; `x_mitre_detection` fallback for old bundles. |
| `mitre-atlas` | AI | ~182 (84+56 + 42 case studies) | `mitre-atlas/atlas-data` → `dist/ATLAS-latest.yaml` | The "AI" framework. 42 case studies = high-value narrative docs. Inherits 13 ATT&CK tactics + AI-specific ones. |
| `mitre-attack-ics` | OT | ~97 (83+14) | `attack-stix-data` → `ics-attack.json` | Uses `x-mitre-asset` (PLC/HMI/RTU) not platforms. Optional/gated. |
| `mitre-attack-mobile` | Mobile | ~124 (77+47) | `attack-stix-data` → `mobile-attack.json` | Android/iOS. Optional/gated. |

- Generation: `pip install mitreattack-python`; `MitreAttackData(<bundle>.json)`;
  per technique pull id/name/description/tactics(kill_chain_phases)/platforms/
  data-components/detection-strategies/mitigations. Pin `framework_version`
  per doc for reproducible regen. ATT&CK refreshes ~2×/yr (Apr/Oct).
- Licensing: ATT&CK redistributable commercially **with attribution** (ATT&CK
  Terms of Use + version cite, no implied MITRE endorsement, respect
  trademark). ATLAS "Distribution Unlimited" with copyright preserved.
- D3FEND / CAPEC / ENGAGE: out of scope for the first wave.

### Cortex XSOAR content repo (`demisto/content`)
- **MIT-licensed** → may redistribute playbook YAML with the MIT notice +
  attribution to `demisto/content` (Palo Alto). Exclude vendor logo binaries
  (trademarks not MIT); we only bundle YAML so risk is low.
- Scale: ~1,300 packs, ~1–3k playbooks. Structure `Packs/<Pack>/Playbooks/
  playbook-*.yml` + `pack_metadata.json`.
- Product/vendor = `pack_metadata.author` (fallback pack name/keywords);
  `Common*` packs = Generic/multi-vendor.
- Label seeds: pack `categories` / `useCases` / `tags` / `support` tier. But
  per-playbook investigation/use-case needs the semantic review pass (pack
  useCases is pack-level). ATT&CK is NOT structured in playbook YAML → any
  `attack_type` label is INFERRED (flag it).

### Guardian KB infra (scaling)
- **Multi-KB is fully supported end-to-end today** (loader, store, REST, UI) —
  adding a `knowledge.bundled[]` entry "just works".
- Search = brute-force cosine (`kb_store.py` search). Comfortable to "low
  thousands"; noticeable at 10–50k. Total arc corpus ≈ 2.6–3.9k → fine **scoped
  by `kb_name`** (default); reserve cross-KB search for explicit action.
- **Boot embedding is the blocker:** loader embeds each doc synchronously,
  one Vertex HTTP call (~200ms) each, no batch API. ~691 docs alone = minutes;
  ~5k = **16+ min first boot + a Vertex bill on every fresh-volume install**.
  Hash-detect skips unchanged on reboot, but first boot still pays.
- JSON docs already support a `content` (embedded) + arbitrary metadata fields
  (e.g. `raw_yaml`) via `additionalProperties:true` — **exactly the playbook
  shape** (embed reviewed description, keep YAML in metadata).
- Only `category` is indexed/filterable today. Arbitrary label filtering (the
  playbook dual-labels) needs a `kb_doc_tags` table + UI chips.

## Architecture decisions

- **`soc-investigation` stays as-is** — hand-written *narrative* ("how a good
  analyst thinks"); the new MITRE KBs are auto-generated *reference* ("what
  exactly is T1059.001"). Complementary; the small technique-id overlap is
  intentional, NOT a dedup target. Do not dissolve its guides into Enterprise.
- **KB naming:** `mitre-attack-enterprise`, `mitre-atlas`, `mitre-attack-ics`,
  `mitre-attack-mobile`, `soar-playbooks` — clean `/knowledge` card grid.
- **Pre-compute embeddings, ship them in the bundle** (the keystone). Add an
  optional pre-computed embedding field to the doc schema; loader unpacks it
  instead of calling Vertex. Pin `embeddingModel=text-embedding-004`/768-dim and
  validate on load (guard against model drift).
- **Dual-label taxonomy (playbooks):** AXIS A product/pack-origin (mechanical,
  from `pack_metadata`), AXIS B investigation_type/use_case/attack_type
  (semantic, per-playbook; attack_type flagged inferred). Labels ride in
  front-matter now; become UI-filterable once `kb_doc_tags` lands (v0.2.20).

## Release decomposition (one concept = one release)

| Release | Scope | Depends on |
|---|---|---|
| **v0.2.17** | **Keystone:** pre-computed-embedding support in schema + loader (skip boot Vertex calls when present); MITRE + MIT attribution/NOTICES surface. No new corpus. | — |
| **v0.2.18** | `mitre-attack-enterprise` KB (~691 docs) via STIX generator, embeddings baked in, schema, `/knowledge` card, docs. Flagship. | v0.2.17 |
| **v0.2.19** | `mitre-atlas` KB (~182: techniques + 42 case studies). | v0.2.17 |
| **v0.2.20** | KB label-filter substrate: `kb_doc_tags` table + index, list/search accept `tags[]`, UI filter chips, search pagination. Re-index shipped MITRE labels. | v0.2.18 |
| **v0.2.21** | `soar-playbooks` KB (SOC categories, ~600–1,200): reviewed descriptions embedded, raw YAML in metadata, dual-labels, MIT attribution. | v0.2.17, v0.2.20 |
| **v0.2.22** | `mitre-attack-ics` (~97), shipped DISABLED / OT-gated. | v0.2.17 |
| **v0.2.23** | `mitre-attack-mobile` (~124), shipped DISABLED / mobile-gated. | v0.2.17 |

## Risks

- **Boot-embedding cost** — BLOCKS the arc; v0.2.17 must land first.
- **Regeneration drift** — generator must read v18 Detection-Strategy/Analytic
  objects (not the deprecated `x_mitre_detection`); pin `framework_version`.
- **Search scaling** — fine scoped-by-KB now; land FTS5-hybrid or pgvector
  before the corpus passes ~10k (only if the full playbook long tail is ever
  imported). Note in architecture-page Implementation gap.
- **Playbook label quality** — `attack_type` inferred; pack useCases are
  pack-level. Per-playbook review + spot-check; flag inferred labels.
- **Licensing** — bundle exact ATT&CK ToU + ATLAS copyright + MIT notice in
  v0.2.17 NOTICES before any corpus ships. Missing attribution = compliance
  defect.
- **Contained-release pressure** — resist collapsing v0.2.18–v0.2.21 into one
  tag.

## Keystone (v0.2.17) — implementation sketch

1. Doc schema: optional `embedding` (base64 float32[768]) + `embedding_model`
   fields, both in markdown front-matter and JSON docs.
2. `kb_loader`: when a doc carries a valid pre-computed embedding whose
   `embedding_model` matches the runtime embedder's model/dims, decode + upsert
   it directly, skipping the synchronous `embedder.embed()` Vertex call. On
   mismatch/absent → fall back to embed-on-boot (current behavior).
3. A repo build tool (`scripts/kb_embed.py` or similar) that, given a KB dir,
   embeds each doc via the SAME Vertex model and writes the embeddings back into
   the docs — run at authoring time, committed to the bundle.
4. NOTICES/attribution surface (About/credits + per-KB footer) — generic, used
   by every later KB.
5. Tests: loader uses pre-computed embedding when present + matching; falls
   back when absent or model-mismatched; never calls Vertex when all docs carry
   valid embeddings.
6. No new corpus — `soc-investigation` can optionally gain baked-in embeddings
   to prove the path (its 30 docs are the test fixture).
