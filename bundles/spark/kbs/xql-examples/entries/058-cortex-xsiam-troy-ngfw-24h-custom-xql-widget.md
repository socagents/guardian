---
id: XQL-058-423f4558
title: Cortex XSIAM Troy NGFW 24h - Custom XQL Widget
category: investigation
dataset: incidents
tags:
- comp
- filter
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy NGFW 24h - Custom XQL Widget

**Dataset**: `incidents`

```sql
dataset = incidents
| filter status = ENUM.RESOLVED_AUTO_RESOLVE and alert_sources = "FW"
| comp count(status)
| view graph type = single subtype = standard header = "Auto Closed 24h" yaxis = count_1 headcolor = "#08ff4b" headerfontsize = 60
```
