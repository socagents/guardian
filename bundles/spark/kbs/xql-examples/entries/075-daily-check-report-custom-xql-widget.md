---
id: XQL-075-e5ae180e
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
| filter sub_type = "ha"
| fields _time, log_source_name, severity, event_name, event_description
| sort desc _time
```
