---
id: XQL-064-46e8257b
title: Cortex XSIAM Troy NGFW Threat Hunting - Custom XQL Widget
category: investigation
dataset: panw_ngfw_traffic_raw
tags:
- comp
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy NGFW Threat Hunting - Custom XQL Widget

**Dataset**: `panw_ngfw_traffic_raw`

```sql
dataset = panw_ngfw_traffic_raw | comp count()
| view graph type = single subtype = standard header = "Total Traffic Logs" yaxis = count_1
```
