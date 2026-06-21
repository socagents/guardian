---
id: XQL-003-b9e7c0fd
title: jira-v2 Alerts (automatically generated)
category: alert-mapping
dataset: jira_v2_generic_alert_raw
tags:
- alter
- filter
ecosystem: xsiam
---
# jira-v2 Alerts (automatically generated)

**Dataset**: `jira_v2_generic_alert_raw`

```sql
dataset = jira_v2_generic_alert_raw
| filter _alert_data != null
| alter alert_severity = json_extract_scalar(_alert_data, "$.severity")
| alter alert_category = json_extract_scalar(_alert_data, "$.alert_category")
| alter alert_name = json_extract_scalar(_alert_data, "$.alert_name")
| alter alert_description = json_extract_scalar(_alert_data, "$.alert_description")
```
