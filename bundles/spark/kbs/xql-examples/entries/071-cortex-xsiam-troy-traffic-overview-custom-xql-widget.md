---
id: XQL-071-1800f63a
title: Cortex XSIAM Troy Traffic Overview - Custom XQL Widget
category: investigation
dataset: panw
tags:
- comp
- fields
- sort
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy Traffic Overview - Custom XQL Widget

**Dataset**: `panw`

```sql
dataset = panw*
| fields action
| comp count(_id ) as traffic_count by action
| sort desc traffic_count
| view graph type = column subtype = grouped layout = horizontal show_callouts = `true` xaxis = action yaxis = traffic_count seriescolor("traffic_count","#4384c2") xvaluesfontsize = 15 calloutfontsize = 15 legend = `false`
```
