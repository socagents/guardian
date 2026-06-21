---
id: XQL-074-e5ae180e
title: Daily Check Report - Custom XQL Widget
category: investigation
dataset: panw_ngfw_system_raw
tags:
- fields
- filter
- sort
ecosystem: xsiam
---
# Daily Check Report - Custom XQL Widget

**Dataset**: `panw_ngfw_system_raw`

```sql
dataset = panw_ngfw_system_raw
| filter severity in ("high", "critical") and _reporting_device_name in ("BH_ASIA_*")
| fields _reporting_device_name, log_type, severity, event_name, event_description
| sort desc _time
```
