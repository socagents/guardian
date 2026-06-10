# Agent-chat MCP-path smoke — failure-mode analysis

Companion to `AGENT_SMOKE_2026-05-28_REPORT.md`. Same run, fresh analysis
once all 22 vendors returned.

## Headline

| Metric | Count |
|---|---|
| Vendors driven via the agent's chat path (workers created) | **22 / 22** |
| Vendors whose events landed in the target dataset | **3 / 22** (Okta okta_okta_raw, ServiceNow, Qualys) |
| Vendors whose XDM rows materialized | **1 / 22** (ServiceNow — XDM=17) |
| Elapsed wallclock | ~26 min over 6 batches |

**The MCP-tool plumbing is correct end-to-end** (every worker created
successfully via `phantom_create_data_worker` invoked through the agent's
HTTPS port-8080 MCP). The drop-off happens downstream — in synthetic event
quality, not in tool invocation.

## Why 19 vendors showed `dataset has no fresh events`

Three orthogonal problems compound, in roughly decreasing order of impact:

### 1. The broker's auto-route uses CEF `vendor` + `product` literally; YAML `dataset_name` ≠ broker-derived name

XSIAM's broker normalizes the CEF header's vendor + product to
`<lowercased-vendor>_<lowercased-product>_raw` (non-alphanumerics → `_`).
The YAML's `dataset_name` field is the canonical name the operator's
**installed upstream Cortex pack PR** routes events to — which is
frequently **different** from what the broker auto-derives from the
literal header.

Concrete mismatches in this run:

| Vendor (YAML) | Product (YAML) | Broker would derive | YAML dataset_name | Match? |
|---|---|---|---|---|
| `Okta` | `Okta` | `okta_okta_raw` | `okta_okta_raw` | ✅ |
| `Amazon Web Services` | `AWS-CloudTrail` | `amazon_web_services_aws_cloudtrail_raw` | `amazon_aws_raw` | ❌ |
| `Amazon Web Services` | `AWS_WAF` | `amazon_web_services_aws_waf_raw` | `aws_waf_raw` | ❌ |
| `Microsoft` | `MicrosoftEntraID` | `microsoft_microsoftentraid_raw` | `msft_azure_ad_raw` | ❌ |
| `Microsoft` | `Office365` | `microsoft_office365_raw` | `msft_o365_*_raw` (× 5) | ❌ |
| `Atlassian` | `Jira` | `atlassian_jira_raw` | `atlassian_jira_raw` | ✅ |
| `ServiceNow` | `ServiceNow` | `servicenow_servicenow_raw` | `servicenow_servicenow_raw` | ✅ |
| `Qualys` | `Qualys` | `qualys_qualys_raw` | `qualys_qualys_raw` | ✅ |

**Pattern**: vendors where the broker's auto-route matches the YAML
dataset_name landed (Okta, ServiceNow, Qualys). Vendors where they
diverge didn't.

**The events still arrived at the broker**, but they probably went to
the auto-derived dataset (e.g., `amazon_web_services_aws_cloudtrail_raw`)
instead of `amazon_aws_raw` — or to `unknown_unknown_raw` if no parsing
rule matches the derived name.

**Fix sketch**: the OverrideSender should look up the vendor's expected
dataset_name (from the YAML) and emit CEF header values whose
broker-auto-derived name matches. For AWS CloudTrail that's literally
`vendor=amazon, product=aws` so the broker derives `amazon_aws_raw`.
Hand-rolled smokes have always done this; the agent's chat path
doesn't yet learn this mapping.

### 2. Multi-dataset packs need a discriminator field set to a specific value

For packs with multiple datasets sharing a vendor/product, the PR uses
a content field as the discriminator. Examples:

- **Okta SSO** (`okta_sso_raw`) — same `vendor=Okta, product=Okta` as
  `okta_okta_raw`. The PR routes by `eventType startswith
  "user.session.*"` or `"user.authentication.sso"`. Random `eventType`
  values land in the catch-all `okta_okta_raw` instead.
