---
id: XQL-092-a291dbc2
title: Cortex XSIAM Troy Threats - Custom XQL Widget
category: investigation
dataset: panw_ngfw_threat_raw
tags:
- bin
- comp
- filter
- sort
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy Threats - Custom XQL Widget

**Dataset**: `panw_ngfw_threat_raw`

```sql
dataset = panw_ngfw_threat_raw
| filter severity != "Informational"
| bin _time span = 1h
| sort asc _time
| comp count(_id ) as counter by _time
| view graph type = area subtype = stacked show_percentage = `false` xaxis = _time yaxis = counter seriescolor("counter","#32c262") seriestitle("counter","Threats")
```
