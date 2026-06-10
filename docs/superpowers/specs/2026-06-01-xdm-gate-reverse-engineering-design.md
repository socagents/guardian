# XDM Gate Reverse-Engineering — Design Spec

**Date:** 2026-06-01
**Status:** Design approved (operator), pending spec review → implementation plan
**Author:** Claude (Opus 4.8) with operator

---

## Goal

Make Phantom's simulated logs actually **populate the Cortex XSIAM data model (XDM)**, not just land in the raw dataset. Today, for several validated data sources, events land raw but **0 `xdm.*` fields populate** because our generated data does not carry the field/value the modeling rule **gates** on. Fix this by **reverse-engineering each data source's real parsing + modeling rules** and writing that understanding back into the source's own `data_source.yaml` (`how_to_use` + field list) — with **no static, hand-maintained mapping table**.

## Background — the proven root cause

End-to-end UI testing (2026-06-01) of five validated sources showed: raw landing ✅, XDM ❌ for AWS CloudTrail and Azure FlowLogs; partial XDM for Okta. Investigation (operator-corrected) established:

- XSIAM modeling rules begin with a `filter` that **gates** execution — they key on **a specific field = a specific value**. If the event lacks that field/value, the rule never runs and **nothing maps to XDM**, regardless of CEF-vs-JSON transport.
- Proven example — `AWSCloudTrail.xif`:
  ```
  [MODEL: dataset = amazon_aws_raw]
  filter _log_type = "Cloud Audit Log"
  ```
  Our `amazon_aws_raw` `data_source.yaml` sets `_log_type` example `"audit"` → gate never matches → 0 XDM. Exactly the observed result.
- This is **systemic**. Gate conditions extracted from the locally-cached modeling rules (`scripts/maintainer/modeling_rules/*.xif`) for the 22 validated sources:

  | Dataset | Gate | Pinnable from payload? |
  |---|---|---|
  | `amazon_aws_raw` | `_log_type = "Cloud Audit Log"` | meta field (`_`-prefixed) — collector/PR-assigned, **not** a raw payload key |
  | `msft_azure_flowlogs_raw` | `category in ("NetworkSecurityGroupFlowEvent"…)` | raw |
  | `msft_azure_ad_raw` / `_audit_raw` | `category in ("AuditLogs","SignInLogs"…)` | raw |
  | `msft_azure_waf_raw` | `Category = "FrontDoorAccessLog"` | raw |
  | `proofpoint_email_security_raw` | `event_type = "message"` | raw |
  | `qualys_qualys_raw` | `event_type in ("activity_log")` | raw |
  | `cyberark_isp_raw` | `is_auth = true` | **computed** (derived in-rule from raw fields) |
  | `okta_sso_raw` | `eventType in (…)` | raw (we set it → partial XDM) |
  | `servicenow_servicenow_raw` | `source_log_type = "syslog transactions"` | raw (gate met → mapped) |

  The two sources that map (Okta, ServiceNow) are precisely the two whose gate field we already populate. The pattern is airtight.

## Decisions (operator-approved)

1. **Scope:** the **22 validated** data sources (`tooling/validate/validated_data_sources.txt`).
2. **"Fixed" bar per source:** the modeling rule **gate fires** and **core `xdm.*` fields populate** (gate + direct top-level mappings). Deep nested-composite saturation (e.g. every `userIdentity.*` leaf) is a **follow-up**, not this arc.
3. **Source of truth:** **reverse-engineer each source's parsing rule(s) + modeling rule(s)** and write the understanding into that source's `data_source.yaml`. **No separate mapping file, no hardcoded literal** that didn't come from analyzing that source's rules.
4. **Coverage + enforcement:** **all 22** are covered, including computed-gate sources (trace the computed gate back to the raw field(s) that satisfy it). The validator **hard-fails** the build on drift, and it is **non-static** (re-derives the gate from the live rule at check time).

## Architecture — reverse-engineering only

There is no mapping artifact. The only persisted output is the enriched per-source `data_source.yaml`. It is produced by a genuine analytical pass over each source's own rules.

```
scripts/maintainer/parsing_rules/<Pack>__<Rule>.xif   ─┐
scripts/maintainer/modeling_rules/<Pack>__<Rule>.xif  ─┤  reverse-engineer (per source)
bundles/spark/.../<id>/data_source.yaml (current)     ─┘            │
                                                                   ▼
                              enriched <id>/data_source.yaml  (how_to_use + fields)
                                                                   │
                          xlog OverrideSender emits the values ────┤
                                                                   ▼
                          CEF/JSON → XSIAM → modeling rule FIRES → xdm.* populated
                                                                   │
                          validate_all.py re-derives gate from live .xif ── hard-fail on drift
```

## Components

