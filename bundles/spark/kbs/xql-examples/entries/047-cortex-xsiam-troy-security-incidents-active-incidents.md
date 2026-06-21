---
id: XQL-047-6cecd981
title: Cortex XSIAM Troy Security Incidents - Active Incidents
category: investigation
dataset: incidents
tags:
- alter
- comp
- filter
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy Security Incidents - Active Incidents

**Dataset**: `incidents`

```sql
dataset = incidents
| filter (status = ENUM.NEW or status = ENUM.UNDER_INVESTIGATION)
| filter starred = 1
| comp count_distinct(incident_id)
| alter from_time = parse_timestamp("%Y-%m-%d %H:%M:%S ", "2024-12-06 00:00:00")
| alter to_time = parse_timestamp("%Y-%m-%d %H:%M:%S ", "2024-12-09 00:00:00")
| view graph type = single subtype = standard yaxis = count_distinct_1
```
