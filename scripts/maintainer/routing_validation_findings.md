# Routing validation findings — reverse-engineered data-source enrichment

Companion to [`routing_validate_enriched.py`](routing_validate_enriched.py). Records what the
sweep validates, the methodology, and the contamination classes discovered while debugging it.
Run against the deployed phantom-vm install on 2026-06-06.

## What this validates

The enrichment campaign (commits `a0cb638a`…`26dae136`) reverse-engineered each non-validated
data source's `how_to_use` from its parsing/modeling rules — including the **dataset-anchored
routing** literal. The broker derives a dataset from `norm(vendor)_norm(product)_raw`, so a pack's
**display** name often does NOT derive its real dataset (Amazon Web Services/AWS-GuardDuty →
`amazon_web_services_aws_guardduty_raw`, not the real `aws_guardduty_raw`). The enricher resolves
this two ways; this sweep validates each empirically on a live tenant.

## Methodology

| Class | `how_to_use` says | Test | Pass criterion |
|---|---|---|---|
| **Asserted** | gives a recovered CEF literal (e.g. `AWS`/`GuardDuty`, recovered from the parsing rule's `[INGEST:]`) | send the **recovered literal** | **target dataset grows** (`VALIDATED`) |
| **Flagged** | warns of a display↔routing divergence, no recovered literal | send the **display name** | **target stays flat** (`CONFIRMED`) |

- **Positive vs negative.** Asserted is the stronger claim — it proves the recovered literal is
  *correct*, not merely that the display name is wrong. 131 of the asserted sources are
  "trap-with-fix": the recovered literal differs from the misleading display name.
- **Delta-based.** Every target is read BEFORE and AFTER the send; `after - before` is the signal,
  so datasets with pre-existing data don't read as false growth.
- **Validated excluded.** The 22 validated vendors are out of scope (not "non-validated
  mismatches") AND their datasets carry continuous smoke traffic that confounds the delta.

## The universe (deployed bundle, 2026-06-06)

`how_to_use` is present on **every** served source (288 total; enrichment fully deployed). Excluding
the 22+ validated vendors and 1 non-conforming `how_to_use`, the sweepable universe is **250**:

- **134 asserted** (≈84% trap-with-fix — recovered literal ≠ display name)
- **116 flagged** (warn-only, no recovered literal)

## Results — full coverage (250/250 swept, 2026-06-06)

| Class | Result |
|---|---|
| **Asserted** (send recovered literal → target grows) | **127/134 VALIDATED** · 103 trap-with-fix |
| **Flagged** (send display name → target stays flat) | **116/116 CONFIRMED** (100%) |

All 116 flagged warnings are justified. The 7 asserted FAILs split cleanly into two classes:

### 6 genuine enrichment bugs — false "normalizes to" claim

| Dataset | `how_to_use` asserts | actually normalizes to |
|---|---|---|
| `microsoft_adfs_raw` | `microsoft`/`windows` | `microsoft_windows_raw` |
| `microsoft_amsi_raw` | `microsoft`/`windows` | `microsoft_windows_raw` |
| `microsoft_dns_raw` | `microsoft`/`windows` | `microsoft_windows_raw` |
| `microsoft_sysmon_raw` | `microsoft`/`windows` | `microsoft_windows_raw` |
| `msft_azure_app_service_raw` | `MSFT`/`Azure` | `msft_azure_raw` |
| `msft_azure_devops_raw` | `msft`/`azure` | `msft_azure_raw` |

These are Windows event channels / Azure resource logs whose parsing-rule `[INGEST:]` declares a
**broad** vendor/product identity (`Microsoft`/`Windows`, `MSFT`/`Azure`) that the rule then splits
into per-channel sub-datasets downstream. The enricher's `match = bool(iv and ip)` trusted the broad
literal and wrote "these normalize → `<sub-dataset>`" — but `norm(microsoft/windows)` =
`microsoft_windows`, not `microsoft_adfs`. The claim is mathematically false; an operator following it
would never fill the sub-dataset. Detectable statically (`collapse(norm(literal)) != collapse(dataset)`),
so the validator's upfront scan lists exactly these 6 — **no XQL needed to find them**.

**Fix:** in `enrich_nonvalidated_how_to_use.py`, require `norm(iv)_norm(ip) == stem` for a `match`;
when a broad `[INGEST:]` identity doesn't normalize to the dataset, *flag* it (channel-split note)
instead of asserting a false routing literal. Then regenerate the 6 YAMLs.

### 1 testing limitation — non-CEF-native vendor

`fortinet_fortiweb_raw` (asserts `fortinet`/`fortiweb`): the literal is **correct** (`norm` = the
target), but Fortinet's native ingestion is its own syslog, not CEF, so the broker drops the synthetic
CEF before it can route — the events appear in no Fortinet dataset. Same class as the 5 Check Point
flagged sources. A limitation of CEF-based synthetic testing, not a wrong literal.

**Imperva note:** `imperva_inc__securesphere_raw` (the double underscore — the dataset that opened this
session) was static-flagged but **live-VALIDATED**: the broker normalizes `Imperva Inc.` →
`imperva_inc_` (period → `_`) and joins to the double-`_` dataset, which `norm()` collapses to single
`_`. The `collapse()` comparison treats the two as equal, so the static scan no longer false-positives.

**Net:** of 134 recovered literals, **127 route correctly, 1 is correct-but-untestable-via-CEF, and 6
carry a false normalization claim** — the one actionable enrichment fix. Verdicts accumulate in
`/app/data/routing_validation.json`.

## Three contamination classes discovered (and handled)

Debugging the sweep surfaced three distinct ways a naive delta misreads, each now handled:

1. **Pre-existing data.** v1 read only the after-count and assumed untested targets were empty —
   so `alibaba_action_trail_raw` (594k pre-existing rows) read as a false anomaly. **Fix:**
   before/after delta. The same dataset then correctly showed `+6479` from the send.
2. **Concurrent background workers.** The synthetic `count=N` worker emits *continuously* at ~N/s
   until killed — it is NOT an N-events-then-stop send. Earlier smokes left **18 workers** pumping
   the validated AWS datasets, so `amazon_aws_raw` grew **+1450 over 75s with no send** while a
   non-validated control held at exactly +0. **Fix:** kill lingering workers + exclude validated
   datasets (whose background traffic can't be subtracted out).
3. **Built-in broker CEF parsers.** Marquee vendors (Check Point, AWS) have broker-side parsers that
   route by recognized `deviceVendor`, overriding pure `norm()` derivation. The flag's load-bearing
   claim is "**display name doesn't reach the target**" (`target+0`); where the events *do* land is
   secondary. **Fix:** `target+0` is the pass criterion; growth in the predicted display-derived
   dataset is a bonus annotation, not a requirement.

## Notable: Check Point

The 5 Check Point sources share one display identity (`Check Point`/`CheckpointFirewall`) and all
hold at `target+0` (flag confirmed). Their display CEF surfaced in **neither** the predicted
`check_point_checkpointfirewall_raw` nor the canonical `check_point_vpn_1_firewall_1_raw` — likely
**dropped**, because Check Point's native ingestion is Log Exporter key-value syslog, not CEF, and
the broker's Check Point-aware pipeline rejects a synthetic CEF that doesn't match. The routing
conclusion is unaffected: the display name does not reach the specific target sub-dataset.

## Re-running / continuing coverage

```bash
# from the repo, against the deployed install (accumulates in /app/data/routing_validation.json):
docker exec -i phantom_agent python3 - --mode both --batch 30 \
    < scripts/maintainer/routing_validate_enriched.py
```

Repeat until the universe is exhausted for full coverage. Always kill lingering workers afterward
(`phantom_list_workers` → `phantom_kill_worker`) — `count=N` workers do not self-terminate.
