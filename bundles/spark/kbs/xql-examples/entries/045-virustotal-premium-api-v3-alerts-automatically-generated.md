---
id: XQL-045-5f7e0c94
title: VirusTotal - Premium (API v3) Alerts (automatically generated)
category: alert-mapping
dataset: virustotal_premium_api_v3__generic_alert_raw
tags:
- alter
- filter
ecosystem: xsiam
---
# VirusTotal - Premium (API v3) Alerts (automatically generated)

**Dataset**: `virustotal_premium_api_v3__generic_alert_raw`

```sql
dataset = virustotal_premium_api_v3__generic_alert_raw
| filter _alert_data != null
| alter alert_severity = json_extract_scalar(_alert_data, "$.severity")
| alter alert_category = json_extract_scalar(_alert_data, "$.alert_category")
| alter alert_name = json_extract_scalar(_alert_data, "$.alert_name")
| alter alert_description = json_extract_scalar(_alert_data, "$.alert_description")
```
