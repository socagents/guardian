---
id: XQL-105-ee730375
title: Cortex XSIAM Troy DNS Activity - Custom XQL Widget
category: investigation
tags:
- alter
- bin
- comp
- filter
- sort
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy DNS Activity - Custom XQL Widget

```sql
preset = network_story
| bin _time span =1h
| sort asc  _time
| alter app = lowercase(arraystring(action_app_id_transitions,","))
| filter app contains "dns"
| comp count(event_id ) as counter by _time
| view graph type = line xaxis = _time yaxis = counter default_limit = `false` seriescolor("counter","#ec9d7c") seriestitle("counter","DNS Queries")
```
