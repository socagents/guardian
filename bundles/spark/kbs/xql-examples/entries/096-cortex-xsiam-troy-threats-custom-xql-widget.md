---
id: XQL-096-a291dbc2
title: Cortex XSIAM Troy Threats - Custom XQL Widget
category: investigation
dataset: panw_ngfw_threat_raw
tags:
- comp
- fields
- filter
- limit
- sort
ecosystem: xsiam
---
# Cortex XSIAM Troy Threats - Custom XQL Widget

**Dataset**: `panw_ngfw_threat_raw`

```sql
dataset = panw_ngfw_threat_raw
| filter severity not in ("informational", "low")
| filter from_zone != "TAP"
| comp count(_id) as hits by from_zone, to_zone,threat_name, threat_category,severity
| fields from_zone, to_zone, threat_name, threat_category,severity, hits
| sort desc hits
| limit 50
```
