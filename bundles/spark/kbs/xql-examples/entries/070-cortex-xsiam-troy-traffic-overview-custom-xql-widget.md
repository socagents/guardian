---
id: XQL-070-1800f63a
title: Cortex XSIAM Troy Traffic Overview - Custom XQL Widget
category: investigation
tags:
- alter
- comp
- limit
- sort
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy Traffic Overview - Custom XQL Widget

```sql
preset = network_story
| alter app = arrayindex(action_app_id_transitions ,2)
| comp count(event_id ) as traffic_count by app
| sort desc traffic_count
| limit 12
| view graph type = column subtype = grouped layout = horizontal show_callouts = `true` xaxis = app yaxis = traffic_count seriescolor("traffic_count","#4384c2") xvaluesfontsize = 12 legend = `false`
```
