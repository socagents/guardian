---
id: XQL-097-2fb3b951
title: Cortex XSIAM Troy Network Zones - Custom XQL Widget
category: investigation
dataset: panw
tags:
- alter
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
| comp count(_id) as counter by from_zone, to_zone
| alter zones = concat(from_zone, "-->", to_zone )
| filter zones != "TAP-->TAP"
| sort desc counter
| limit 10
| view graph type = area subtype = standard show_callouts = `true` show_percentage = `false` xaxis = zones yaxis = counter seriescolor("counter","#9b5e19") legend = `false`
```
