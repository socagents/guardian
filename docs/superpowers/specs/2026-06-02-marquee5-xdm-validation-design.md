# Marquee-5 XDM validation — design spec

**Date:** 2026-06-02
**Goal:** Onboard 5 marquee SOC data sources to the **validated XDM set**, proven end-to-end on the live XSIAM tenant, using the #116 method (+ v0.17.120/121 hardening). One contained arc → one customer release tag (v0.17.122 candidate, Scenario 1).

## Sources (operator-approved 2026-06-02)

| # | Vendor | dataset | bundled dir | fields | category |
|---|---|---|---|---|---|
| 1 | Microsoft 365 Defender | `microsoft_365_defender_raw` | `MicrosoftDefenderAdvancedThreatProtection__Microsoft365DefenderEventCollector__microsoft_365_defender_raw` | 67 | EDR / XDR |
| 2 | Cisco Firepower | `cisco_firepower_raw` | `CiscoFirepower__CiscoFirepower__cisco_firepower_raw` | 31 | NGFW / IPS |
| 3 | Netskope | `netskope_netskope_raw` | `Netskope__NetskopeEventCollector__netskope_netskope_raw` | 88 | CASB / SSE |
| 4 | Cisco Duo | `duo_duo_raw` | `DuoAdminApi__DuoModelingRule__duo_duo_raw` | 49 | MFA / identity |
| 5 | GitHub | `github_github_audit_raw` | `GitHub__GithubModelingRules__github_github_audit_raw` | 25 | DevOps / SaaS audit |

All five currently have **empty `how_to_use`** and **display-name `vendor`/`product`** (need routing-literal correction).

## Method (per source — the proven #116 template)

1. **Routing literals.** Set CEF `vendor`/`product` so the XSIAM broker derives the dataset `<lower-vendor>_<lower-product>_raw`. Target literals (verify against the tenant parsing rule before declaring):
   - `microsoft` / `365_defender` → `microsoft_365_defender_raw`
   - `cisco` / `firepower` → `cisco_firepower_raw`
   - `netskope` / `netskope` → `netskope_netskope_raw`
   - `duo` / `duo` → `duo_duo_raw`
   - `github` / `github_audit` → `github_github_audit_raw`
2. **Gate seed** (re-derived from each modeling rule via `reverse_engineer_gate.py`):
   - MS 365 Defender / Cisco Firepower / Netskope — **unconditional**, no `observables_dict` seed (maps regardless, like FortiGate).
   - Cisco Duo — `eventtype ∈ {administrator, authentication, telephony}` → seed `eventtype=authentication` (richest branch). Pin the YAML `eventtype` example to `authentication`.
   - GitHub — `action ∈ {account*, billing*, …}` **wildcard** gate → seed a concrete action under a covered prefix (e.g. `account.created`). Pin the YAML `action` example accordingly.
3. **how_to_use** — author gate-aware blocks (Required CEF header / MR pattern / Verify XQL / Make-it-map-to-XDM) for all 5 (#116 pattern; all currently empty).
4. **Generate + verify** — `data_sources_get_schema(compact=true)` → `phantom_create_data_worker(schema_override=full, gate seed)` → verify **fresh** XDM via the L24 method (`sort desc _time`; count distinct non-null `xdm.*`; don't assume `xdm.event.type`).
5. **Validate** — `validated: true` + add to `validated_data_sources.txt` (→ **32** total); `check_validated_data_sources_manifest` + `check_gate_fields_satisfied` green.

## Acceptance bars (fresh-event-verified)

- MS 365 Defender, Netskope, Cisco Duo: **≥25** XDM.
- Cisco Firepower, GitHub: **≥15** XDM.
- Every source: fresh `_time` on the verified rows (this run, not accumulated).

## Risks / wrinkles

1. **GitHub wildcard gate.** `check_gate_fields_satisfied` does exact set-membership, but GitHub's modeling-rule values are wildcards (`account*`…). **Resolve:** extend the gate-check to honor trailing-`*` prefix wildcards (preferred — general), OR pin the YAML example to a value the live rule accepts and document the exception. Decide at implementation.
2. **UDP MTU (L18).** Netskope (88f) + MS Defender (67f) may approach the 1500-byte ceiling if composites are large. Check single-event size; split into 2 events (SentinelOne pattern) only if a single event truncates.
3. **Routing-literal drift.** YAML `vendor`/`product` are display names; the CEF routing literals differ (the #116 SentinelOne trap). Verify each derives the intended dataset on the live broker before declaring validated.

## Release

One arc, one customer tag (v0.17.122 candidate). Closing cycle mirrors #116: `validated:true` ×5 + manifest, CHANGELOG + release-notes, gate-aware `how_to_use`, cumulative smoke matrix to the tracking issue. Mid-arc commits get CHANGELOG entries; tag only at capability completion with explicit operator approval.

## Outcome (2026-06-03)

End-to-end verification on the live tenant (365-day window) resolved the arc as **3 of 5 validated**:

| Source | dataset | XDM fields | Verdict |
|---|---|---|---|
| Cisco Firepower | `cisco_firepower_raw` | **39** | ✅ validated (unconditional MR; CEF `Cisco`/`Firepower`) |
| Cisco Duo | `duo_duo_raw` | **54** | ✅ validated (gate `eventtype=authentication`; CEF `duo`/`duo`) |
| Microsoft 365 Defender | `microsoft_365_defender_raw` | **40** | ✅ validated (unconditional MR; CEF `microsoft`/`365_defender`) |
| Netskope | `netskope_netskope_raw` | 0 | ⛔ tenant-gated — raw lands + columns extract (`source_log_event=application`), but `datamodel` yields 0 rows over 365d; broker-auto-created dataset, MR not associated. Fix: onboard the Netskope content pack. |
| GitHub audit | `github_github_audit_raw` | 0 | ⛔ tenant-gated — JSON-native; tenant INGEST parses JSON `created_at`, not CEF, so the MR's `action` column is absent. Fix: JSON via HTTP collector. |

**Spec corrections from reality:**
- The GitHub acceptance bar (≥15 XDM) was wrong: the GitHub MR caps at ~5 mapped fields, and on this tenant GitHub is unmappable via syslog-CEF entirely (0). Dropped from the validated target.
- **Window trap:** synthetic events can carry a `_time` several days in the past, so XDM verification MUST use a ≥7-day window. A 24h window briefly made Cisco Firepower (39 fields) look like a total routing failure (`raw=0`). The root-cause generator fix (event time → now) is tracked as a separate task; the wide-window workaround is documented in each validated `how_to_use`.

Released as v0.17.122 (Scenario 1). Netskope + GitHub remain bundled with documented onboarding requirements in their `how_to_use`, not flagged validated.
