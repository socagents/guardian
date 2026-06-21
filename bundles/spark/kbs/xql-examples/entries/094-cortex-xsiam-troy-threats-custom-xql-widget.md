---
id: XQL-094-a291dbc2
title: Cortex XSIAM Troy Threats - Custom XQL Widget
category: investigation
dataset: panw_ngfw_threat_raw
tags:
- comp
- filter
- limit
- sort
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy Threats - Custom XQL Widget

**Dataset**: `panw_ngfw_threat_raw`

```sql
dataset = panw_ngfw_threat_raw
| filter severity != "Informational"
| comp count(_id ) as counter by severity
| sort desc counter
| limit 10
| view graph type = pie subtype = semi_donut xaxis = severity yaxis = counter
```
