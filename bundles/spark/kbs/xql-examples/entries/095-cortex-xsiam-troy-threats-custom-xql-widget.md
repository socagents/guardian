---
id: XQL-095-a291dbc2
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
| filter threat_category != "unknown"
| comp count(_id ) as traffic_count by threat_category
| sort desc traffic_count
| limit 10
| view graph type = column subtype = grouped layout = horizontal show_callouts = `true` xaxis = threat_category yaxis = traffic_count seriescolor("traffic_count","#32c262") calloutfontsize = 13 legend = `false`
```
