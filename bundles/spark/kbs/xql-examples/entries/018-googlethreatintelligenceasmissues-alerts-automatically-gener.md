---
id: XQL-018-b5105c89
title: GoogleThreatIntelligenceASMIssues Alerts (automatically generated)
category: alert-mapping
dataset: googlethreatintelligenceasmissues_generic_alert_raw
tags:
- alter
- filter
ecosystem: xsiam
---
# GoogleThreatIntelligenceASMIssues Alerts (automatically generated)

**Dataset**: `googlethreatintelligenceasmissues_generic_alert_raw`

```sql
dataset = googlethreatintelligenceasmissues_generic_alert_raw
| filter _alert_data != null
| alter alert_severity = json_extract_scalar(_alert_data, "$.severity")
| alter alert_category = json_extract_scalar(_alert_data, "$.alert_category")
| alter alert_name = json_extract_scalar(_alert_data, "$.alert_name")
| alter alert_description = json_extract_scalar(_alert_data, "$.alert_description")
```
