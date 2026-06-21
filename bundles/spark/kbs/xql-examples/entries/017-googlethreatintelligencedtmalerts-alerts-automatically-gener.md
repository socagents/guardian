---
id: XQL-017-b15edc6f
title: GoogleThreatIntelligenceDTMAlerts Alerts (automatically generated)
category: alert-mapping
dataset: googlethreatintelligencedtmalerts_generic_alert_raw
tags:
- alter
- filter
ecosystem: xsiam
---
# GoogleThreatIntelligenceDTMAlerts Alerts (automatically generated)

**Dataset**: `googlethreatintelligencedtmalerts_generic_alert_raw`

```sql
dataset = googlethreatintelligencedtmalerts_generic_alert_raw
| filter _alert_data != null
| alter alert_severity = json_extract_scalar(_alert_data, "$.severity")
| alter alert_category = json_extract_scalar(_alert_data, "$.alert_category")
| alter alert_name = json_extract_scalar(_alert_data, "$.alert_name")
| alter alert_description = json_extract_scalar(_alert_data, "$.alert_description")
```
