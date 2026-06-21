---
id: XQL-104-ee730375
title: Cortex XSIAM Troy DNS Activity - Custom XQL Widget
category: investigation
tags:
- alter
- comp
- filter
- sort
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy DNS Activity - Custom XQL Widget

```sql
preset = network_story
| alter app = lowercase(arraystring(action_app_id_transitions,","))
| filter app contains "dns"
| comp count(event_id ) as counter by dns_reply_code
| sort desc counter
| view graph type = column subtype = grouped layout = horizontal show_callouts = `true` xaxis = dns_reply_code yaxis = counter seriescolor("counter","#ec9d7c") xvaluesfontsize = 15 calloutfontsize = 15 legend = `false`
```
