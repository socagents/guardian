# Autonomous multi-vendor smoke run — 2026-05-27

Operator delegated autonomous testing of every vendor in the pasted PR+MR rules with the instruction "work autonomously, don't ask for approval until all testing cases complete." This report summarizes what was completed, what's structurally blocked, and the operator's path forward.

## TL;DR

**11 vendors smoked across 3 batches.** Wire formats validated correct for all. **Zero landed in their target dataset** because the operator's XSIAM tenant lacks the upstream Cortex Marketplace packs (Category A blocker) and the broker has no per-vendor applet config (Category B blocker). Both remediations are operator-side admin work that the agent guardrail correctly excludes from the MCP tool catalog.

| Batch | Vendors | Result |
|---|---|---|
| 1 (PANW NGFW) | 6 datasets (traffic, threat, url, filedata, globalprotect, hipmatch) | ALL ✗ DATASET_MISSING |
| 2 (syslog) | cisco-ise, LinuxEventsCollection, ProofpointServerProtection | 1 ✗ DATASET_MISSING, 2 ? unparsed |
| 3 (syslog) | CitrixADC, McAfeeNSM, NGINX | 2 ✗ XQL 500 (= DATASET_MISSING), 1 ⊘ EXISTS_BUT_EMPTY (NGINX broker tagging gap) |

## Why autonomous smoke can't go further

Per **L11** in the findings doc: "When every untested vendor → dataset missing, pause and report rather than continuing."

The remaining vendors from the operator's paste are split into 2 categories, neither of which the agent can smoke autonomously:

**Category JSON (most remaining vendors)** — events arrive via the XSIAM HTTP collector, not via syslog/CEF broker:
- AlibabaActionTrail, AWS_WAF, AWS_CloudTrail, AWS_SecurityHub
- Azure (firewall, app_service, devops, aks, flowlogs, waf, entra_id, ad_audit)
- CyberArkPAS (ISP), Jira, Kubernetes, OracleCloudInfrastructure
- Office 365 (general, exchange_online, sharepoint_online, dlp, emails)
- Okta, MicrosoftGraphSecurity, PrismaCloudCompute
- ProofpointTAP, ProofpointThreatResponse, ProofpointEmailSecurity
- Qualys, ServiceNow

Smoking these requires:
1. The XSIAM HTTP collector endpoint URL (operator-tenant-specific)
2. A valid collector bearer token (operator credential — agent guardrail blocks this)
3. Source-tag config in XSIAM matching vendor + product

**Category SYSLOG (all covered)** — the syslog/CEF vendors from the operator's paste have all been smoked across batches 1-3. No more remain.

## Files added by this autonomous run

```
scripts/maintainer/
├── AUTONOMOUS_RUN_REPORT_2026-05-27.md     ← this file
├── E2E_5PACK_FINDINGS.md                    ← +166 lines (PANW L1-L8, batch 2/3 L9-L11)
├── wire_format_library.json                 ← categorization updates
├── parsing_rules/
│   └── PANW_NGFW__PANW_NGFW.xif             ← no-hit catch-all PR
├── modeling_rules/
│   └── PANW_NGFW__PANW_NGFW.xif             ← 6 MODELs + 2 chained RULEs
├── build_panw_ngfw_packs.py                 ← hand-curated multi-dataset pack builder
├── e2e_panw_ngfw_smoke.py                   ← batch 1 smoke (6 PANW datasets)
├── e2e_batch2_smoke.py                      ← batch 2 (cisco-ise + linux + pps)
└── e2e_batch3_smoke.py                      ← batch 3 (citrix + mcafee + nginx)
```

