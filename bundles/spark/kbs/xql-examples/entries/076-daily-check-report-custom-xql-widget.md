---
id: XQL-076-e5ae180e
title: Daily Check Report - Custom XQL Widget
category: investigation
dataset: panw_ngfw_threat_raw
tags:
- fields
- filter
- sort
ecosystem: xsiam
---
# Daily Check Report - Custom XQL Widget

**Dataset**: `panw_ngfw_threat_raw`

```sql
dataset = panw_ngfw_threat_raw
| filter severity in ("high", "critical")
| fields log_type, threat_name, from_zone, to_zone, source_ip, source_user, dest_ip, dest_port, app, action, severity, file_name, file_url
| sort desc _time
```