### A. The reverse-engineering unit (one per source) — the heart of the work
**Input:** the source's parsing rule(s) (`parsing_rules/`) + modeling rule(s) (`modeling_rules/`) + its current `data_source.yaml`.
**Analysis (genuine, not regex):**
- Identify the **gate** condition (the `filter … = "…"` / `in (…)`), and classify it:
  - **raw-field gate** → the field is carried in the event; record the required value.
  - **computed-field gate** (e.g. `is_auth = true`) → read the rule's `alter <field> = <expr>` chain, resolve which **raw** field(s)+value(s) make the expression true, and target those.
  - **meta-field gate** (`_`-prefixed, e.g. `_log_type`) → collector/PR-assigned, **not** set from the payload; document the onboarding/PR requirement in `how_to_use` rather than pretending a payload field will set it.
- Identify which **raw fields** the parsing rule extracts and the modeling rule reads into XDM, and **how each must be valued/shaped** (enum members, JSON-object composites, IP/port formats, etc.).

**Output (written back into the source's `data_source.yaml`):**
- **`how_to_use`** — specific instructions: which fields to populate, with what values, to (1) clear the gate and (2) drive core XDM. Calls out meta-field/onboarding caveats explicitly.
- **field list** — accurate `description` + `example` per rule-relevant field (gate field example = the rule's required value/one-of; composites noted as JSON objects).

This pass is **subagent-driven, one source at a time**, so the analysis is faithful to each source's real rules.

### B. Generation faithfulness (xlog `OverrideSender`) — confirm in R1
For the enriched examples to actually fire the gate, the generator must **emit the reverse-engineered field value** (the gate field's example) rather than faker-overriding it. R1 confirms how `OverrideSender`/`generate_records_with_override` treats a field that carries an explicit `example`, and makes the minimal change so rule-critical fields emit their derived value while non-gate fields keep faker variety. The value still originates from the per-source analysis — not a constant injected in code.

### C. Validator (`tooling/validate/validate_all.py`) — non-static
`check_gate_fields_satisfied()`: for each validated source, **parse its live `.xif` at check time** to recover the gate, then assert the source's `data_source.yaml` satisfies it (gate field example matches / `how_to_use` documents the meta-field caveat). The expected value is **read from the rule**, never hardcoded in the validator. Hard-fails the build on drift, so XDM coverage can't silently rot.

## Data flow (one source, happy path)
1. Maintainer/subagent reverse-engineers `<id>` → enriched `data_source.yaml` committed.
2. Agent simulates `<id>` (stream_simulate_to_xsiam) → reads schema + `how_to_use` → worker emits events carrying the gate value.
3. XSIAM parsing rule routes to the dataset; modeling rule's `filter` matches → `alter xdm.*` runs → XDM populated.
4. Agent's `datamodel dataset=<ds>` query shows core `xdm.*` non-null.
5. CI `validate_all.py` re-derives the gate from the live rule + confirms the YAML still satisfies it.

## Testing / acceptance
- **Per source:** agent E2E (today's prompt shape): generate (max coverage) → `xsiam_get_datasets` → raw XQL → **`datamodel` XQL shows core `xdm.*` populated** → stop worker → confirm none running.
- **Proof set:** the five tested today (Okta, AWS CloudTrail, Azure FlowLogs, Proofpoint, Qualys). CloudTrail (meta-gate) is the hardest and the clearest before/after.
- **Unit:** `OverrideSender` emits a field's explicit example verbatim (R1); validator positive/negative (gate satisfied vs drifted).

## Release decomposition (drives the plan)
- **R1 — mechanism + proof set.** Confirm/repair generation faithfulness; reverse-engineer + enrich the 5 proof-set sources; prove XDM now fires E2E on the deployed install.
- **R2 — full coverage.** Reverse-engineer + enrich the remaining 17 (all 22, incl. computed gates).
- **R3 — enforcement + docs.** Non-static validator hard-fail; `how_to_use` documented as the generation contract (architecture/user pages); re-test all 22; arc closure.

## Out of scope (this arc)
- Deep nested-composite XDM saturation (every `userIdentity.*` / `requestParameters.*` leaf) — follow-up after the gate-fires baseline.
- The non-validated bundled packs (~175) — a later expansion once the 22 pattern is proven.
- Changing XSIAM tenant content/modeling rules — those are tenant-managed; we only change what Phantom generates + documents.

## Risks / open questions
- **Meta-field gates (`_log_type`):** if the broker/PR assigns `_log_type` per routed dataset, CloudTrail's fix is broker-config + a `how_to_use` note, not a payload field. R1's reverse-engineering of CloudTrail's parsing rule resolves this concretely.
- **Generator example-vs-faker:** if `OverrideSender` ignores examples, B is a real (small) code change; confirmed first thing in R1.
- **`in (…)` gates:** pick a representative allowed value; document the full set in `how_to_use`.
