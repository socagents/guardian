---
id: XQL-014-a405ae5d
title: Generic Webhook Alerts (automatically generated)
category: alert-mapping
dataset: generic_webhook_generic_alert_raw
tags:
- alter
- filter
ecosystem: xsiam
---
# Generic Webhook Alerts (automatically generated)

**Dataset**: `generic_webhook_generic_alert_raw`

```sql
dataset = generic_webhook_generic_alert_raw
| filter _alert_data != null
| alter alert_severity = json_extract_scalar(_alert_data, "$.severity")
| alter alert_category = json_extract_scalar(_alert_data, "$.alert_category")
| alter alert_name = json_extract_scalar(_alert_data, "$.alert_name")
| alter alert_description = json_extract_scalar(_alert_data, "$.alert_description")
```
