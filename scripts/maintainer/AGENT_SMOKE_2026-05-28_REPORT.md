# Agent-chat MCP-path smoke matrix — 22 validated vendors

Started: 2026-05-28 09:39:57 UTC
Finished: 2026-05-28 10:06:40 UTC
Elapsed: ~26 min

Path tested per vendor:
  1. Agent MCP (port 8080, HTTPS): phantom_create_data_worker(
     type=CEF, vendor=X, product=Y, schema_override=<fields[]>)
  2. Worker → OverrideSender → CEF over UDP → broker 10.10.0.8:514
  3. XSIAM connector MCP (direct, port 9000): run_xql_query against
     `dataset = <vendor>_<product>_raw | sort desc _time | limit 1`

| Vendor (slug) | Dataset | Worker created? | Events landed? | XDM rows | Notes |
|---|---|---|---|---|---|
| `Okta__OktaModelingRules_2_0__okta_okta_raw` | `okta_okta_raw` | ✅ | ✅ 1 | 0 | landed; XDM 0 (likely composite-JSON synthesis gap) |
| `Okta__OktaModelingRules_2_0__okta_sso_raw` | `okta_sso_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `AlibabaActionTrail__AlibabaModelingRules__alibaba_action_...` | `alibaba_action_trail_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `AWS-CloudTrail__AWSCloudTrail__amazon_aws_raw` | `amazon_aws_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `AWS-SecurityHub__AWSSecurityHubModelingRules__aws_securit...` | `aws_security_hub_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `AWS_WAF__AWS_WAF__aws_waf_raw` | `aws_waf_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `Jira__JiraEventCollector__atlassian_jira_raw` | `atlassian_jira_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `ServiceNow__ServiceNow__servicenow_servicenow_raw` | `servicenow_servicenow_raw` | ✅ | ✅ 1 | ✅ 1 | landed; XDM=17 |
| `CyberArkPAS__CyberArkISP__cyberark_isp_raw` | `cyberark_isp_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `MicrosoftEntraID__MicrosoftEntraID__msft_azure_ad_audit_raw` | `msft_azure_ad_audit_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `MicrosoftEntraID__MicrosoftEntraID__msft_azure_ad_raw` | `msft_azure_ad_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `Office365__Office365__msft_o365_general_raw` | `msft_o365_general_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `Office365__Office365__msft_o365_exchange_online_raw` | `msft_o365_exchange_online_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `Office365__Office365__msft_o365_sharepoint_online_raw` | `msft_o365_sharepoint_online_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `Office365__Office365__msft_o365_emails_raw` | `msft_o365_emails_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `Office365__Office365__msft_o365_dlp_raw` | `msft_o365_dlp_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `qualys__QualysModelingRules__qualys_qualys_raw` | `qualys_qualys_raw` | ✅ | ✅ 1 | 0 | landed; XDM 0 (likely composite-JSON synthesis gap) |
| `ProofpointEmailSecurity__ProofpointEmailSecurity__proofpo...` | `proofpoint_email_security_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `ProofpointTAP__ProofpointTAPModelingRules__proofpoint_tap...` | `proofpoint_tap_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `AzureFlowLogs__AzureFlowLogs__msft_azure_flowlogs_raw` | `msft_azure_flowlogs_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `AzureWAF__AzureWAF__msft_azure_waf_raw` | `msft_azure_waf_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |
| `AzureKubernetesServices__AzureKubernetesServices__msft_az...` | `msft_azure_aks_raw` | ✅ | ❌ 0 | 0 | dataset has no fresh events |

**Summary**: 3/22 vendors landed events in their dataset. 1/22 produced any XDM rows.

**Known follow-on (out of scope for this run):** `_generate_value` in `xlog/app/dynamic_schema.py` doesn't honor `type: json` — composite fields like Okta's `actor`, AWS WAF's `httpRequest`, Azure AD's `targetResources` get random strings instead of JSON-shaped values. The MR's `json_extract_scalar` returns null → XDM stays sparse for nested-JSON vendors. Flat-field vendors (Azure WAF, Azure Flow Logs) should saturate well.
