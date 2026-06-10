# Agent-chat MCP-path smoke — 22 validated vendors (CORRECTED)

Re-verified: 2026-06-04 05:07 UTC

Method: per-vendor CEF worker created via the **agent MCP** (port 8080, HTTPS) → OverrideSender → CEF/UDP → broker `10.10.0.8:514` → XSIAM. Landing + XDM confirmed via the **xsiam connector MCP** (port 9000) `run_xql_query`. XDM counts are **distinct non-null `xdm.*` fields across up to 20 rows** (30-day window) — not the single newest row, which undercounts.

## Result: 22/22 datasets landed events · 22/22 produced XDM rows

The earlier in-run state recorded **0/22 landed**. That was a *harness* bug, NOT a data-landing failure: `verify_vendor` called `run_xql_query` with a `{"request": {…, "tenant_timeframe": …}}` wrapper, which the connector tool rejects (`Unexpected keyword argument`). The tool takes a single **flat** `query` string with the window inline (`config timeframe = …`). With the corrected call, every dataset shows landed events and rich XDM mapping.

| # | Vendor (slug) | Dataset | Landed | XDM fields | Rows | Most recent (UTC) |
|---|---|---|:---:|:---:|:---:|---|
| 1 | `Okta__OktaModelingRules__okta_okta_raw` | `okta_okta_raw` | ✅ | 49 | 20 | 06-04 04:56 |
| 2 | `Okta__OktaModelingRules__okta_sso_raw` | `okta_sso_raw` | ✅ | 49 | 20 | 06-01 03:54 |
| 3 | `AlibabaActionTrail__AlibabaModelingRules__alibaba...` | `alibaba_action_trail_raw` | ✅ | 26 | 20 | 06-04 04:58 |
| 4 | `AWS-CloudTrail__AWSCloudTrail__amazon_aws_raw` | `amazon_aws_raw` | ✅ | 37 | 6 | 06-01 15:44 |
| 5 | `AWS-SecurityHub__AWSSecurityHubModelingRules__aws...` | `aws_security_hub_raw` | ✅ | 11 | 20 | 06-04 04:58 |
| 6 | `AWS_WAF__AWS_WAF__aws_waf_raw` | `aws_waf_raw` | ✅ | 15 | 20 | 06-04 04:59 |
| 7 | `Jira__JiraEventCollector__atlassian_jira_raw` | `atlassian_jira_raw` | ✅ | 21 | 3 | 05-28 03:54 |
| 8 | `ServiceNow__ServiceNow__servicenow_servicenow_raw` | `servicenow_servicenow_raw` | ✅ | 17 | 20 | 06-01 15:45 |
| 9 | `CyberArkPAS__CyberArkISP__cyberark_isp_raw` | `cyberark_isp_raw` | ✅ | 40 | 20 | 06-04 05:00 |
| 10 | `MicrosoftEntraID__MicrosoftEntraID__msft_azure_ad...` | `msft_azure_ad_audit_raw` | ✅ | 29 | 20 | 06-01 15:48 |
| 11 | `MicrosoftEntraID__MicrosoftEntraID__msft_azure_ad...` | `msft_azure_ad_raw` | ✅ | 44 | 20 | 06-04 05:01 |
| 12 | `Office365__Office365__msft_o365_general_raw` | `msft_o365_general_raw` | ✅ | 53 | 20 | 06-01 15:48 |
| 13 | `Office365__Office365__msft_o365_exchange_online_raw` | `msft_o365_exchange_online_raw` | ✅ | 53 | 20 | 06-04 05:02 |
| 14 | `Office365__Office365__msft_o365_sharepoint_online...` | `msft_o365_sharepoint_online_raw` | ✅ | 38 | 20 | 06-04 05:03 |
| 15 | `Office365__Office365__msft_o365_emails_raw` | `msft_o365_emails_raw` | ✅ | 18 | 20 | 06-04 05:03 |
| 16 | `Office365__Office365__msft_o365_dlp_raw` | `msft_o365_dlp_raw` | ✅ | 37 | 20 | 06-01 15:50 |
| 17 | `qualys__QualysModelingRules__qualys_qualys_raw` | `qualys_qualys_raw` | ✅ | 14 | 20 | 06-04 05:04 |
| 18 | `ProofpointEmailSecurity__ProofpointEmailSecurity_...` | `proofpoint_email_security_raw` | ✅ | 16 | 20 | 06-04 05:04 |
| 19 | `ProofpointTAP__ProofpointTAPModelingRules__proofp...` | `proofpoint_tap_raw` | ✅ | 12 | 20 | 06-04 05:03 |
| 20 | `AzureFlowLogs__AzureFlowLogs__msft_azure_flowlogs...` | `msft_azure_flowlogs_raw` | ✅ | 50 | 20 | 06-01 15:52 |
| 21 | `AzureWAF__AzureWAF__msft_azure_waf_raw` | `msft_azure_waf_raw` | ✅ | 40 | 6 | 06-04 04:54 |
| 22 | `AzureKubernetesServices__AzureKubernetesServices_...` | `msft_azure_aks_raw` | ✅ | 16 | 20 | 06-04 04:54 |

**XDM field-count distribution** (datasets with XDM>0): min 11, max 53, mean 31.1, median 37.

## Root-cause fix shipped this run

- `scripts/maintainer/e2e_all_vendors_via_agent_mcp.py` → `verify_vendor`: `run_xql_query` now receives `{"query": "config timeframe = 1d | …"}` instead of the rejected `{"request": {"query": …, "tenant_timeframe": …}}`. Single cause of the campaign-wide false-0.
- `scripts/maintainer/wide_verify_datasets.py` → reusable wide-window re-verification using the corrected flat-`query` shape + distinct-xdm methodology.