---
id: XQL-001-bbfbd1c9
title: Arista Cloud Vision Wireless Alerts (automatically generated)
category: alert-mapping
dataset: arista_cloud_vision_wireless_generic_alert_raw
tags:
- alter
- filter
ecosystem: xsiam
---
# Arista Cloud Vision Wireless Alerts (automatically generated)

**Dataset**: `arista_cloud_vision_wireless_generic_alert_raw`

```sql
dataset = arista_cloud_vision_wireless_generic_alert_raw
| filter _alert_data != null
| alter alert_severity = json_extract_scalar(_alert_data, "$.severity")
| alter alert_category = json_extract_scalar(_alert_data, "$.alert_category")
| alter alert_name = json_extract_scalar(_alert_data, "$.alert_name")
| alter alert_description = json_extract_scalar(_alert_data, "$.alert_description")
```