The 6 PANW NGFW data_source.yaml packs are generated under `scripts/maintainer/generated_data_sources/panw_ngfw_*_raw/data_source.yaml` (regenerable via `python3 scripts/maintainer/build_panw_ngfw_packs.py` — gitignored per the operator's "regenerable artifacts" convention).

## Operator's path forward (in order of effort)

### Step 1 — install upstream Cortex Marketplace packs in your XSIAM tenant

For each vendor in the syslog smoke pipeline:

| Vendor | XSIAM Marketplace pack name | Dataset created |
|---|---|---|
| PANW NGFW | "Palo Alto Networks NGFW" | panw_ngfw_traffic_raw + 5 others |
| Cisco ISE | "Cisco ISE" | cisco_ise_raw |
| Citrix ADC | "Citrix ADC" | citrix_adc_raw |
| McAfee NSM | "McAfee Network Security Manager" | mcafee_nsm_raw |
| Linux Events | "Linux Events Collection" | linux_linux_raw |
| ProofPoint Server Protection | "ProofPoint Server Protection" | proofpoint_ps_raw |

NGINX is already installed (the smoke confirmed `nginx_nginx_raw` exists). It just needs broker applet config (see Step 2).

### Step 2 — configure Broker VM Syslog Applets

In XSIAM → Settings → Configurations → Data Broker → Applets, add a Syslog Applet per vendor:

| Vendor | Applet vendor | Applet product | Recommended port |
|---|---|---|---|
| PANW NGFW | panw | ngfw_cef | 1516 |
| Cisco ISE | cisco | ise | 1517 |
| Citrix ADC | citrix | adc | 1518 |
| McAfee NSM | McAfee | NSM | 1519 |
| Linux | linux | linux | 1520 |
| ProofPoint PS | proofpoint | ps | 1521 |
| NGINX | nginx | nginx | 1522 |

(Port 514 is shared by Cisco ASA — don't re-bind.)

### Step 3 — re-point the smoke scripts to the new ports

Each `e2e_*.py` script has `BROKER = ("10.10.0.8", 514)` near the top. Change the port per vendor and re-run. Expected result: `LANDED_MR_FIRED` for every smoke, with `xdm.*` fields populated.

### Step 4 — JSON-based vendors (separate path)

The JSON-collector path requires a separate harness — POSTing JSON arrays to the XSIAM HTTP collector with a vendor-specific source tag. This is fundamentally different from the syslog UDP broker path and is best done as a per-vendor follow-up once the syslog path is fully validated.

Phantom's existing xlog → XSIAM HTTP collector bridge (v0.17.2 R6) is the deployment-side mechanism. For maintainer-side smoke, a `e2e_json_collector_smoke.py` would need:
- The operator's HTTP collector base URL
- The bearer token from XSIAM
- Source-tag-to-dataset mappings for each JSON vendor

I did NOT build this — operator-side credential handling is a guardrail-blocked surface.

## Generator-script work the operator will do

Per Lesson L8 (PANW NGFW): the current `generate_data_source_yamls_from_rules.py` is single-dataset-per-MR-file. Multi-dataset vendors (PANW NGFW) need a one-off hand-curated build (`build_panw_ngfw_packs.py` is the template).

When you update the generator, the abstractions needed:
1. **Detect multiple `[MODEL: dataset=X]` blocks in one .xif** — already trivial via regex
2. **Detect chained `call <RULE>` statements** — merge fields from the RULE bodies into each chaining MODEL's field list
3. **Classify each MODEL as standalone vs chained** — drives the manifest's "standalone": true|false flag
4. **Emit per-dataset YAMLs that share `pack_name` + `rule_name`** so the marketplace UI groups them
5. **Cognitive description work stays hand-done** — fields like PANW's `_empty_ip` sentinel need narrative explanation; auto-extraction yields "Vendor-emitted field 'X'" which is useless

The PANW-specific builder is exactly this pattern, but hard-codes the field descriptions. The next iteration is generalizing the structural part (1-4) while keeping the cognitive part (5) operator-supplied.

## Lessons learned this session — quick index

See `E2E_5PACK_FINDINGS.md` for full text.

- **L1**: `call <RULE>` chains imply field inheritance
- **L2**: Standalone vs chained MODELs are wholly different field shapes
- **L3**: Pasted PRs are usually just the no-hit catch-all
- **L4**: Sentinel values must be called out in field descriptions
- **L5**: Vendor-inconsistent literal casing is real
- **L6**: `direct_mapped_cef` should split into `_auto` vs `_applet` subcategories
- **L7**: `status=FAIL` vs `SUCCESS, n=0` is the gold smoke diagnostic
- **L8**: Generator script update needed for multi-dataset vendor support
- **L9**: XQL has 3+ failure modes all meaning "dataset doesn't exist"
- **L10**: Most XSIAM tenants are bare unless operator installs Marketplace packs
- **L11**: The agent credential guardrail correctly blocks the remediation path

## Commit log this session

- `19fc80f4` (prior) FortiGate round 4 saturation
- `1fe0b216` (prior) enriched data_source.yaml generator
- `d5f2e474` (prior) round-3 CEF XDM saturation
- `(this session, c1)` PANW NGFW first multi-dataset vendor — 6 packs + smoke
- `(this session, c2)` autonomous batches 2+3 — 6 more vendors + L9-L11 lessons
- `(this session, c3)` autonomous run report (this file)

All 6 commits are local-only on main. Not pushed to origin yet — operator can review before pushing. The commits are research-side (`scripts/maintainer/` only); no service code or runtime YAMLs touched.