- **O365 × 5 datasets** — same `vendor=Microsoft, product=Office365`.
  The PR uses `Workload` (`Exchange`/`SharePoint`/`DLP`/etc.) as the
  discriminator. Random strings don't match any branch.
- **Microsoft Entra ID** sign-in vs audit — discriminated by
  `category` (`SignInLogs`/`AuditLogs`).

**Fix sketch**: the YAML's `how_to_use` field already documents the
discriminator value per dataset; the OverrideSender should consult it
(or a new structured `pr_discriminator:` field) to fill that field
with the right literal value per worker.

### 3. `_generate_value` doesn't honor controlled YAML types — composites become random strings

Documented at length in v0.17.78 follow-on backlog. `type: json` /
`type: enum` / `type: regex` fields get random short strings, so the
MR's `json_extract_scalar`, enum-branch, and regex-extract paths all
return null. Even when events DID land (Okta, ServiceNow, Qualys),
XDM saturation stayed at 0 — except ServiceNow.

### Why ServiceNow scored XDM=17

ServiceNow's MR seems to be **mixed/flat-field heavy** AND the
`servicenow_servicenow_raw` dataset's parsing rule must be lenient about
field shapes. The OverrideSender's random strings populated enough
typed columns that 17 XDM mappings materialized. Sample populated XDM
fields from the state file:

```
(see state JSON for full list — typically xdm.event.*, xdm.source.user.*,
xdm.target.host.*, xdm.observer.action, etc.)
```

This is the **best-case** scenario for the current OverrideSender:
flat-field MR + lenient PR + broker auto-route matches YAML name.

## Recommended next iterations (in priority order)

### A. Broker-route mapping table (P0)

`xlog/app/override_sender.py` should accept a `dataset_routing:` hint
from the agent's call (or from the YAML) and override the CEF header's
`vendor` + `product` values to match what the broker auto-derives to
the target dataset_name.

Concretely: when the agent calls `phantom_create_data_worker(
schema_override=<okta sso fields>, target_dataset='okta_sso_raw')`, the
OverrideSender should:

1. Recognize this as `okta_okta_raw` family (same vendor) needing
   discriminator override
2. Emit `vendor=Okta`, `product=Okta` (auto-derives to `okta_okta_raw`)
3. Set `eventType=user.session.start` (the SSO discriminator) so the
   PR routes to `okta_sso_raw`

This single change should unblock 6 of the 19 failing vendors (Okta
SSO + O365 × 5).

### B. AWS / Microsoft vendor-name normalization (P0)

For vendors where the YAML's display name doesn't auto-derive correctly,
add a `broker_vendor:` / `broker_product:` override field to the YAML
that the OverrideSender prefers over the canonical `vendor` / `product`.

This unblocks AWS-CloudTrail (`amazon_aws_raw`), AWS-SecurityHub,
AWS_WAF, Microsoft Entra ID × 2, and the Azure family (× 3).

### C. `_generate_value` controlled-type synthesis (P1)

The v0.17.78 follow-on. Builds on (A) + (B): once events route
correctly, the XDM saturation gap becomes the dominant problem.

### D. Bug-family flatten for xsiam/cortex-xdr tool signatures (P1)

So the agent's chat can drive XQL verification without bypassing to
the connector's port 9000.

## Files this run produced

- `scripts/maintainer/e2e_all_vendors_via_agent_mcp.py` — autonomous
  batch script that handled 4 vendors per call, persisted state in
  `/app/data/agent_smoke_state.json`
- `scripts/maintainer/AGENT_SMOKE_2026-05-28_REPORT.md` — auto-generated
  matrix (this companion analysis lives next to it)
- `scripts/maintainer/AGENT_SMOKE_2026-05-28_STATE.json` — per-vendor
  raw result fields
