---
id: XQL-059-423f4558
title: Cortex XSIAM Troy NGFW 24h - Custom XQL Widget
category: investigation
dataset: panw_ngfw_traffic_raw
tags:
- comp
- filter
- limit
- sort
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy NGFW 24h - Custom XQL Widget

**Dataset**: `panw_ngfw_traffic_raw`

```sql
dataset = panw_ngfw_traffic_raw
| filter app not contains "xdr" and app not contains "paloalto" and app not contains "traps" and app not contains "traps" and app not contains "panos" and action = "allow"
| comp count(app ) as counter by app
| sort desc counter
| limit 10
| view graph type = pie subtype = full xaxis = app yaxis = counter
```
