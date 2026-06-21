---
id: XQL-021-e4fee5c7
title: Palo Alto Networks IoT Alerts (automatically generated)
category: alert-mapping
dataset: palo_alto_networks_iot_generic_alert_raw
tags:
- alter
- filter
ecosystem: xsiam
---
# Palo Alto Networks IoT Alerts (automatically generated)

**Dataset**: `palo_alto_networks_iot_generic_alert_raw`

```sql
dataset = palo_alto_networks_iot_generic_alert_raw
| filter _alert_data != null
| alter alert_severity = json_extract_scalar(_alert_data, "$.severity")
| alter alert_category = json_extract_scalar(_alert_data, "$.alert_category")
| alter alert_name = json_extract_scalar(_alert_data, "$.alert_name")
| alter alert_description = json_extract_scalar(_alert_data, "$.alert_description")
```
