---
id: XQL-072-1800f63a
title: Cortex XSIAM Troy Traffic Overview - Custom XQL Widget
category: investigation
tags:
- alter
- comp
- sort
- view
ecosystem: xsiam
---
# Cortex XSIAM Troy Traffic Overview - Custom XQL Widget

```sql
preset = network_story
| alter proto = to_string(action_network_protocol )
| alter proto = if(proto = "1", "ICMP",proto = "6", "TCP",proto = "17", "UDP", proto = "47", "GRE", proto = "4", "IP-in-IP")
| comp count(event_id ) as traffic_count by proto
| sort desc traffic_count
| view graph type = pie subtype = semi_donut xaxis = proto yaxis = traffic_count
```
