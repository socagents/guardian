---
name: data-source-xdm-validation
description: >
  Reverse-engineer, create, update, and validate a Phantom data source against
  Cortex XSIAM — making a vendor's synthetic CEF logs route into their XSIAM
  dataset, clear the modeling-rule gate, and map a rich set of `xdm.*` fields.
  Use this WHENEVER you are: onboarding a new data source; debugging "why doesn't
  this map to XDM / why is xdm=0"; a source lands raw but maps few/zero fields;
  seeding a modeling-rule gate; shaping JSON composites for nested-JSON rules;
  pulling demisto/content modeling rules; promoting a source to `validated`; or
  reconciling a data_source.yaml schema against its parsing/modeling rules. The
  work is COGNITIVE — every source differs — but the end-to-end loop, the
  failure-mode decision tree, and the supporting scripts are captured here.
  Reach for this skill even when the user just says "validate <vendor>",
  "make <vendor> map to XDM", or "this dataset isn't modeling."
paths:
  - bundles/spark/data-sources/**
  - scripts/maintainer/modeling_rules/**
  - scripts/maintainer/parsing_rules/**
  - tooling/validate/validated_data_sources.txt
  - xlog/app/dynamic_schema.py
  - xlog/app/override_sender.py
---

# Data-source XDM validation & reverse-engineering

This skill is the distilled memory of validating ~36 data sources end-to-end
against a live XSIAM tenant. **It is a thinking harness, not a script to run.**
Each vendor's parsing + modeling rules are different; your job is to read the
rule, understand what it expects, shape the synthetic event to match, and prove
the mapping on the tenant. The steps below are the spine; the judgment is yours.

## Delivery doctrine — syslog/CEF ONLY (the load-bearing rule; read FIRST)

**Phantom delivers every synthetic log over syslog/CEF to the Cortex Broker. We NEVER
use an HTTP collector or an API integration to deliver logs — full stop.** This holds
*even when the real-world vendor is collected that way in production* (CrowdStrike FDR
pulling gzipped JSON from S3, Snowflake/Wiz/Rapid7/PingOne API pollers, an HTTP event
collector, etc.).

**Why this is sound, not a workaround:** the broker, parsing rules, and modeling rules
are **protocol-agnostic**. They do not care *how* an event arrived — they map on the
**data shape**: the field/column/JSON structure of the event. A modeling rule reading
`json_extract_scalar(evt, "$.a.b")` maps our event whether it arrived over an API or over
syslog, *as long as the event carries `a.b` in the expected shape*. The collection
mechanism is invisible to the rule.

**Therefore the whole job is reverse-engineering, not transport.** Read the vendor's
**parsing + modeling rules**, derive the exact data shape they expect (column names, JSON
paths, value types, the gate), and encode it into `data_source.yaml` `fields[]` (names,
types, descriptions, examples) + `how_to_use`. The phantom agent then crafts synthetic
events of that shape and ships them over syslog/CEF; the parsing rule extracts the
columns, the modeling rule maps them, `xdm.*` populates → validated.

**Consequences that correct the most common mistakes:**
- A vendor being "native-collector-only" or "API-integration" in real XSIAM is **irrelevant**
  to whether we can validate it. **Never** dismiss a source as un-validatable because its
  production collection is HTTP/API/FDR. Reverse-engineer the rule and replicate the *shape*
  over CEF.
- `raw > 0, xdm = 0` is **not** "this source can't map." It means **no modeling rule is bound
  to the dataset** — the rule isn't installed or doesn't exist yet. The fix is to obtain +
  reverse-engineer the rule (install the content pack so it binds, or export the tenant's
  rule), not to give up. (PingFederate, 2026-06-08: synthetic CEF landed `raw=45229` but
  `xdm=0` purely because the tenant had no PingFederate modeling rule bound.)
- The `how_to_use` documents the **data shape + the syslog/CEF routing literal** — NOT the
  vendor's real-world collection plumbing. Describing "FDR S3/SQS" or "API poller" as the
  *delivery mechanism* misleads the agent into thinking it needs an HTTP collector; it never
  does. State the field shape and that Phantom ships it as CEF.
- JSON-native rules are mapped by emitting the JSON as a **CEF composite extension**
  (dotted-leaf fields → nested JSON string on the wire — §4). No HTTP collector, ever.

## What counts as a data source (the admission rule — check BEFORE onboarding a vendor)

A Phantom data source MUST correspond to a real Cortex XSIAM **log-ingestion + parsing path**:
the vendor has a **parsing rule and/or modeling rule** — shipped in a content pack OR built-in
to the platform (e.g. PingFederate's native authentication parser + `ping_identity_pingfederate_raw`
dataset) — so its logs land in a dataset and get *structured*.

**A vendor whose only Cortex presence is an XSOAR/Marketplace integration with no Parsing/Modeling
rules is NOT a data source — it's an action integration** (it fetches alerts/incidents or runs
response actions via API; it never ingests + parses logs into a dataset). Do not onboard it. SIEMs
that are log *destinations* (IBM QRadar, Rapid7 InsightIDR) are likewise not sources.

**Quick admission triage (quota-free), run BEFORE any simulate cycle:**
1. `GET https://api.github.com/repos/demisto/content/contents/Packs/<Pack>/ParsingRules` and `…/ModelingRules`
   (200 = the pack ships rules → candidate data source; 404 on BOTH = no rules in the snapshot).
2. Inspect the pack contents: only `Integrations/`+`Playbooks/`+`Classifiers/` (no `ParsingRules`/
   `ModelingRules`/`Datasets`) ⇒ **XSOAR automation pack = action integration, not a data source.**
3. If demisto/content has nothing, check the Cortex docs for a NATIVE/built-in ingestion path
   ("Ingest <vendor> …" data-source page naming a dataset). Native parsers count (PingFederate).
4. No rule in a pack AND no native ingestion+parsing path ⇒ **not a data source. Do not add it.**

(v0.17.144: 12 newly-added vendors failed this test — CrowdStrike, Sophos ×2, PingOne, Wiz,
Rapid7 ×2, SAP, ESET, Snowflake, Veeam, QRadar — and were removed; only PingFederate, which has a
native parser + matching dataset, was kept. They *land raw* over CEF but have no rule to map them,
so they can never green-pill and aren't useful as structured SOC-simulation sources.)

Two reference files carry the deep detail — read them when you hit the
corresponding work:

- **[references/diagnostic-playbook.md](references/diagnostic-playbook.md)** — the
  full `xdm=0 / low-field` decision tree, the gate taxonomy, JSON-composite
  mechanics, and the reverse-engineering deep-dive. **Read this the moment a
  source doesn't map as expected.**
- **[references/tooling.md](references/tooling.md)** — every script, MCP tool,
  exact invocation, the GitHub rule-pull command, and file paths. **Read this
  when you need to run something.**

---

## The mental model (internalize this first)

A synthetic event has to survive **two independent layers**. Diagnose them
separately — conflating them is the #1 time-sink.

```
  phantom worker → CEF/syslog over UDP → XSIAM Broker
        │                                     │
        │  LAYER 1: ROUTING + LANDING         │  raw rows appear in <dataset>_raw ?
        │  (vendor/product header → dataset)  │  → `dataset = X | comp count()`
        ▼                                     ▼
  Broker INGEST/parsing rule extracts columns  ──→ LAYER 2: MODELING (XDM)
        │                                     │  do xdm.* fields populate ?
        │  modeling rule reads columns →      │  → `datamodel dataset = X | fields xdm.*`
        ▼  xdm.* / XDM.Endpoint.*             ▼
```

Three load-bearing truths, each learned the hard way:

1. **Routing is by the CEF *header*, not the extensions.** The broker derives the
   target dataset from `<lower-vendor>_<lower-product>_raw` (or matches an explicit
   `[INGEST: vendor="X", product="Y"]` rule). The display `vendor`/`product` in the
   YAML are **not** the routing literals — derive them from the dataset name and
   verify (the "SentinelOne trap"). Casing can matter (`Cisco`/`Firepower`, not
   `cisco`/`firepower`).

2. **A modeling rule only binds to a dataset that is XDM-enabled — which means its
   content pack is installed in XSIAM.** A broker-**auto-created** dataset (unknown
   vendor/product, no INGEST rule) is raw-only: `datamodel dataset=X` returns
   **0 rows** no matter how perfect the event, because no rule is associated.
   **This is the single biggest blocker.** The fix is operator-side: install the
   vendor's content pack → it binds the modeling + parsing rules to the dataset.
   *(Symptom: raw rows present, columns extracted, `datamodel`=0.)*

3. **Modern cloud/SaaS rules are JSON-native.** They read **nested JSON** via
   `json_extract_scalar(properties, "$.extendedProperties.user name")` and
   `protoPayload -> methodName`. CEF-over-syslog still works — the worker emits
   composite fields as **JSON strings** on the wire, which the rule parses — but
   the `data_source.yaml` schema must carry **dotted-leaf fields**
   (`properties.alertDisplayName`, `properties.extendedProperties.user name`) so
   the generator synthesizes the nested object. No HTTP collector is needed.

---

## The end-to-end loop (the proven method)

Run this against the deployed install via the IAP tunnel + bearer (see
tooling.md for the exact tunnel + `agent_chat_e2e.py` invocation). The loop is
also encoded as the `stream_simulate_to_xsiam` MCP skill — this skill is the
*authoring/debugging* companion to that *runtime* skill.

1. **Pre-req: is the pack installed?** If you don't know, assume not. If
   `datamodel dataset=X` returns 0 while raw>0, the pack isn't bound — ask the
   operator to install the vendor's content pack in XSIAM. **Don't burn cycles
   tuning the event until the dataset is XDM-enabled.**

2. **Pull the rules.** `python3 scripts/fetch_demisto_modeling_rules.py` mirrors
   the `.xif` modeling + parsing rules from `demisto/content` into
   `scripts/maintainer/modeling_rules/` and `…/parsing_rules/`. These are your
   ground truth for what the rule reads. *(Caveat: the snapshot can lag the
   operator's **installed** rule version — if everything looks right but xdm=0,
   suspect a snapshot-vs-installed mismatch and ask the operator to export the
   tenant's actual rule.)*

3. **Reverse-engineer the gate.** `python3 scripts/maintainer/reverse_engineer_gate.py <ds_id>`
   classifies the modeling-rule gate: `unconditional` (maps regardless), `raw`
   (filter on a literal value set — **must seed**), `function` (coalesce-derived —
   seed the raw inputs), `computed` (regex/json-derived, e.g. GCP `logName` — seed a
   realistic value), `meta` (`_`-prefixed, ingestion-stamped — not seedable). See
   the gate taxonomy in the playbook.

4. **Derive the routing literal — read the INGEST/parsing rule FIRST.** If the pack
   has a parsing rule, it *hands* you the literal verbatim:
   `[INGEST: vendor="prisma", product="cloud_compute", target_dataset="prisma_cloud_compute_raw", no_hit=keep]`
   — also telling you the `_time` parse and `no_hit` behavior. Only if there's **no**
   INGEST rule do you fall back to deriving from the dataset name (`aws_guardduty_raw`
   → `AWS`/`GuardDuty`; broker lowercases, multi-word → underscores). **Beware
   non-derivable dataset names**: `imperva_inc__securesphere_raw` does NOT split to a
   clean literal — its routing comes from the vendor's **canonical CEF header**
   (`Imperva Inc.`/`SecureSphere`, which the broker normalizes to that dataset). When
   in doubt, look up the vendor's standard CEF header and **verify empirically which
   dataset the events land in** (and that `unknown_unknown_raw` didn't grow).

4b. **Pre-flight: diff the schema field names against the MR's source columns.** This
   one deterministic check catches the most common low-mapping cause *before* you
   spend a simulate cycle. **For CEF sources the schema field names MUST be the CEF
   wire keys the MR reads** — `cs1`–`cs6`, `cn1`–`cn3`, `src`, `dst`, `spt`, `dpt`,
   `act`, `app`, `duser`, `suser`, `cat`, `request`, `cefDeviceEventClassId`,
   `cefSeverity`, … — **NOT** the vendor's human-readable names. The broker extracts
   each CEF extension into a column named by its key, and the schema field name *is*
   that key. An auto-extracted schema with logical names (Imperva shipped
   `alertSeverity`/`destinationIP`/`httpMethod`) maps **zero**. Run the column-diff
   one-liner in the playbook (§3) — if the overlap with the MR's reads is poor, rebuild
   the schema fields to the MR's actual column names before simulating.

   **Run the diff on the SERVED schema, not the on-disk YAML.** The worker streams
   whatever `data_sources_get_schema` returns, which (Gap #8) can lag the bundled file.
   After any bundled-schema edit, confirm `get_schema` actually returns your new fields
   **before** streaming — and after streaming, confirm by querying the landed raw
   columns (`dataset = X | sort desc _time | fields <new_key>, <old_key> | limit 1`):
   if the OLD column names landed (Imperva streamed `action`/`alertSeverity` even after
   the bundle was fixed to `cs1`/`src`), the served schema is stale and the edit is
   inert until the store refreshes. **Looking at the landed raw columns is the
   ground-truth check — never trust the bundled YAML alone.**

5. **Shape the schema.** For flat rules, the bundled `data_source.yaml` fields
   usually match. For JSON-native rules, ensure the composite (`type: json`) field
   has **dotted-leaf children matching the rule's `json_extract` paths**
   (`scripts/maintainer/complete_composite_leaves.py` derives them from the `.xif`).

6. **Simulate.** `phantom_create_data_worker(type="CEF", destination="udp:10.10.0.8:514",
   vendor=…, product=…, count=400, schema_override=<FULL compact fields[]>,
   observables_dict={<gate_field>:[<value>]})`. **`observables_dict` values are
   LISTS** (scalar fails pydantic). Use `data_sources_get_schema(…, compact=true)` —
   it's lossless for the override and fits the agent's tool-result cap.

7. **Verify over a WIDE window AND across MANY rows.** Two independent traps:
   - **Wide window:** synthetic `_time` can land days in the past, so a 24h window
     reads zero on a clean mapping. Use ≥7 days, even 30.
   - **Many rows:** count distinct non-null `xdm.*` **across ≥20 rows**, never the
     newest single row (or even newest-5). Synthetic events are sparse and varied —
     any one row populates only a handful of fields, so a single-row count badly
     **undercounts** (Prisma Cloud Compute read `6` from the newest row but `29`
     across 20 rows — nearly its whole rule). Take the UNION across rows:
     `config timeframe = 30d | datamodel dataset = X | sort desc _time | fields xdm.* | limit 20`
     → count distinct field paths non-null in *any* of those rows.
   `datamodel` applies the rule at *query time*, so re-querying after a wait is valid.

8. **If it didn't map → go to the decision tree** (playbook). Do **not** guess —
   walk the layers in order.

9. **Promote to validated** only after a real field count on the tenant:
   set `validated: true` in the YAML, add the id to
   `tooling/validate/validated_data_sources.txt`, write a validated `how_to_use`,
   and run the validator (`check_validated_data_sources_manifest` +
   `check_gate_fields_satisfied` must pass). For gated sources the YAML's gate-field
   `example` must be a value the rule accepts, or the gate-check fails.

---

## The diagnostic decision tree (when xdm is 0 or low)

This is the scriptable spine of an otherwise-cognitive task. Walk it **in order** —
each step is one XQL query. Full version with the exact queries + fixes is in the
playbook; the summary:

| Observation | Layer | Likely cause → fix |
|---|---|---|
| `raw = 0` | 1 | Routing. Wrong vendor/product literal, OR tenant `[INGEST … no_hit=drop]` discards syslog. → fix literal / confirm an INGEST rule keeps it. **Check a wide window first — old `_time` reads 0.** |
| `raw > 0`, columns sit in `cefRawExtension` (not extracted) | 1.5 | The tenant INGEST/parsing rule is JSON-shaped (overrides generic CEF extraction) and your CEF event didn't "hit" its parse. → **NOT a dead-end** (doctrine: never fall back to an HTTP collector). Reverse-engineer the parsing rule and shape the CEF event so it hits — usually emit the JSON body the rule expects as a composite extension. If the tenant rule is `no_hit=drop` JSON-only, the operator widens the broker config to keep CEF; still syslog/CEF, never API/HTTP. |
| `raw > 0`, columns extracted, `datamodel = 0` | 2 | **Modeling rule not bound** — pack not installed. → operator installs the content pack. |
| `datamodel > 0` rows but `xdm.* = 0` populated | 2 | Gate not matched, OR the rule reads columns/paths your event doesn't produce. → seed the gate; check MR source columns vs schema field names; for JSON, check composite dotted-leaves vs `json_extract` paths. |
| Maps *some* `xdm.*` but fewer than the rule defines | 2 | Composite shape / column-name / value-type mismatch (e.g. `to_number(json_extract…)` needs a numeric leaf). → align the schema to the rule. |
| `datamodel` rows but `fields xdm.*` all null **and** rule says `model="Endpoint"` | 2 | Source maps to the **Endpoint preset** (`XDM.Endpoint.*`), not unified `xdm.*`. Query that namespace; note it may not be standard-XQL-enumerable. |

**Hypotheses that look right but are usually NOT the cause** (each was disproven on
real sources — don't waste time here without evidence): MTU truncation (UDP
fragments + reassembles; 2.5 KB events map fine), CEF space-mangling (the broker
reads an extension value until the next ` key=`, so JSON with spaces survives),
`compact=true` dropping fields (it's lossless), the generator emitting `{}` (it
builds nested JSON correctly when the leaves exist), materialization timing (counts
are stable within minutes). Confirm any of these with a query before believing them.

---

## Lessons & gotchas (the cognitive tips)

These don't fit a flowchart but will save you hours. The runtime skill
`stream_simulate_to_xsiam` encodes L1–L24 from earlier smokes; these are the
high-leverage ones plus what the cloud campaign added.

- **Seed the gate or XDM stays 0** even when raw lands. The #1 layer-2 blocker.
- **`observables_dict` values are LISTS**: `{"category":["AZFWApplicationRule"]}`.
- **Wide verify window (≥7d).** The single most common false negative.
- **Verify freshness from the data** (`sort desc _time`), don't filter on
  `xdm.event.type != null` — firewall/endpoint rules lead with other fields.
- **Routing literal ≠ display vendor/product.** Reverse it from the dataset name.
- **Install-first.** A source can be perfect and still read `datamodel=0` purely
  because its pack isn't installed. Establish XDM-binding before tuning.
- **JSON-native ≠ unmappable over CEF.** Shape dotted-leaf composites; the worker
  JSON-stringifies them onto the wire and the rule parses them.
- **Endpoint-preset sources** (`model="Endpoint"`) bind + count rows but aren't
  enumerable via `datamodel | fields xdm.*` — a known verification gap.
- **Worker-ID collisions:** IDs are timestamp-second-granular; create workers ≥3–4s
  apart, or one clobbers another.
- **Snapshot vs installed rule drift:** the committed `.xif` can differ from the
  operator's installed pack. When the analysis is airtight but it won't map, ask
  for the tenant's actual rule text.
- **Background-shell PATH:** long-running/`run_in_background` bashes can run under a
  stripped PATH (`sleep`/`head` "command not found"); use absolute `/bin/sleep` and
  avoid array/loop constructs, or run foreground.
- **Two failure FAMILIES per fix:** when you fix one source, grep sibling sources
  for the same pattern (e.g. empty `{}` composites, scalar observables) — the bug
  is usually copy-pasted across the bundle.

Added from the Prisma Cloud Compute + Imperva WAF test (2026-06-04):

- **CEF-source field names ARE the CEF wire keys** (`cs1`–`cs6`, `cn1`–`cn3`, `src`,
  `dst`, `spt`, `dpt`, `act`, `duser`, `cat`, …), never the vendor's logical names.
  Imperva shipped a logical-name schema (`alertSeverity`, `destinationIP`) → **0/16**
  mapped. Always run the pre-flight column diff (step 4b / playbook §3).
- **Read the parsing/INGEST rule first** — when present it hands you the routing
  literal, the `_time` parse, and `no_hit`, so you never guess. Prisma's
  `[INGEST: vendor="prisma", product="cloud_compute", … no_hit=keep]` gave it all.
- **Non-derivable dataset names** (double-underscore / vendor-specific, e.g.
  `imperva_inc__securesphere_raw`) → use the vendor's canonical CEF header
  (`Imperva Inc.`/`SecureSphere`) and verify empirically which dataset lands.
- **Bracket-notation JSON paths** `$['baseimage.name']` (keys containing a literal
  dot) cannot be expressed by the dotted-leaf convention — see playbook §4.
- **This skill is path-scoped** (`paths:` frontmatter → auto-activates when you edit
  `bundles/spark/data-sources/**`, the rules, or the generator/sender). It is NOT
  invoked by name via the Skill tool — follow it directly when it surfaces.
- **Count distinct `xdm.*` across ≥20 rows, never one row** (see step 7). Prisma read
  `6` from the newest row but `29` across 20 — a single-row count badly undercounts.
- **Served schema ≠ bundled YAML — the deploy/cache trap.** `data_sources_get_schema`
  serves from a **persistent SQLite store** (`data_sources_store`, in the `/app/data`
  volume) seeded at first install, NOT the live bundled file. The volume survives
  container recreation, so editing a bundled `data_source.yaml`'s **fields** +
  redeploying does **not** refresh the served schema (`PHANTOM_VERSION` flips, the new
  YAML is in the container, yet `get_schema` returns the seeded version). **Verify the
  SERVED field count** (`data_sources_get_schema` — does it carry your new fields?),
  not just the on-disk YAML or the version marker. To make a bundled field-change take
  effect, the store must be re-seeded/refreshed (or push the change via the
  `data_sources_edit` path). Imperva's CEF-key fix is correct in the bundle but inert
  on the served schema until that refresh exists — a real platform gap, not a skill one.

---

Added from the 13-new-vendor campaign (2026-06-08 — the syslog/CEF-only doctrine):

- **Ingestion mode is IRRELEVANT to validatability — but a modeling rule must EXIST to map.**
  The collection mechanism never changes our approach (always syslog/CEF — see the Delivery
  doctrine at the top). But a *rule* must exist to map the shape. Before burning any tenant
  cycle, run the quota-free triage: does the vendor's pack ship a modeling rule? Check
  `GET https://api.github.com/repos/demisto/content/contents/Packs/<Pack>/ModelingRules`
  (200 = has `.xif`; 404 = none). No modeling rule anywhere → nothing to reverse-engineer →
  the dataset lands raw but `datamodel = 0`. That is the honest `validated:false` outcome.
- **XSOAR pack ≠ XSIAM content pack.** A pack in demisto/content with only `Integrations/`
  / `Playbooks/` (API alert-fetch automation) is an XSOAR pack — it carries NO modeling rule.
  XSIAM *ingestion* content lives in packs WITH a `ModelingRules/` dir (often a separate
  `*EventCollector` / `*ModelingRules` pack). All 13 new vendors (CrowdStrike, Sophos, Wiz,
  Rapid7, SAP, Snowflake, Veeam, QRadar, Ping, ESET) had XSOAR packs but ZERO modeling rules
  in demisto/content → none could saturate XDM on the stock tenant.
- **To validate a no-rule-in-snapshot vendor:** the rule must come from elsewhere — the
  operator installs the vendor's XSIAM content pack from the Cortex Marketplace (binds the
  rule to the dataset), or exports the tenant's installed rule. Then reverse-engineer it and
  craft the matching CEF shape. Until a rule exists, keep `validated:false` and document the
  precise prerequisite in `how_to_use`. Do NOT conflate "no rule yet" with "can't be done
  over CEF" — those are different problems.

Added from the green-pill expansion campaign (2026-06-08, batches of 10 cortex-content candidates):

- **Green-pill yield is GATED by the tenant's installed content packs — probe before you batch.** A candidate can have a perfect cortex-content/demisto modeling rule AND land millions of raw rows, yet `datamodel dataset=X` returns 0 because the rule isn't *bound* — the pack isn't installed on THIS tenant. Round 1 hit 3 installed packs (Entra `msft_azure_raw`=42, Zscaler NSS=52, Cisco ASA=65 → validated); round 2 hit **0/10** installed (BeyondTrust, VMware ESXi, Defender for Cloud, Proofpoint CASB, Barracuda CGFW, SecureAuth, Cisco Catalyst, FireEye HX, Arista, Azure App Service — all landed 100K–4.6M raw rows, all `xdm=0`). **Before simulating a batch, cheaply probe which candidates are installed**: for a dataset that already carries raw data, `config timeframe = 30d | datamodel dataset = X | comp count() as modeled` >0 ⇒ rule bound (installed) ⇒ worth a simulate; =0 (with raw>0) ⇒ not installed ⇒ skip (or ask the operator to install the pack). Don't burn simulate cycles on un-installed datasets.
- **`_raw_log`-regex sources need a REALISTIC raw line, not random fields.** Many syslog-native cortex-content rules (firewalls/switches/EDR-audit: BeyondTrust PRA, VMware ESXi/vCenter, Barracuda CGFW, SecureAuth, Cisco Catalyst, FireEye HX, Arista) extract every field via `regextract(_raw_log, "…")` and gate on a *computed* column also carved from `_raw_log` (e.g. `event_type=arrayindex(regextract(_raw_log,"event=([^;]+)"),0) | filter event_type in(…)`). The OverrideSender emits random field values, so the `_raw_log` composite is random → the regex matches nothing → `xdm=0` even when the pack IS installed (cf. round-1 vCenter). To green-pill these, the generator must emit a realistic vendor wire line in `_raw_log` (a real generator enhancement — per-vendor raw-line templates), or seed the full crafted line via `observables_dict={"_raw_log":["<realistic vendor syslog line>"]}`. **CEF-key + JSON-composite sources don't have this problem** — their fields are the real wire columns / json leaves the generator populates directly, which is exactly why the round-1 passes (Cisco ASA `_json` composite, Entra `properties` JSON, Zscaler NSS CEF keys) saturated and the `_raw_log`-regex ones didn't.

## What "validated" means (the bar)

A source is `validated: true` **only** after a live tenant run shows a rich,
fresh `xdm.*` field count through `simulate → XSIAM → XQL`. It is a customer-facing
green pill that asserts "this maps to XDM" — never set it on a source that merely
*should* map. If a source lands + is reverse-engineered but doesn't map on a stock
tenant (e.g. needs pack onboarding), **document it in `how_to_use` with the precise
reason and prerequisite — do not validate it.** That honesty is the whole point of
the pill.

## Scripts & tools at a glance

Full invocations + paths in **[references/tooling.md](references/tooling.md)**.

| Need | Use |
|---|---|
| Pull `.xif` rules from GitHub | `scripts/fetch_demisto_modeling_rules.py` |
| Classify the modeling-rule gate | `scripts/maintainer/reverse_engineer_gate.py` |
| Drive simulate+verify on the tenant | `scripts/maintainer/agent_chat_e2e.py` (+ IAP tunnel + `PHANTOM_API_KEY`) |
| Synthesize missing JSON-composite leaves | `scripts/maintainer/complete_composite_leaves.py` |
| Author `how_to_use` from a rule | `scripts/maintainer/gen_cloud_how_to_use.py` (pattern) |
| Promote to validated (+manifest) | `scripts/maintainer/gen_cloud_validated.py` (pattern) |
| Inspect the generator/sender behavior locally | `xlog/app/dynamic_schema.py`, `xlog/app/override_sender.py` |
| Enforce the validated set + gate seeds in CI | `tooling/validate/validate_all.py` |

The `gen_cloud_*` and `complete_composite_leaves` scripts are **patterns**, not
universal tools — each was tuned to a batch. Read them, adapt the `TARGETS`/`VALIDATED`
dicts, re-run. They write minimal-diff YAML; verify with `git diff` before committing.
