---
id: XQL-099-2fb3b951
title: Cortex XSIAM Troy Network Zones - Custom XQL Widget
category: investigation
dataset: panw
tags:
- comp
- filter
- limit
- sort
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy Network Zones - Custom XQL Widget

**Dataset**: `panw`

```sql
dataset = panw*
| comp count(_id) as traffic_count by from_zone
| filter from_zone != "TAP"
| sort desc traffic_count
| limit 10
| view graph type = column subtype = grouped layout = horizontal show_callouts = `true` xaxis = from_zone yaxis = traffic_count seriescolor("counter","#9b5e19") seriescolor("traffic_count","#9b5e19") xvaluesfontsize = 15 calloutfontsize = 15 legend = `false` seriestitle("counter","traffic_count")
```
